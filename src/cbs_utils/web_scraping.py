"""
A collection of classes and utilities to assist with web scraping
"""
import re
import os
import logging
import pickle
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from requests.exceptions import ConnectionError, ReadTimeout, TooManyRedirects

import requests
from cbs_utils.misc import (make_directory, get_dir_size)

logger = logging.getLogger(__name__)


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

    def __init__(self, url, search_strings: dict,
                 store_page_to_cache=False, timeout=1.0, max_iterations=10,
                 max_cache_dir_size=None, skip_write_new_cache=False
                 ):

        self.store_page_to_cache = store_page_to_cache
        self.max_cache_dir_size = max_cache_dir_size
        self.skip_write_new_cache = skip_write_new_cache

        if not url.startswith('http://') and not url.startswith('https://'):
            self.url = 'http://{:s}/'.format(url)
        else:
            self.url = url

        self.max_iterations = max_iterations
        self.timeout = timeout
        self.session = requests.Session()

        self.search_regexp = dict()
        for key, regexp in search_strings.items():
            # store the compiled regular expressions in a dictionary 
            self.search_regexp[key] = re.compile(regexp)

        # results are stored in these attributes
        self.exists = False
        self.matches = dict()
        for key in self.search_regexp.keys():
            self.matches[key] = list()
            
        self.number_of_iterations = 0

        # start the recursive search
        self.recursive_pattern_search(self.url)

    def recursive_pattern_search(self, url):
        """
        Search the 'url'  for the patterns and continue of links to other pages are present
        """

        self.number_of_iterations += 1
        soup = self.make_soup(url)

        if soup:
            
            # first do all the searches defined in the search_strings dictionary
            for key, regexp in self.search_regexp.items():
                result = self.get_patterns(soup, regexp)
                # extend the total results with the current result
                self.matches[key].extend(result)

            # next, see if there are any frames. If so, retrieve the *src* reference and recursively
            # search again calling this routine
            frames = soup.find_all('frame')
            for frame in frames:
                src = frame.get('src')
                url = urljoin(url, src)
                
                if self.number_of_iterations <= self.max_iterations:
                    logger.debug(f"Recursive call to pattern search with {url}")
                    self.recursive_pattern_search(url)
                else:
                    logger.warning(
                        "Maximum number of {} iterations reached. Quiting"
                        "".format(self.max_iterations))
        else:
            logger.debug(f"No soup retrieved from {url}")

    def make_soup(self, url):
        """ Get the beautiful soup of the page *url*"""

        soup = None
        try:
            if self.store_page_to_cache:
                logger.debug("Get (cached) page: {}".format(url))
                page = get_page_from_url(url, timeout=self.timeout,
                                         max_cache_dir_size=self.max_cache_dir_size)
            else:
                logger.debug("Get page: {}".format(url))
                page = self.session.get(url, timeout=self.timeout)
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

        string = "Matches in {}\n".format(self.url)
        for key, matches in self.matches.items():
            string += "{} : ".format(key)
            string += "{}".format(matches)
            string += "\n"

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
    and only new cache is written if the size of the directory in Mb is smaller than the defined
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

        cache_file = '{}{}.pkl'.format(func.__name__, args).replace('/', '_')
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
        except IOError:
            result = func(*args, **kwargs)
            if not skip_write_new_cache:
                with open(cache, 'wb') as f:
                    pickle.dump(result, f)
            return result

    return wrapper


@cache_to_disk
def get_page_from_url(url, timeout=1.0, skip_cache=False, raise_exceptions=False,
                      max_cache_dir_size=None):
    """

    Parameters
    ----------
    url: str
        String met the url om op te halen
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
        page = requests.get(url, timeout=timeout)
    except (ConnectionError, ReadTimeout, TooManyRedirects) as err:
        logger.warning(err)
        page = None
        if raise_exceptions:
            raise err
    return page
