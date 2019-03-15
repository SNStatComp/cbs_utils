"""
A collection of classes and utilities to assist with web scraping
"""

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
