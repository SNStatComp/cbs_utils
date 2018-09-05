#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import pandas as pd
import logging
from pandas.util.testing import assert_frame_equal
from cbs_utils.misc import range1

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
_logger = logging.getLogger(__name__)

try:
    # this import is used when running python setup.py test or when running from within pycharm
    _logger.debug(sys.path)
    from cbs_utils.readers import SbiInfo
except ImportError:
    # if the import fails we are running this script from the command line and need to include the
    # current path
    real_path = os.path.realpath(os.path.join(os.path.dirname(__file__), "../src/cbs_utils"))
    sys.path.insert(0, real_path)
    _logger.debug("Import cbs_utils from {}".format(sys.path[0]))
    # the double mlab_mdfreader is needed in case we are running the script from the command line
    from cbs_utils.readers import SbiInfo

    sys.path.pop()

DATA_DIR = "data"
SBI_FILE = "SBI 2008 versie 2018.xlsx"


def write_data():
    """
    Write the data to a pickle file
    """

    data_location = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", DATA_DIR))

    sbi_file_name = os.path.join(data_location, SBI_FILE)

    sbi = SbiInfo(sbi_file_name)

    # the test file is stored in the same directory as the script
    test_file = os.path.splitext(os.path.join(os.path.dirname(__file__), SBI_FILE))[0] + ".pkl"
    _logger.info("Writing header object to {}".format(os.path.join(os.path.dirname(__file__),
                                                                   test_file)))
    sbi.data.to_pickle(test_file)


def test_sbi_info():
    # name of the example xls file
    data_location = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", DATA_DIR))
    sbi_file_name = os.path.join(data_location, SBI_FILE)

    # name of the pickle file which was stored to check if the data frame was read correctly
    test_file = os.path.splitext(os.path.join(os.path.dirname(__file__), SBI_FILE))[0] + ".pkl"

    # create the sbi object
    sbi = SbiInfo(sbi_file_name)

    # the sbi data frame
    sbi_df = sbi.data

    sbi_df_expected = pd.read_pickle(test_file)

    # see if the data frames are the same
    assert_frame_equal(sbi_df, sbi_df_expected)


def test_sbi_merge_groups():

    # name of the example xls file
    data_location = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", DATA_DIR))
    sbi_file_name = os.path.join(data_location, SBI_FILE)

    # name of the pickle file which was stored to check if the data frame was read correctly
    test_file = os.path.splitext(os.path.join(os.path.dirname(__file__), SBI_FILE))[0] + ".pkl"

    _logger.info(range1(10))
    _logger.info(range1(18,20))

    # create the sbi object
    sbi = SbiInfo(sbi_file_name)

    sbi.create_sbi_group(group_name="10-12", group_label="Voedings- en genotsmiddelenindustrie",
                         level_1=range1(10, 12))
    sbi.create_sbi_group(group_name="13-15", group_label="Textiel-, kleding-, en lederindustrie",
                         level_1=range1(13, 15))
    sbi.create_sbi_group(group_name="16-18", group_label="Hout-, papier- en grafische industrie",
                         level_1=range1(16, 18))
    sbi.create_sbi_group(group_name="20-28", group_label="20 and 28", level_1=list([20, 28]))
    sbi.create_sbi_group(group_name="A-B", group_label="A and B", level_0=list("AB"))

    sbi.create_sbi_group(group_name="Q", group_label="Q", level_0=list("Q"))
    sbi.create_sbi_group(group_name="64.19-64.92", group_label="Banken",
                         level_1=64, level_2=range1(2, 8), )
    sbi.create_sbi_group(group_name="64.19-64.92", group_label="Banken",
                         level_1=64, level_2=1, level_3=9)
    sbi.create_sbi_group(group_name="64.19-64.92", group_label="Banken",
                         level_1=64, level_2=9, level_3=range1(0, 2))
    pass


def main():
    if "--debug" in sys.argv:
        _logger.setLevel(logging.DEBUG)
    write_data()


if __name__ == "__main__":
    # in case we run the test_mdf_parser as a script from the command line like
    # python.exe tests/test_mdf_parser
    # we call the main routine which will call the routine to create the pkl data from the header.
    # This pickle data is used later by the 'test_header' unit test in order to see if we read the
    # header correctly
    test_sbi_merge_groups()
