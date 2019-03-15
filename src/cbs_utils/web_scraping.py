"""
A collection of classes and utilities to assist with web scraping
"""
import re
import logging
import pickle
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from requests.exceptions import ConnectionError, ReadTimeout

import requests
from cbs_utils.misc import make_directory

logger = logging.getLogger(__name__)


class UrlSearchStrings(object):
    """
    Class to set up a recursive search of string on web pages
    
    Parameters
    ----------
    url: str    
        Main url to start searching
    search_strings: dict
        Dictionary with the searches performed per page. The form is
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
    * This class takes care of a web page with frames. Normally, these are not analysed by 
      beautiful soup, however, by explicity looking up all frames and following the links defined
      by the 'src' tag, we can access all the frames in an url
    """

    def __init__(self, url, search_strings: dict,
                 store_page_to_cache=False, timeout=1.0, max_iterations=10):

        self.store_page_to_cache = store_page_to_cache
        self.search_strings = search_strings

        if not url.startswith('http://') and not url.startswith('https://'):
            self.url = 'http://{:s}/'.format(url)
        else:
            self.url = url

        self.max_iterations = max_iterations
        self.timeout = timeout
        self.session = requests.Session()

        self.search_regexp = dict()
        for key, regexp in self.search_strings.items(): 
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
            for key, regexpc in self.search_regexp.items():
                string = self.search_strings[key]
                logger.debug(f"Searching {key}:{string} on page {url}")
                result = self.get_patterns(soup, string, regexpc=regexpc)
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
                page = get_page_from_url(url, timeout=self.timeout)
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
    def get_patterns(soup, string: str, regexpc) -> list:
        """
        
        Parameters
        ----------
        soup: object:BeautifulSoup
            Return value of the beautiful soup of the page where we want to search
        string: str
            String regular expresion to find on this page
        regexpc: re.compiled
            Compiled regular expresion to find on this page

        Returns
        -------
        list:
            List of matches with the regular expression
        """
        
        matches = list()
        lines = soup.find_all(string=string)
        for line in lines:
            match = regexpc.search(str(line))
            if bool(match):
                grp = match.group(1)
                matches.append(grp)

        return matches


def cache_to_disk(func):
    """
    Decorator which allows to cache the output of a function to disk

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
    """

    def wrapper(*args, **kwargs):

        skip_cache = kwargs.get("skip_cache", False)
        if skip_cache:
            # in case the 'skip_cache' option was used, just return the result without caching
            return func(*args, **kwargs)

        cache_file = '{}{}.pkl'.format(func.__name__, args).replace('/', '_')
        cache_dir = Path(kwargs.get("cache_directory", "cache"))

        make_directory(cache_dir)
        cache = Path(cache_dir) / cache_file

        try:
            with open(cache, 'rb') as f:
                return pickle.load(f)
        except IOError:
            result = func(*args, **kwargs)
            with open(cache, 'wb') as f:
                pickle.dump(result, f)
            return result

    return wrapper


@cache_to_disk
def get_page_from_url(url, timeout=1.0, skip_cache=False):
    """

    Parameters
    ----------
    url: str
        String met the url om op te halen
    timeout: float
        Aantal second dat je het probeert
    skip_cache: bool
        If True, prevent that we are using the cache decorator

    Returns
    -------
    request.Page:
        The html pagnia

    Notes
    -----
    * De 'cache_to_dist' decorator zorgt ervoor dat we de file ook kunnen cachen
    """

    if skip_cache:
        logger.debug("Run fuction with caching")

    try:
        page = requests.get(url, timeout=timeout)
    except requests.exceptions.ConnectionError as err:
        page = None
    return page
