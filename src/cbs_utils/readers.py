"""
A collection of utilities to read from several data formats
"""

import logging
import os
import re

import pandas as pd

_logger = logging.getLogger(__name__)


class SbiInfo(object):
    """
    Class to read the sbi coding as stored in the excel data file found on the intranet

    Parameters
    ----------
    file_name: str
        Name of the excel file containing the Sbi codes
    cache_filename: str, optional
        Dump the data file to cache in order to improve reading time. Default = "sbi_codes_df
    cache_filetype: str, optional
        Type of the cache file. Default = ".pkl"
    reset_cache: bool, optional
        If true, force the reading of the original Excel file in stead of the cache
    code_key: str, optional
        Name of the column containing the full key of the sbi. Default = "code"
    label_key: str, optional
        Name of the label with the sbi description. Default = "Label"

    Notes
    -----
    * The SBI file can be downloaded from the `intranet`_ and is a excel file containing all the SBI
      codes

    Examples
    --------

    A minimal example of the loading of a SBI file is:

    >>> file_name = "SBI 2008 versie 2018.xlsx"
    >>> sbi = SbiInfo(file_name=file_name)

    The Sbi code are now loaded to 'data' attribute as a multiindex Pandas data frame.
    To have a look at the data, use the standard Pandas tool:

    >>> sbi.data.info
    >>> print(sbi.data.head())

    The *merge_groups*  method allows to merge groups or list of sbi codes to a new group. For
    instance, to merge the groupd D and E to a new group 'D-E' do:

    >>> sbi.merge_groups(new_name="D-E", group_list=["D", "E"])

    Also, you can merge based on a list of sbi codes as defined in the *code* field of the "data"
    attributes

    >>> sbi.merge_groups(new_name="IC", group_list=["26.11",  "26.12",  "46.51", "46.52"])

    The new groups can be found in the data attribute

    _intranet::
        http://cbsintranet/werkruimten/Standaard%20Bedrijfsindeling/Documenten/SBI%202008%20versie%202018%20xlsx.xlsx
    """

    def __init__(self,
                 file_name,
                 cache_filename="sbi_codes_df",
                 cache_filetype=".pkl",
                 dump_cache=False,
                 reset_cache=False,
                 code_key="code", label_key="Label",
                 ):
        # start with reading the excel data base
        self.code_key = code_key
        self.label_key = label_key
        self.cache_filetype = cache_filetype
        self.cache_filename = cache_filename + cache_filetype
        self.level_names = ["L0", "L1", "L2", "L3"]

        self.info = None
        self.levels = list()
        self.data = None

        if not os.path.exists(self.cache_filename) or reset_cache:
            self.parse_sbi_excel_database(file_name)
            if dump_cache:
                self.write_to_cache_file()
        else:
            self.read_from_cache()

        self.create_group_per_level()

        _logger.debug("Done")

    def parse_sbi_excel_database(self, file_name):
        """
        The sbi excel data file needs to restructuring to get a proper multiindex dataframe
        """

        # read the data file
        _logger.info("Reading SBI data base {}".format(file_name))
        xls_df = pd.read_excel(file_name)
        # set the index name 'code'
        # change the index name to 'code' (A, B, etc or xx.xx.xx) and the label
        self.info = xls_df.columns.values[0].strip()
        xls_df.rename(columns={xls_df.columns[0]: self.label_key}, inplace=True)
        xls_df.rename_axis(self.code_key, inplace=True)

        group_char = None

        # only of both the index and column contain a valid value we can processes.
        # to check at the same time, first change the index to a column, then back
        xls_df = xls_df.reset_index().dropna(axis=0, how="any")
        xls_df.set_index(self.code_key, drop=True, inplace=True)
        # make sure the index is seen as a string, not int
        xls_df.index = xls_df.index.values.astype(str)

        # create new columns to store the level values (L0, L1, L2, L3
        for name in self.level_names:
            # use 0 for the non existing level
            xls_df[name] = 0

        # loop over all the rows in the data base and see if we can get the level values
        for code, label in xls_df.iterrows():
            _logger.debug("{} : {}".format(code, label))
            is_level0 = re.match("^\s*[a-zA-Z]", code)
            if bool(is_level0):
                # this is a row with the main character, indicating we are entering a new group
                _logger.debug("creating group {}".format(code))
                group_char = code.strip()
                xls_df.ix[code, self.level_names[0]] = group_char
            else:
                # we have entered the group, now we assume we are analyse the code xx.xx.xx
                # where the code can have zero dots, one dot, or two dots
                digits = [int(v) for v in code.split(".")]

                # allway store the group character + the first digits of the code
                xls_df.ix[code, self.level_names[0]] = group_char
                xls_df.ix[code, self.level_names[1]] = digits[0]

                if len(digits) > 1:
                    # in case we have at least two digits, also store the second level
                    xls_df.ix[code, self.level_names[2]] = digits[1]
                if len(digits) > 2:
                    # in case we have at least three digits, also store the third level
                    xls_df.ix[code, self.level_names[3]] = digits[2]

        _logger.debug("Turn all dicts into a multindex data frame")
        _logger.debug(xls_df.head())

        # we had stored all the levels into the data frame.Reset the index
        xls_df = xls_df.reset_index()
        xls_df.rename(columns={"index": self.code_key}, inplace=True)

        # make the level names the multi-index column of the main dataframe
        # and assign it to the codes attribute of the class
        xls_df.set_index(self.level_names, inplace=True, drop=True)
        self.data = xls_df

        _logger.info("Done")

    def create_group_per_level(self):
        """
        Loop over all the groups and create a grope per leve
        """

        # select the separate levels section based on the none values in the dataframe

        self.levels = list()
        codes = self.data.reset_index()
        for cnt, name in enumerate(self.level_names[1:]):
            # create a mask for level N based on the None in the level N + 1
            mask = codes[name].values == 0

            # select the levels for level N (from 0 until the current level)
            if cnt == 0:
                # only for the level with th A/B etc, we include the letter in the index
                level_selection = self.level_names[:1]
            else:
                # for the other levels we don't include the letter as it indicate the same
                # as the first 2 digits and thus is double.
                level_selection = self.level_names[1:cnt + 1]

            # make a selection of columns we want into the dataframe
            column_selection = level_selection + [self.code_key, self.label_key]

            # select the data from the main data frame
            level_df = codes.ix[mask, column_selection]
            prev_level_name = self.level_names[cnt]
            level_df = level_df[level_df[prev_level_name] != 0]
            level_df.reset_index(inplace=True, drop=True)
            level_df.set_index(level_selection, inplace=True, drop=True)

            # store the new selection in the levels list attribute
            self.levels.append(level_df)

    def merge_groups(self, new_name, group_list):
        """
        Merge two or more groups based on the first level

        Parameters
        ----------
        new_name: str
            Name of the new group group after merging
        group_list: list
            List of group names we want to merge
        """
        self.data.reset_index(inplace=True)

        # first make sure that the group list are strings

        if not isinstance(group_list[0], str):
            raise ValueError("Found a non string in the group to merge. Make sure only"
                             "to use strings: {}".format(group_list))

        main_level_name = self.level_names[0]

        if bool(re.search("[a-zA-Z]", group_list[0])):
            # in case the group list contain alphanumerical characters (A, B), use the first
            # index column name to replace the values
            # get the values of the column
            col = self.data[main_level_name].values
        else:
            col = self.data[self.code_key].values

        mask = [v in group_list for v in col]
        self.data.ix[mask, main_level_name] = new_name

        self.data.drop_duplicates(self.level_names, keep="first", inplace=True)

        # put back the columns as index
        self.data.set_index(self.level_names, inplace=True, drop=True)
        self.data.sort_index(inplace=True)

        _logger.debug("Done")

    def read_from_cache(self):
        """
        Read from the cache file
        """

        _logger.info("Reading SBI data from cache file {}".format(self.cache_filename))
        if self.cache_filetype == ".hdf5":
            self.data = pd.read_hdf(self.cache_filename)
        elif self.cache_filetype == ".pkl":
            self.data = pd.read_pickle(self.cache_filename)
        else:
            raise ValueError("Only implemented for hdf and pkl")

    def write_to_cache_file(self):
        """
        Writing to the cache file
        """
        _logger.info("Writing to cache file {}".format(self.cache_filename))
        if self.cache_filetype == ".hdf5":
            self.data.to_hdf(self.cache_filename,
                             key="sbi_codes",
                             mode="w", dropna=True,
                             format="fixed")
        elif self.cache_filetype == ".pkl":
            self.data.to_pickle(self.cache_filename)
        else:
            raise ValueError("Only implemented for hdf and pkl")

    def get_sbi_groups(self, code_array):
        """
        Get all the sbi groups belonging to the sbi code array

        Parameters
        ----------
        code_array: array
            String array with all the sbi numbers

        Returns
        -------
        nd.array
            Array with all the sbi groups
        """

        sbi_group = list()
        for code_str in code_array:
            main = int(code_str[0:2])
            subs = int(code_str[2:4])
            group = None
            # group = self.codes.ix[(main, subs,), self.level_names[0]].values[0]
            sbi_group.append(group)

        return sbi_group
