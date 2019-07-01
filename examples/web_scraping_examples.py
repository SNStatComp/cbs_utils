import logging
from pathlib import Path

from bs4 import BeautifulSoup

from cbs_utils.misc import (create_logger, merge_loggers, Timer)
from cbs_utils.regular_expressions import (KVK_REGEXP, ZIP_REGEXP, BTW_REGEXP)
from cbs_utils.web_scraping import (get_page_from_url, UrlSearchStrings)

# set up logging
log_level = logging.DEBUG  # change to DEBUG for more info
log_format = logging.Formatter('%(levelname)8s --- %(message)s (%(filename)s:%(lineno)s)')
logger = create_logger(console_log_level=log_level, formatter=log_format)
merge_loggers(logger, "cbs_utils.web_scraping", logger_level_to_merge=logging.INFO)

# create url name and clean previous cache file
cache_directory = Path("tmp")
clean_cache = True
if clean_cache:
    for item in cache_directory.iterdir():
        item.unlink()
    cache_directory.rmdir()
url = "https://www.example.com"

# first read: read from the url and report time
with Timer(units="s") as timer:
    page = get_page_from_url(url, cache_directory=cache_directory)
logger.info(f"Scraping from url took: {timer.duration} {timer.units}")

# show body
soup = BeautifulSoup(page.text, 'lxml')
logger.info("\n{}\n".format(soup.body))

# second read: from cache
with Timer("From Cache", units="ms") as timer:
    page = get_page_from_url("https://www.example.com", cache_directory=cache_directory)
logger.info(f"Scraping from cache took: {timer.duration} {timer.units}")

searches = dict(
    postcode=ZIP_REGEXP,
    kvknumber=KVK_REGEXP,
    btwnumber=BTW_REGEXP,
)

url = "www.be-one.nl"
with Timer(units="s") as timer:
    url_analyse = UrlSearchStrings(url, search_strings=searches, cache_directory=cache_directory,
                                   store_page_to_cache=True)
logger.info(f"Scraping from url took: {timer.duration} {timer.units}")
logger.info(url_analyse)

with Timer(units="s") as timer:
    url_analyse = UrlSearchStrings(url, search_strings=searches, cache_directory=cache_directory,
                                   store_page_to_cache=True,
                                   schema=url_analyse.schema,
                                   ssl_valid=url_analyse.ssl_valid,
                                   validate_url=False
                                   )
logger.info(url_analyse)
logger.info(f"Scraping from cache took: {timer.duration} {timer.units}")

# now give a list of order to scrape
with Timer(units="s") as timer:
    url_analyse = UrlSearchStrings(url, search_strings=searches, cache_directory=cache_directory,
                                   store_page_to_cache=True,
                                   schema=url_analyse.schema,
                                   ssl_valid=url_analyse.ssl_valid,
                                   validate_url=False,
                                   sort_order_hrefs=[
                                        "about",
                                        "over",
                                        "contact",
                                        "privacy",
                                        "algeme",
                                        "voorwaarden",
                                        "klanten",
                                        "customer",
                                   ],
                                   stop_search_on_found_keys=["btwnumber"]
                                   )
logger.info(url_analyse)
logger.info(f"Scraping from cache took: {timer.duration} {timer.units}")
