"""
A collection of classes and utilities to assist with web scraping
"""
import re
import os
import pandas as pd
import tldextract
import collections
import logging
import pickle
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from requests.exceptions import (ConnectionError, ReadTimeout, TooManyRedirects, MissingSchema,
                                 InvalidSchema, SSLError, RetryError, InvalidURL)
from urllib3.exceptions import MaxRetryError

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
from cbs_utils.misc import (make_directory, get_dir_size)

HREF_KEY = "href"
URL_KEY = "url"
EXTERNAL_KEY = "external_url"
RELATIVE_KEY = "relative_href"
RANKING_KEY = "ranking_href"
CLICKS_KEY = "clicks"

# examples of the btw code ar
# NL001234567B01, so always starting with NL, 9 digits, a B, and then 2 digits
# the problem is that sometime companies add dots in the btw code, such as
# NL8019.96.028.B.01
# the following regular expressions allows to have 0 or 1 dot after each digit
BTW_REGEXP = r"\bNL([\d][\.]{0,1}){9}B[\.]{0,1}([\d][\.]{0,1}){1}\d\b"
# KVK_REGEXP = r"\b([\d][\.]{0,1}){7}\d\b"  # 8 digits. may contain dots, not at the end
# this regular expression replaces the \b word boundaries of the previous version with the part
# ((?![-\w])|(\s^)), because the word boundary also matchs a hyphen, which means that -232 also
# is allowed. This give many hits for the kvk which are not kvk numbers but just a part of the
# coding. In order to exclude the hyphen , I have replaced it with the new version
KVK_REGEXP = r"((?![-\w])|(\s|^))([\d][\.]{0,1}){7}\d((?![-\w])|(\s|^))"
# 12345678 -> match
# A-12345678 -> no match
# A12345678 -> no match
ZIP_REGEXP = r"\d{4}\s{0,1}[A-Z]{2}"  # 4 digits and 2 capitals, 0 or 1 spaces: 1234AB or 1234 AB

logger = logging.getLogger(__name__)


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

    def __init__(self, href, url, valid_extensions=None, max_depth=1,
                 ranking_score=None, branch_count=None, max_branch_count=50,
                 tld_ext=None):
        self.href = href
        self.url = url
        self.branch_count = branch_count
        self.max_branch_count = max_branch_count

        self.url_extract = tldextract.extract(url)
        self.href_extract = tldextract.extract(href)

        self.ssl_key = True
        self.connection_error = False
        self.invalid_scheme = False
        self.relative_link = False
        self.external_link = False

        self.max_depth = max_depth

        self.ranking_score = ranking_score
        # sort list based on the ranking score dict : {"regexp1": score1, "regexp2": score2}

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

        # all hrefs starting with a '/' or './' are relative to the root
        if href.startswith("/") or href.startswith("./"):
            # this link is relative to the root. Extend it
            self.full_href_url = urljoin(self.url, href)
            self.relative_link = True
        else:
            # this reference is already absolute
            href_url = href
            self.relative_link = False

            self.url_req = RequestUrl(href_url)

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

        href = self.href

        # skip special page references
        if href in ("#", "/"):
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
        href_rel_to_domain = re.sub(strip_url_schema(self.url), "", strip_url_schema(href))

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
                 status_forcelist: list = (500, 502, 503, 504)
                 ):

        self.url = None
        self.ssl = None
        self.ext = None
        self.connection_error = False
        self.ssl_invalid = False
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

        with self.session as ses:
            self.assign_protocol_to_url(url, ses)

        if self.url is not None:
            self.ssl = self.url.startswith("https://")
            self.ext = tldextract.extract(self.url)

    def assign_protocol_to_url(self, url, session):

        clean_url = strip_url_schema(url)
        protocols = ("https", "http")
        # the url provides does not have any protocol. Check if one of these match
        for pp in protocols:
            full_url = f'{pp}://{clean_url}/'
            full_url = re.sub(r"//$", "/", full_url)
            self.connection_error = False
            if pp == "http":
                self.verify = False
            try:
                # use allow redirect to prevent blocking from a site if they use a redirect
                logger.debug(f"Requesting {full_url}")
                req = session.head(full_url, timeout=self.timeout, allow_redirects=True)
            except SSLError as err:
                logger.debug(f"Failed request {full_url} due to SSL")
                self.ssl_invalid = True
            except (ConnectionError, ReadTimeout, MaxRetryError, RetryError, InvalidURL) as err:
                self.connection_error = True
                logger.debug(f"Failed request {full_url}: {err}")
            except Exception as err:
                self.connection_error = True
                logger.info(f"Failed request with unknown error {full_url}: {err}")
            else:
                self.status_code = req.status_code
                logger.debug(f"Success {full_url} with {self.status_code}")
                if self.status_code == 200:
                    self.url = full_url
                    # this protocol gives us a proper status, stop searching
                    break
                else:
                    logger.debug(f"Connection error {full_url} : {self.status_code}")

    def __str__(self):

        msgf = "{:20s}: {}\n"
        msg = msgf.format("URL", self.url)
        msg += msgf.format("SSL", self.ssl)
        msg += msgf.format("status_code", self.status_code)
        msg += msgf.format("connection error", self.connection_error)

        return msg


class UrlSearchStrings(object):
    """
    Class to set up a recursive search of string on web pages
            status_forcelist=[500, 502, 503, 504],
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
    max_iterations: int, optional
        Maximum recursion depth. Default = 10
    
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

    Let she we have a web site 'www.example.com' which contains framesets and we want to extract all
    the postcodes + kvk numbers. You can do

    >>> search = dict(postcode=r"\d{4}\s{0,1}[a-zA-Z]{2}", kvk=r"(\d{7,8})")
    >>> url_analyse = UrlSearchStrings(url, search_strings=search)

    The results are stored in the 'matches' attribute of the class. You can report all info using

    >>> print(url_analyse)

    ::

        Matches in http://www.example.com
        postcode : ['2414AB', '6432XU']
        kvk_nummer : ['89369787', '89369787', '10067106']

    You can access the zipcodes via the *matches* attribute as

    >>> postcodes = url_analyse.matches["postcode"]

    Note that the keys of the *matches* dictionary are the same as the keys we used for the search
    """

    def __init__(self, url,
                 search_strings: dict,
                 sort_order_hrefs: list = None,
                 stop_search_on_found_keys: list = None,
                 store_page_to_cache=False,
                 timeout=5.0,
                 max_frames=10,
                 max_hrefs=1000,
                 max_depth=2,
                 max_space_dummies=3,
                 max_branch_count=10,
                 max_cache_dir_size=None,
                 skip_write_new_cache=False,
                 scrape_url=False
                 ):

        self.store_page_to_cache = store_page_to_cache
        self.max_cache_dir_size = max_cache_dir_size
        self.skip_write_new_cache = skip_write_new_cache

        self.sort_order_hrefs = sort_order_hrefs
        self.stop_search_on_found_keys = stop_search_on_found_keys

        # this call checks if we need https or http to connect to the side
        if scrape_url:
            self.req = RequestUrl(url)
        else:
            self.req = None
        logger.debug(f"with scrape flag={scrape_url} got {self.req}")

        self.external_hrefs = list()
        self.followed_urls = list()

        self.max_frames = max_frames
        self.max_hrefs = max_hrefs
        self.max_depth = max_depth
        self.max_space_dummies = max_space_dummies
        self.max_branch_count = max_branch_count
        self.timeout = timeout
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/61.0.3163.100 Safari/537.36'}
        if scrape_url:
            self.session = requests.Session()
            self.session.headers.update(self.headers)
        else:
            self.session = None

        self.stop_with_scanning_this_url = False

        self.search_regexp = dict()
        for key, regexp in search_strings.items():
            # store the compiled regular expressions in a dictionary 
            self.search_regexp[key] = re.compile(regexp)

        # results are stored in these attributes
        self.exists = False
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
            if self.req.url is not None:
                # start the recursive search
                logger.debug(f"------------> Start searching {self.req.url}")
                self.recursive_pattern_search(self.req.url)
                logger.debug(f"------------> Done searching {self.req.url}")
            else:
                logger.debug(f"------------> Could not connect for {self.req.url}. Skipping")
        else:
            logger.debug(f"Scrape flag was false: skip scraping {url}")

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

        valid_urls = list()
        valid_hrefs = list()
        extern_href = list()
        relative = list()
        rankings = list()
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

            logger.debug(f"CHeching {href} because {ext.domain} not in externals")
            check = HRefCheck(href, url=self.req.url, branch_count=self.branch_count)

            if check.valid_href:
                valid_hrefs.append(href)
                valid_urls.append(check.full_href_url)
                if check.external_link:
                    extern_href.append(True)
                    if check.clean_href_url not in self.external_hrefs:
                        logger.debug(f"adding exteral linkedin href {check.clean_href_url}")
                        self.external_hrefs.append(check.clean_href_url)
                else:
                    logger.debug(f"href is internal {href}")
                    extern_href.append(False)

                if check.relative_link:
                    relative.append(True)
                else:
                    relative.append(False)

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
            for key in self.stop_search_on_found_keys:
                if self.matches[key]:
                    # we found a match for this key. Stop searching any href immediately
                    logger.debug(f"Found a match for {key}")
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
                logger.debug("Get (cached) page: {}".format(url))
                page = get_page_from_url(url,
                                         session=self.session,
                                         timeout=self.timeout,
                                         max_cache_dir_size=self.max_cache_dir_size,
                                         headers=self.headers)
            else:
                logger.debug("Get page: {}".format(url))
                page = self.session.get(url, timeout=self.timeout, verify=False,
                                        headers=self.headers)
        except (ConnectionError, ReadTimeout) as err:
            logger.warning(err)
        else:
            if page is None or page.status_code != 200:
                logger.warning(f"Page not found: {url}")
            else:
                self.exists = True
                soup = BeautifulSoup(page.text, 'lxml')

        return soup

    @staticmethod
    def get_patterns(soup, regexp: re.Pattern) -> list:
        """
        Retrieve all the pattern match in the soup obtained from the url with Beautifulsoup
        
        Parameters
        ----------
        soup: object:BeautifulSoup
            Return value of the beautiful soup of the page where we want to search
        regexp: re.Pattern
            Compiled regular expresion to find on this page

        Returns
        -------
        list:
            List of matches with the regular expression
        """

        matches = list()
        lines = soup.find_all(string=regexp)
        for line in lines:
            match = regexp.search(str(line))
            if bool(match):
                matches.append(match.group(0))

        return matches

    def __str__(self):
        """ Overload print method with some information """

        if self.req is not None:
            string = "Matches in {}\n".format(self.req.url)
            for key, matches in self.matches.items():
                string += "{} : ".format(key)
                string += "{}".format(matches)
                string += "\n"
        else:
            string = "No scrape was done as req is None"

        return string


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

    def wrapper(*args, **kwargs):

        skip_cache = kwargs.get("skip_cache", False)
        max_cache_dir_size = kwargs.get("max_cache_dir_size", None)
        if skip_cache:
            # in case the 'skip_cache' option was used, just return the result without caching
            return func(*args, **kwargs)

        cache_file = '{}{}'.format(func.__name__, args).replace("/", "_")
        cache_file = re.sub(r"[\"'():,.&%#$;\s]", "_", cache_file)
        cache_file = re.sub(r"[__]{1,}", "_", cache_file)
        cache_file += ".pkl"
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
                return pickle.load(f)
        except (FileNotFoundError, OSError):
            result = func(*args, **kwargs)
            if not skip_write_new_cache:
                try:
                    with open(cache, 'wb') as f:
                        pickle.dump(result, f)
                except OSError as err:
                    logger.warning(f"Cache write error:\n{err}")
            return result

    return wrapper


@cache_to_disk
def get_page_from_url(url, session=None, timeout=1.0, skip_cache=False, raise_exceptions=False,
                      max_cache_dir_size=None, headers=None):
    """

    Parameters
    ----------
    url: str
        String met the url om op te halen
    session: object:Session:
        A session can be passed in case you want to keep it open
    timeout: float
        Aantal second dat je het probeert
    skip_cache: bool
        If True, prevent that we are using the cache decorator
    skip_cache: bool
        If True, do not write new cache.
    raise_exceptions: bool
        If True, raise the expections of the requests
    max_cache_dir_size: int
        Maximum size of cache in Mb. Stop writing cache as soon max_cache has been reached. If None,
        this test is skip and the cache is always written. If 0, we never write cache and therefore
        the check of the current directory size can be skipped, which significantly speeds up the
        code
    headers: dict
        Headers to use for the request

    Returns
    -------
    request.Page:
        The html pagnia

    Notes
    -----
    * De 'cache_to_dist' decorator zorgt ervoor dat we de file ook kunnen cachen
    """

    if skip_cache:
        logger.debug("Run function without caching")

    if max_cache_dir_size:
        logger.debug(f"A maximum cache dir of  {max_cache_dir_size} Mb is defined")

    try:
        if session is None:
            page = requests.get(url, timeout=timeout, headers=headers)
        else:
            page = session.get(url, timeout=timeout, headers=headers)
    except (ConnectionError, ReadTimeout, TooManyRedirects) as err:
        logger.warning(err)
        page = None
        if raise_exceptions:
            raise err
    return page


def requests_retry_session(
        retries=1,
        backoff_factor=0.3,
        status_forcelist=(500, 502, 503, 504),
        session=None):
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
