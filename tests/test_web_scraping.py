#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import os
from pathlib import Path
import re
from bs4 import BeautifulSoup

import sys
from pandas.util.testing import assert_frame_equal
from cbs_utils.web_scraping import (get_page_from_url, make_cache_file_name)
from numpy.testing import (assert_string_equal, assert_equal)

DATA_DIR = "data"

_logger = logging.getLogger(__name__)


def test_get_page_from_url():
    # name of the example xls file

    # name of the url we want to scrape
    url = "https://www.example.com"

    # set the cache directory name and the name of the cache file we expect for the url
    cache_file_name = make_cache_file_name("get_page_from_url_", (url, ))
    cache_dir = Path("cache_test")

    cache_file = cache_dir / cache_file_name

    if cache_file.exists():
        # for the first round we want to make sure to get the data from the url, so
        # remove the original cache file
        cache_file.unlink()
        cache_dir.rmdir()

    body_text_expect = \
        ' Example Domain This domain is established to be used for illustrative examples in ' \
        'documents. You may use this domain in examples without prior coordination or asking for ' \
        'permission. More information... '

    # get page from url
    page = get_page_from_url(url, cache_directory=cache_dir)

    # extract body text and clean up
    soup = BeautifulSoup(page.text, 'lxml')
    body_text = re.sub("[\n\s]+", " ", soup.body.text)

    # check if the body is equal to the string we expect
    assert_string_equal(body_text, body_text_expect)

    # now the cache file should exist
    if cache_file.exists():
        cache_file_is_generated = True
    else:
        cache_file_is_generated = False

    assert_equal(cache_file_is_generated, True)

    # get page from url, this time is should be obtained from the cache file
    page2 = get_page_from_url(url, cache_directory=cache_dir)

    # extract body text and clean up
    soup2 = BeautifulSoup(page2.text, 'lxml')
    body_text2 = re.sub("[\n\s]+", " ", soup2.body.text)

    # check if the body is equal to the string we expect
    assert_string_equal(body_text2, body_text_expect)

    # get page from url, now force to skip the use of the cache (so again get the url data)
    page3 = get_page_from_url(url, cache_directory=cache_dir, skip_cache=True)

    # extract body text and clean up
    soup3 = BeautifulSoup(page3.text, 'lxml')
    body_text3 = re.sub("[\n\s]+", " ", soup3.body.text)

    assert_string_equal(body_text3, body_text_expect)

    # get page from url, finally, read again with max_size to zero, so that we read
    # but do not write the cache in case we have a new url
    page4 = get_page_from_url(url, cache_directory=cache_dir, max_cache_dir_size=0)

    # extract body text and clean up
    soup4 = BeautifulSoup(page4.text, 'lxml')
    body_text4 = re.sub("[\n\s]+", " ", soup4.body.text)

    assert_string_equal(body_text4, body_text_expect)

    # we remove the cache file try again with max_cache_dir_size to zero. We should
    # now obtained the url again but do not write a new cache file
    cache_file.unlink()
    cache_dir.rmdir()
    page5 = get_page_from_url(url, cache_directory=cache_dir, max_cache_dir_size=0)

    # extract body text and clean up
    soup5 = BeautifulSoup(page5.text, 'lxml')
    body_text5 = re.sub("[\n\s]+", " ", soup5.body.text)

    assert_string_equal(body_text5, body_text_expect)

    # last check: set max cache a bit larger. Then the directory size is checked first.
    # If it is smaller than *max_cache_dir_size*  we will write the cache. Note the getting
    # the size of a directory takes a lot of time, so this is really slow. Prevent to use this
    # If you want to prevent to write new cache (but still want to read existing cache),
    # set the max_cache_dir_size to 0
    page6 = get_page_from_url(url, cache_directory=cache_dir, max_cache_dir_size=10)

    # extract body text and clean up
    soup6 = BeautifulSoup(page6.text, 'lxml')
    body_text6 = re.sub("[\n\s]+", " ", soup6.body.text)

    assert_string_equal(body_text6, body_text_expect)
