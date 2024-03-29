"""
A collection of classes and utilities to assist with web scraping

Author: Eelco van Vliet
"""
import collections
import datetime
import logging
import os
import pickle
import re
from functools import wraps
from pathlib import Path
from urllib.parse import (urljoin, urlparse)

import pandas as pd
import pytz
import requests
import tldextract
from OpenSSL.SSL import Error as OpenSSLError
from requests.adapters import HTTPAdapter
from requests.exceptions import (ConnectionError, ReadTimeout, TooManyRedirects, MissingSchema,
                                 InvalidSchema, SSLError, RetryError, InvalidURL,
                                 ContentDecodingError, ChunkedEncodingError)
from urllib3.exceptions import MaxRetryError
from urllib3.util import Retry

from cbs_utils.global_vars import *
from cbs_utils.regular_expressions import *
from cbs_utils.misc import (make_directory, get_dir_size)

logger = logging.getLogger(__name__)

try:
    from bs4 import BeautifulSoup
except ImportError:
    logger.warning("Could not load bs4. Please make sure you install it ")


def get_clean_url(url):
    """ Get the base of a url without the relative part """
    cl = tldextract.extract(url)
    if cl.subdomain == "":
        clean_url = cl.registered_domain
    else:
        clean_url = ".".join([cl.subdomain, cl.registered_domain])
    return clean_url


def strip_url_schema(url):
    return re.sub(r"http[s]{0,1}://", "", url)


class HRefCheck(object):
    """
    Class to check if a hyper ref obtained from a web page is a valid internal or external 
    hyper-reference
    
    Parameters
    ----------
    href: str   
        hyper-reference to check as found on the domain
    url: str    
        Main domain name. Used to check if we have a internal or external hyper-reference
    valid_extensions: list, optional 
        List of string with valid extensions. Default = [".html"]
    max_depth: int, optional
        Maximum search depth. Default = 1
    branch_count: object
        collection.Counter object which keeps the current count of each branch. This is used to 
        check how often subbranches of the domain are visited. In case the *max_branch_count* is
        exceeded we stop searching this branch
    max_branch_count: int, optional
        Maximum number of time a branch in a domain is visit. For instance, in case we have 
        ebay/cars/ as branch, there may be 100,000 cars under this branch which would be all 
        visited. with branch counter. Now we can stop visiting this branch. Default = 50
    schema: str, optional
        Either http or https. If not given (None) then the scheme will be obtained by doing 
        requests to the side, however, in case we give a 'schema', this can be skipped and the 
        given schema is used
    ssl_valid: bool, optional
        In case of a https schema, this flag indicates if the certificate was valid.
    validate_url: bool
        Validate each url if it gives a 200 code.
    """

    def __init__(self, href, url, valid_extensions=None, max_depth=1,
                 branch_count=None, max_branch_count=50,
                 schema=None, ssl_valid=True, validate_url=False):
        self.href = href
        self.url = url
        self.branch_count = branch_count
        self.max_branch_count = max_branch_count
        self.schema = schema
        self.ssl_valid = ssl_valid

        self.url_extract = tldextract.extract(url)
        self.href_extract = tldextract.extract(href)

        self.ssl_key = True
        self.validate_url = validate_url
        self.connection_error = False
        self.invalid_scheme = False
        self.relative_link = False
        self.external_link = False

        self.max_depth = max_depth

        if valid_extensions is None:
            self.valid_extensions = [".html"]
        else:
            self.valid_extensions = valid_extensions

        self.valid_href = self.is_valid_href()

        self.full_href_url = None
        self.clean_href_url = None
        self.url_req = None

        if self.valid_href:
            self.get_full_url(href=href)

    def get_full_url(self, href):
        """ Test if this href could be a full url and if so, if it is valid """

        is_valid_url = is_url(href)

        # all hrefs starting with a '/' or './' are relative to the root
        if href.startswith("/") or href.startswith(
                "./") or self.href_extract.domain == "html" or not is_valid_url:
            # this link is relative to the root. Extend it
            try:
                self.full_href_url = urljoin(self.url, href)
            except ValueError:
                self.valid_href = False
            else:
                self.relative_link = True
        else:
            # this reference is already absolute
            href_url = href
            self.relative_link = False

            self.url_req = RequestUrl(href_url, schema=self.schema, ssl_valid=self.ssl_valid,
                                      validate_url=self.validate_url)

            self.full_href_url = self.url_req.url

            try:
                self.clean_href_url = get_clean_url(self.full_href_url)
            except TypeError as err:
                self.valid_href = False
                return

            # the href is a independent link. If it is outside the domain, skip it but store
            href_domain = self.href_extract.domain
            domain = self.url_extract.domain
            logger.debug(f"Got 200 code from {href}: compare {href_domain} - {domain}")
            if href_domain != domain:
                self.external_link = True

    def is_valid_href(self):
        """
        Check if the current hyper-reference is valid such that we can follow it further
        
        Returns
        -------
        bool:
            Flag which is True in case the hyperref is valid  
        """

        href = self.href

        # skip special page references
        if href in ("#", "/", "-"):
            logger.debug(f"Skipping special page link {href}")
            return False

        if set("#?").intersection(set(href)):
            logger.debug(f"Skipping href with forbidden # {href}")
            return False

        # skip images
        base, ext = os.path.splitext(href)
        if ext != "" and ext.lower() not in self.valid_extensions:
            logger.debug(f"href {href} has an extension which is not an html. Skipping")
            return False

        # number_of_space_dummies = href.count("-") + href.count("_")
        # if number_of_space_dummies > self.max_space_dummies:
        #     logger.debug(f"Max num#ber of spaces {number_of_space_dummies} exceeded. Skipping")
        #     return False

        if ":" in strip_url_schema(href):
            # this is to check if this is not a telefoon:
            logger.debug(f"Core href {href} contains a :. Skipping")
            return False

        href_ext = tldextract.extract(href)
        logger.debug(f"Stripping {self.url} from {href}")
        try:
            href_rel_to_domain = re.sub(strip_url_schema(self.url), "", strip_url_schema(href))
        except re.error as err:
            logger.warning(f"Could not strip ulr {self.url}: {err}")
            return False

        # get branches
        sections = re.sub(r"^/|/$", "", href_rel_to_domain).split("/")
        branch_depth = len(sections)
        if self.max_branch_count is not None and branch_depth > 0:
            first_branch = sections[0]
            self.branch_count.update({first_branch: 1})
            if self.branch_count[first_branch] > self.max_branch_count:
                logger.debug(f"Branch {first_branch} has occurred more than "
                             f"{self.max_branch_count} times. Skipping {href} ")
                return False

        # for links within the domain, check if it is not too deep
        if strip_url_schema(href_ext.domain) in ("", strip_url_schema(self.url_extract.domain)):
            if re.search(r"\.html$", href_rel_to_domain):
                # in case we are looking a html already, we can lower the depth of the branch
                branch_depth -= 1
            if branch_depth > self.max_depth:
                logger.debug(f"Maximum branch depth exceeded with {branch_depth}. Skipping {href}")
                return False

        return True


class RequestUrl(object):
    """
    Add a protocol (https, http) if we don't have any. Try which one fits
    
    Parameters
    ----------
    url: str
        Url to get the protocal from 
    session: optional
        Session object of an already open session can be passed
    timeout: float, optional
        Time-out of the request. Default = 5 s
    retries: int, optional
        Number of time we try to connect.  Default = 3
    backoff_factor: float, optional
        Time that we delay. Default = 0.3
    status_forcelist: list, optional 
        List of status codes which we force to stop. Default = (500, 502, 503, 504),
    schema: str, optional
        Schema of the url (http or https). If given, this schema is used. Default = None, 
        which means it will be obtained by the class
    ssl_valid: bool, optional
        True in case the certificate is valid of a https
    validate_url: bool, optional
        Make connection to the url to validate if it exists (has 200 code). Default=False

    Examples
    --------

    >>> req = RequestUrl("www.google.com")

    This adds https to www.google.com as this is the first address that is valid
    """

    def __init__(self,
                 url: str,
                 session=None,
                 timeout: float = 5.0,
                 retries: int = 3,
                 backoff_factor: float = 0.3,
                 status_forcelist: list = (500, 502, 503, 504),
                 schema=None,
                 ssl_valid=None,
                 validate_url=False
                 ):

        self.url = None
        self.ssl = None
        self.ext = None
        self.connection_error = False
        self.ssl_valid = True
        self.status_code = None
        self.timeout = timeout
        self.verify = True

        # start a session with a user agent
        self.session = requests_retry_session(
            retries=retries,
            backoff_factor=backoff_factor,
            status_forcelist=status_forcelist,
            session=session
        )
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/61.0.3163.100 Safari/537.36'})

        if schema is None:
            logger.debug(f"Assign schema to {url}")
            self.assign_protocol_to_url(url)
        else:
            clean_url = strip_url_schema(url)
            self.url = self.add_schema_to_url(clean_url, schema=schema)
            self.ssl_valid = ssl_valid
            # this checks if the url has a proper 200 response for our schema and set it to
            if validate_url:
                self.make_contact_with_url(clean_url, schema=schema, verify=ssl_valid)
            else:
                self.status_code = 200
            logger.debug(f"Added external schema: {self.url}")

        if self.url is not None:
            self.ssl = self.url.startswith("https://")
            self.ext = tldextract.extract(self.url)
            if self.ssl:
                self.schema = "https"
            else:
                self.schema = "http"

        self.session.close()

    def assign_protocol_to_url(self, url):
        """ Add http of https to an url and check if the tls is valid """

        clean_url = strip_url_schema(url)

        for schema in ("https", "http"):
            for verify in (True, False):
                success = self.make_contact_with_url(clean_url, schema=schema, verify=verify)
                if success:
                    break
            if success:
                break

    @staticmethod
    def add_schema_to_url(url, schema="https"):
        """ create a full url link including http or https a """
        full_url = f'{schema}://{url}/'
        full_url = re.sub(r"//$", "/", full_url)
        return full_url

    def make_contact_with_url(self, url, schema="https", verify=True):
        """ Connect to the url to see if it is valid """

        full_url = self.add_schema_to_url(url, schema=schema)

        success = False
        self.verify = verify
        try:
            # use allow redirect to prevent blocking from a site if they use a redirect
            logger.debug(f"Requesting {full_url} with verify={verify}")
            req = self.session.head(full_url, timeout=self.timeout, verify=verify,
                                    allow_redirects=True)
        except SSLError as err:
            logger.debug(f"Failed request {full_url} due to SSL: {err}")
            self.ssl_valid = False
        except (ConnectionError, ReadTimeout, MaxRetryError, RetryError, InvalidURL) as err:
            self.connection_error = True
            logger.debug(f"Failed request {full_url}: {err}")
        except Exception as err:
            self.connection_error = True
            logger.info(f"Failed request with unknown error {full_url}: {err}")
        else:
            success = True
            self.status_code = req.status_code
            logger.debug(f"Success {full_url} with {self.status_code}")
            self.url = req.url
            if self.status_code != 200:
                logger.debug(f"Connection error {full_url} : {self.status_code}")
                success = False
            else:
                logger.debug(f"Good connection {full_url} : {self.status_code}")

        return success

    def __str__(self):
        """ Override the __str__ method of the class for a nice output """

        msgf = "{:20s}: {}\n"
        msg = msgf.format("URL", self.url)
        msg += msgf.format("SSL", self.ssl)
        msg += msgf.format("status_code", self.status_code)
        msg += msgf.format("connection error", self.connection_error)

        return msg


class UrlSearchStrings(object):
    """
    Class to set up a recursive search of string on web pages

    Parameters
    ----------
    url: str    
        Main url to start searching
    search_strings: dict
        Dictionary with the searches performed per page. The form is::

            {
                "name_of_search_1": "search_string_1" ,
                "name_of_search_2": "search_string_2" 
            }

    store_page_to_cache: bool, optional
        Each page retrieved is also stored to cache if true. Default = False
    timeout: float, optional
        Time in sec to wait on a request before going to the next. Default = 1.0
    sort_order_hrefs: dict, optional
        Give an list of names of subdomain which we want to search first
    stop_search_on_found_keys: list
        List of search keys from the *search_strings* dict for which we immediately stop with 
        searching as soon as we found a match 
    store_page_to_cache: bool, optional
        Store all the pages to cache
    cache_directory: str, optional
        Name of the cache directory, default="cache"
    timeout: float, optional
       Stop requesting the page after *timeout* seconds. Default = 5.0 s
    max_frames: int, optional
        Maximum number of frames we scrape. Default = 10
    max_hrefs: int, optional
        Maximum number of hyper references we follow. Default = 1000
    max_depth: int, optional
        Maximum depth we search the domain. Default = 1
    max_branch_count: int, optional
        Maximum number of request per branch. Default = 10
    max_cache_dir_size: int, optional
        Maximum size of the cache directory in Mb. If None, there is no maximum. If 0, no cache 
        is written. If a finite number, each request before writing the cache, first the current
        directory size needs to be checked, so that slows down the code significantly. Default=None
    scrape_url: bool, optional
        Flag to indicate if we want to scrape. If false, no scraping or any other access of internet
        is done. This allows to use the object with doing a scrape
    timezone: str, optional
        Time zone of the scrape. Default = "Europe/Amsterdam"
    schema str, optional
        Protocal of the url, http or https. If None (default) it will be obtained
    ssl_valid: bool, optional
        Flag to indicate if the tls encryption has a valid certificate
    validate_url:
        Validate url to check if it exists
        

    Attributes
    ----------
    exists: bool
        Set flag True is url exists
    matches: dict
        Dictionary containing the results of the searches defined by *search_strings*. The keys
        are derived from the *search_strings* key, the results are lists containing all the matches
    number_of_iterations: int
        Number of recursions 
    
    Notes
    -----
    * This class can also handle web page with frames. Normally, these are not analysed by
      beautiful soup, however, by explicitly looking up all frames and following the links defined
      by the 'src' tag, we can access all the frames in an url

    Examples
    --------

    Let she we have a web site 'www.example.com' want to extract all the postcodes. Also, we want
    to get all the words with more than 10 characters. For this, store your regular expression
    for both searches in a dictionary and feed it to the UrlSearchStrings class

    >>> url = "www.example.com"
    >>> search = dict(postcode=r"\d{4}\s{0,1}[a-zA-Z]{2}", longwords=r"\w{11,}")
    >>> url_analyse = UrlSearchStrings(url, search_strings=search)

    The results are stored in the 'matches' attribute of the class and can be report by printing
    the class like: 

    >>> print(url_analyse)
    Matches in https://www.example.com/
    postcode : []
    longwords : ['established', 'illustrative', 'coordination', 'information']

    In our example, the matches with the postal codes is empty (for the example domain). and we have
    found 5 words with more than 10 characters

    >>> postcodes = url_analyse.matches["postcode"]

    Note that the keys of the *matches* dictionary are the same as the keys we used for the search
    """

    def __init__(self, url,
                 search_strings: dict,
                 sort_order_hrefs: list = None,
                 stop_search_on_found_keys: list = None,
                 store_page_to_cache=False,
                 cache_directory="cache",
                 timeout=5.0,
                 max_frames=10,
                 max_hrefs=1000,
                 max_depth=2,
                 max_branch_count=10,
                 max_cache_dir_size=None,
                 scrape_url=True,
                 timezone="Europe/Amsterdam",
                 schema=None,
                 ssl_valid=None,
                 validate_url=None
                 ):

        self.store_page_to_cache = store_page_to_cache
        self.cache_directory = cache_directory
        self.max_cache_dir_size = max_cache_dir_size

        self.sort_order_hrefs = sort_order_hrefs
        self.stop_search_on_found_keys = stop_search_on_found_keys

        # this call checks if we need https or http to connect to the side
        self.schema = schema
        self.ssl_valid = ssl_valid
        self.validate_url = True
        if schema is not None and ssl_valid is not None:
            # in case a scheme is given, but the validate_url flag not: do not validate
            if validate_url is None:
                self.validate_url = False
            else:
                self.validate_url = validate_url
        self.req = RequestUrl(url, schema=schema, ssl_valid=ssl_valid,
                              validate_url=self.validate_url)
        logger.debug(f"with scrape flag={scrape_url} got {self.req}")
        if self.schema is None:
            self.schema = self.req.schema
        if self.ssl_valid is None:
            self.ssl_valid = self.req.ssl_valid

        self.external_hrefs = list()
        self.followed_urls = list()

        self.max_frames = max_frames
        self.max_hrefs = max_hrefs
        self.max_depth = max_depth
        self.max_branch_count = max_branch_count
        self.timeout = timeout
        self.exists = False
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/61.0.3163.100 Safari/537.36'}
        if scrape_url:
            self.session = requests_retry_session()
            self.session.headers.update(self.headers)
        else:
            self.session = requests.Session()

        self.stop_with_scanning_this_url = False

        self.search_regexp = dict()
        for key, regexp in search_strings.items():
            # store the compiled regular expressions in a dictionary 
            self.search_regexp[key] = re.compile(regexp)

        # results are stored in these attributes
        self.matches = dict()
        self.url_per_match = dict()
        for key in self.search_regexp.keys():
            self.matches[key] = list()
            self.url_per_match[key] = dict()

        self.frame_counter = 0
        self.href_counter = 0
        self.branch_count = collections.Counter()

        self.href_df = None

        self.current_branch_depth = 0

        if scrape_url:
            if self.req.url is not None and self.req.status_code == 200:
                # start the recursive search
                logger.debug(f"------------> Start searching {self.req.url}")
                self.recursive_pattern_search(self.req.url)
                logger.debug(f"------------> Done searching {self.req.url}")
            else:
                self.exists = False
                logger.debug(f"------------> Could not connect for {self.req.url}. Skipping")
        else:
            logger.debug(f"Scrape flag was false: skip scraping {url}")
            self.exists = None

        if self.session is not None:
            self.session.close()

        self.process_time = datetime.datetime.now(pytz.timezone(timezone))

    def recursive_pattern_search(self, url, follow_hrefs_to_next_page=True):
        """
        Search the 'url'  for the patterns and continue of links to other pages are present
        """

        if self.stop_with_scanning_this_url:
            logger.debug("STOP flag set for recursion search.")
            return

        try:
            soup = self.make_soup(url)
        except (InvalidSchema, MissingSchema) as err:
            logger.warning(err)
            soup = None

        if soup:

            # first do all the searches defined in the search_strings dictionary
            for key, regexp in self.search_regexp.items():
                result = self.get_patterns(soup, regexp)
                if result:
                    logger.debug(f"Extending search {key} with {result}")
                    # extend the total results with the current result
                    self.matches[key].extend(result)
                    # per match of a key we also store the url where it was found
                    for match in result:
                        self.url_per_match[key][match] = url
                else:
                    logger.debug(f"No matches found for {key} at {url}")

            # next, see if there are any frames. If so, retrieve the *src* reference and recursively
            # search again calling this routine
            logger.debug(f"Following all frames,  counter {self.frame_counter}")
            self.follow_frames(soup=soup, url=url)

            # next, follow all the hyper references
            if follow_hrefs_to_next_page:
                logger.debug(f"Following all hrefs,  counter {self.href_counter}")
                self.follow_hrefs(soup=soup)

        else:
            logger.debug(f"No soup retrieved from {url}")

    def make_href_df(self, links):
        """
        Create a pandas dataframe of all the hyper reference on this page and keep track of the 
        properties of the hrefs. At the end, a sort of the references is made
        
        Parameters
        ----------
        links: list
            List of hyper references
        """

        valid_urls = list()
        valid_hrefs = list()
        extern_href = list()
        relative = list()
        rankings = list()
        logger.debug("Start creating a sorted href list for {} links".format(len(links)))
        for link in links:
            # we strip the http:// or https:// because sometime the internal links have http
            href = link["href"]

            ext = tldextract.extract(href)

            try:
                clean_href = get_clean_url(href)
            except TypeError:
                logger.debug("Could not clean the href. Just continue")
                continue
            else:
                if clean_href in self.external_hrefs:
                    logger.debug(f"external domain of href {href} already in domain. SKipping")
                    continue

            if href in valid_hrefs or href in valid_urls:
                logger.debug(f"internal href {href} already in domain. SKipping")
                continue

            logger.debug(f"Checking {href} because {ext.domain} not in externals")
            check = HRefCheck(href, url=self.req.url, branch_count=self.branch_count,
                              schema=self.schema, ssl_valid=self.ssl_valid,
                              validate_url=self.validate_url)

            if check.valid_href:
                valid_hrefs.append(href)
                valid_urls.append(check.full_href_url)
                if check.external_link:
                    extern_href.append(True)
                    if check.clean_href_url not in self.external_hrefs:
                        logger.debug(f"adding external link href {check.clean_href_url}")
                        self.external_hrefs.append(check.clean_href_url)
                else:
                    logger.debug(f"href is internal {href} ({check.full_href_url})")
                    extern_href.append(False)

                if check.relative_link:
                    relative.append(True)
                else:
                    relative.append(False)

                # we check here if the href matches a given list of string which are likely to
                # have contact information (such at about-us, info, etc). Give it a ranking point
                # such we can sort the href list based on its score. Those proper matches will
                # be scraped first
                ranking = 0
                if self.sort_order_hrefs is not None:
                    for regexp in self.sort_order_hrefs:
                        if bool(re.search(regexp, href, re.IGNORECASE)):
                            ranking = 1
                            break
                rankings.append(ranking)
            else:
                logger.debug(f"skipping invalid href {href}")

        self.href_df = pd.DataFrame(
            list(zip(valid_hrefs, valid_urls, extern_href, relative, rankings)),
            columns=[HREF_KEY, URL_KEY, EXTERNAL_KEY, RELATIVE_KEY, RANKING_KEY])
        self.href_df[CLICKS_KEY] = 0

        # sort the url group with the relative key, and drop all double full urls
        self.href_df.sort_values([URL_KEY, RELATIVE_KEY], inplace=True)
        self.href_df.drop_duplicates([URL_KEY], inplace=True, keep="last")

        # now sort again on the ranking
        self.href_df.sort_values([RANKING_KEY], inplace=True, ascending=False)

        logger.debug("Created href data frame with {} hres:\n{}"
                     "".format(self.href_df.index.size, self.href_df[[URL_KEY]].head(10)))

    def follow_hrefs(self, soup):
        """
        In the current soup, find all the hyper references and follow them if we stay in the domain

        Parameters
        ----------
        soup: BeautifulSoup.soup
            The current soup
        url: str
            The current url
        """

        links = soup.find_all('a', href=True)

        # only for the first page, get a list of the all the hrefs with the number of clicks
        if self.href_df is None:
            self.make_href_df(links)

        # first store all the external refs
        external_url_df = self.href_df[self.href_df[EXTERNAL_KEY]]
        for index, row in external_url_df.iterrows():
            url = row[URL_KEY]
            external = row[EXTERNAL_KEY]
            if external and url not in self.external_hrefs:
                logger.debug(f"Store external url {url} and continue")
                self.external_hrefs.append(url)

        for index, row in self.href_df.iterrows():
            self.href_counter += 1
            href = row[HREF_KEY]
            url = row[URL_KEY]

            if url in self.external_hrefs:
                logger.debug(f"SKipping external ref {url}")
                continue

            logger.debug(f"Found href {self.href_counter}: {href}")

            if url in self.followed_urls:
                logger.debug(f"Skipping {url}. Already followed it")
                continue

            self.followed_urls.append(url)

            if self.href_counter <= self.max_hrefs:
                logger.debug(f"Recursive call to pattern search with {url}")
                self.recursive_pattern_search(url, follow_hrefs_to_next_page=False)
            else:
                logger.warning(
                    "Maximum number of {} hrefs iterations reached. Quiting"
                    "".format(self.max_hrefs))

            # in case we have passed a list of keys for which we want to stop as soon we have found
            # match, loop over those keys and see if any matches were found
            if self.stop_search_on_found_keys is not None:
                for key in self.stop_search_on_found_keys:
                    if self.matches[key]:
                        # we found a match for this key. Stop searching any href immediately
                        logger.info(f"Found a match for {key} at {url}")
                        self.stop_with_scanning_this_url = True
                        break

            if self.stop_with_scanning_this_url:
                logger.debug(f"Stop request for this page is set due")
                break

        logger.debug("Done following hrefs on this page")

    def follow_frames(self, soup, url):
        """
        In the current soup, find all the frames and for each frame start a new pattern search

        Parameters
        ----------
        soup: BeautifulSoup.soup
            The current soup
        url: str
            The current url
        """

        frames = soup.find_all('frame')
        if frames:
            self.frame_counter += 1
            for frame in frames:
                src = frame.get('src')
                url = urljoin(url, src)

                if self.frame_counter <= self.max_frames:
                    logger.debug(f"Recursive call to pattern search with {url}")
                    self.recursive_pattern_search(url)
                else:
                    logger.warning(
                        "Maximum number of {} iterations reached. Quiting"
                        "".format(self.max_frames))
        else:
            logger.debug(f"No frames found for {url}")

    def make_soup(self, url):
        """ Get the beautiful soup of the page *url*"""

        soup = None
        try:
            if self.store_page_to_cache:
                logger.info("Get (cached) page: {} with validate {}".format(url, self.req.verify))
                page = get_page_from_url(url,
                                         session=self.session,
                                         timeout=self.timeout,
                                         max_cache_dir_size=self.max_cache_dir_size,
                                         headers=self.headers,
                                         verify=self.req.verify,
                                         cache_directory=self.cache_directory)
            else:
                logger.info("Get page: {}".format(url))
                page = self.session.get(url, timeout=self.timeout, verify=False,
                                        headers=self.headers, allow_redirects=True)
        except (ConnectionError, ReadTimeout, RetryError) as err:
            logger.warning(err)
        else:
            if page is None or page.status_code != 200:
                logger.warning(f"Page not found: {url}")
            else:
                self.exists = True
                soup = BeautifulSoup(page.text, 'lxml')

        return soup

    @staticmethod
    def get_patterns(soup, regexp) -> list:
        """
        Retrieve all the pattern match in the soup obtained from the url with Beautifulsoup
        
        Parameters
        ----------
        soup: object:BeautifulSoup
            Return value of the beautiful soup of the page where we want to search
        regexp: re.Pattern
            Compiled regular expression to find on this page

        Returns
        -------
        list:
            List of matches with the regular expression
        """

        matches = list()
        lines = soup.find_all(string=regexp)
        for line in lines:
            all_match_on_line = regexp.finditer(str(line))
            for match in all_match_on_line:
                matches.append(match.group(0).strip())

        return matches

    def __str__(self):
        """ Overload print method with some information """

        if self.req is not None:
            string = "Matches in {}".format(self.req.url)
            for key, matches in self.matches.items():
                string += "\n{} : ".format(key)
                string += "{}".format(matches)
        else:
            string = "No scrape was done as req is None"

        return string


def make_cache_file_name(function_name, args):
    """
    Create a cache file name based on the function name + list of arguments

    Parameters
    ----------
    function_name: str
        name of the function to prepend
    args: tuple
        arguments passed to the function

    Returns
    -------
    str:
        Name of the cache file

    Notes
    -----
    * Used by *cache_to_disk* to make a name of a cache file based on its input arguments
    * To make sure that we get a valid file name, we remove all the special characters
    """

    cache_file = '{}{}'.format(function_name, args).replace("/", "_")
    cache_file = re.sub(r"[\"'():,.&%#$;\s]", "_", cache_file)
    cache_file = re.sub(r"[__]{1,}", "_", cache_file)
    cache_file += ".pkl"

    return cache_file


def cache_to_disk(func):
    """
    Decorator which allows to cache the output of a function to disk

    Parameters
    ----------
    skip_cache: bool
        If True, always skip the cache, even the decorator was added
    max_cache_dir_size: int or None
        If not None, check if the size of the cache directory is not exceeding the maximum
        given in Mb
    cache_directory: str
        Name of the cache file output directory

    Examples
    --------

    Say you have a function that reads the contents of a web page from internet::

        @cache_to_disk
        def get_page_from_url(url, timeout=1.0):
            try:
                page = requests.get(url, timeout=timeout)
            except requests.exceptions.ConnectionError as err:
                page = None
            return page

    Without the @cache_to_disk decorator, you would just read the contents of a html file with::

        page = get_page_from_url("nu.nl")

    However, because we have added the @cache_to_disk decorator, the first time the data is read
    from the website, but this is stored to a pickle file. All the next runs you just obtain the
    data from the pickle file.

    The cache_to_disk decorator checks if some parameters are given. With the *skip_cache* flag you
    can prevent the cache being used even if the decorator was added
    In case the *max_cache_dir_size* is defined, the size of the cache directory is checked first
    and only new cache is written if the size of the directory in MB is smaller than the defined
    maximum. An example of using the maximum would be::

        page = get_page_from_url("nu.nl", max_cache_dir_size=0)

    In this example, we do not allow to add new cache files at all, but old cache files can still
    be read if present in the cache dir

    """
    @wraps(func)
    def wrapper(*args, **kwargs):

        skip_cache = kwargs.get("skip_cache", False)
        max_cache_dir_size = kwargs.get("max_cache_dir_size", None)
        if skip_cache:
            # in case the 'skip_cache' option was used, just return the result without caching
            return func(*args, **kwargs)

        cache_file = make_cache_file_name(func.__name__, args)
        cache_dir = Path(kwargs.get("cache_directory", "cache"))

        make_directory(cache_dir)
        cache = Path(cache_dir) / cache_file

        skip_write_new_cache = False
        if max_cache_dir_size is not None:
            if max_cache_dir_size == 0:
                skip_write_new_cache = True
            else:
                cache_dir_size = get_dir_size(cache_dir)
                if cache_dir_size >= max_cache_dir_size:
                    # we are allowed to read, but not allowed to write
                    skip_write_new_cache = True

        try:
            with open(cache, 'rb') as f:
                data = pickle.load(f)
                logger.debug(f"Retrieved from cache {cache}")
                return data
        except (FileNotFoundError, OSError, EOFError):
            result = func(*args, **kwargs)
            if not skip_write_new_cache:
                try:
                    with open(cache, 'wb') as f:
                        logger.debug(f"Dumping to cache {cache}")
                        pickle.dump(result, f)
                except OSError as err:
                    logger.warning(f"Cache write error:\n{err}")
            return result

    return wrapper


@cache_to_disk
def get_page_from_url(url, session=None, timeout=1.0, skip_cache=False, raise_exceptions=False,
                      max_cache_dir_size=None, headers=None, verify=True, cache_directory=None):
    
    """
    Get the contents of *url* and immediately store the result to a cache file

    Args:
        url: str
            String with the url to fetch
        session: object:Session:
            A session can be passed in case you want to keep it open
        timeout: float
            Number of seconds you try to connect
        skip_cache: bool
            If True, prevent that we are using the cache decorator
        skip_cache: bool
            If True, do not write new cache.
        raise_exceptions: bool
            If True, raise the exceptions of the requests
        max_cache_dir_size: int
            Maximum size of cache in Mb. Stop writing cache as soon max_cache has been reached. If None,
            this test is skip and the cache is always written. If 0, we never write cache and therefore
            the check of the current directory size can be skipped, which significantly speeds up the
            code
        headers: dict
            Headers to use for the request
        verify: bool
            Forces to verify the certificate
        cache_directory: str
            Name of the cache directory which is passed to the decorator

    Returns:
        
        request.Page:
            The html page

    Notes:
       * The 'cache_to_dist' decorator takes care of  caching the data to the directory *cache*

    Examples:

        If you want to get the page using request.get with caching do the following

        >>> url = "https://www.example.com"
        >>> page = get_page_from_url(url, cache_directory="cache_test")

        >>> soup = BeautifulSoup(page.text, 'lxml')
        >>> body_text = re.sub('\s+', ' ', soup.body.text)
        >>> print(body_text)
        ' Example Domain This domain is established to be used for illustrative examples in ' \
        'documents. You may use this domain in examples without prior coordination or asking for ' \
        'permission. More information... '

        At this point also a directory *cache_test* has been create with a cache file name
        with the name *get_page_from_url_https_www_example_com_.pkl*

        If you only want to read existing cache (in case it was written before) but do not want
        to write new cache, add the *max_cache_dir_size=0* argument

        >>> page = get_page_from_url(url, cache_directory="cache_test", max_cache_dir_size=0)

    """

    if skip_cache:
        logger.debug("Run function without caching")

    logger.debug(f"Cache directory is set to {cache_directory}")

    if max_cache_dir_size:
        logger.debug(f"A maximum cache dir of  {max_cache_dir_size} Mb is defined")

    try:
        if session is None:
            page = requests.get(url, timeout=timeout, headers=headers, verify=verify,
                                allow_redirects=True)
        else:
            page = session.get(url, timeout=timeout, headers=headers, verify=verify,
                               allow_redirects=True)
    except (ConnectionError, ReadTimeout, TooManyRedirects,
            ContentDecodingError, InvalidURL, UnicodeError, ChunkedEncodingError,
            SSLError, OpenSSLError) as err:
        logger.warning(err)
        page = None
        if raise_exceptions:
            raise err
    except Exception as err:
        # does is actually not allowed, but I want to make it more rebust Just catch all
        logger.warning(err)
        page = None
        if raise_exceptions:
            raise err
    return page


def requests_retry_session(retries=1, backoff_factor=0.3, status_forcelist=(500, 502, 503, 504),
                           session=None):
    """
    Do request with retry

    Parameters
    ----------
    retries: int
        Number of retryres
    backoff_factor
    status_forcelist
    session: object

    Returns
    -------
    requests.Session
        session linkk

    """

    session = session or requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
        method_whitelist=frozenset(['GET', 'POST'])
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)

    return session


def is_url(url):
    """ Check if *url* is valid """
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False
