"""
A collection of utilities to read from several data formats
"""

import logging
import os
import re

import pandas as pd

logger = logging.getLogger(__name__)


class SbiInfo(object):
    """
    Class to read the sbi coding as stored in the excel data file found on the intranet

    Parameters
    ----------
    file_name: str
        Name of the excel file containing the Sbi codes
    cache_filename: str, optional
        Dump the data file to cache in order to improve reading time. Default = 'sbi_codes_df'
    cache_filetype: str, optional
        Type of the cache file. Default = '.pkl'
    reset_cache: bool, optional
        If true, force the reading of the original Excel file in stead of the cache
    code_key: str, optional
        Name of the column containing the full key of the sbi. Default = 'code'
    label_key: str, optional
        Name of the label with the sbi description. Default = 'Label'

    Notes
    -----
    * The SBI file can be downloaded from the intranet_ and is a excel file containing all the SBI
      codes

    Examples
    --------

    A minimal example of the loading of a SBI file is:

    >>> file_name = 'SBI 2008 versie 2018.xlsx'
    >>> sbi = SbiInfo(file_name=file_name)

    The Sbi code are now loaded to 'data' attribute as a multiindex Pandas data frame.
    To have a look at the data, use the standard Pandas tool:

    >>> sbi.data.info
    >>> print(sbi.data.head())

    The *merge_groups*  method allows to merge groups or list of sbi codes to a new group. For
    instance, to merge the groups D and E to a new group 'D-E' do:

    >>> sbi.merge_groups(new_name='D-E', group_list=['D', 'E'])

    Also, you can merge based on a list of sbi codes as defined in the *code* field of the 'data'
    attributes

    >>> sbi.merge_groups(new_name='IC', group_list=['26.11',  '26.12',  '46.51', '46.52'])

    The new groups can be found in the data attribute

    .. _intranet:
            http://cbsintranet/werkruimten/Standaard%20Bedrijfsindeling/Documenten/SBI%202008%20versie%202018%20xlsx.xlsx
    """

    def __init__(self,
                 file_name,
                 cache_filename='sbi_codes_df',
                 cache_filetype='.pkl',
                 dump_cache=False,
                 reset_cache=False,
                 code_key='code', label_key='Label',
                 ):
        # start with reading the excel data base
        self.code_key = code_key
        self.label_key = label_key
        self.cache_filetype = cache_filetype
        self.cache_filename = cache_filename + cache_filetype
        self.level_names = ['L0', 'L1', 'L2', 'L3']

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

        logger.debug('Done')

    def parse_sbi_excel_database(self, file_name):
        """
        The sbi excel data file needs to restructured to get a proper multi-index dataframe

        Notes
        -----

        * The sbi excel file can be downloaded from the intranet, but is also stored in the
          'data' directory of this module (SBI 2008 versie 2018.xlsx)
        * The excel file has two columns, the first with the SBI code, the second with the
          description. The SBI codes are grouped by alphanumeric char A, B, C, etc.::

            A       Landbouw, bosbouw en visserij

            01     Landbouw, jacht en dienstverlening voor de landbouw en jacht

            0.1.1   Teelt van eenjarige gewassen

            :

            0.2     Bosbouw, exploitatie van bossen en dienstverlening voor de bosbouw

            :
            :

            B       Winning van delfstoffen

            6       Winning van aardolie en aardgas

        * In this script, the format of the first column is used in create a proper
          hierarchy for the SBI levels
        * The alphanumeric chars is used for the first level, the codes with zero '.' are used
          for the second level, the codes with two dots are used to the third level etc
        * The multi-index pandas Data frame is stored the the *data* attribute of the class
        """

        # read the data file
        logger.info('Reading SBI data base {}'.format(file_name))
        xls_df = pd.read_excel(file_name)
        # set the index name 'code'
        # change the index name to 'code' (A, B, etc or xx.xx.xx) and the label
        self.info = xls_df.columns.values[0].strip()
        xls_df.rename(columns={xls_df.columns[0]: self.label_key}, inplace=True)
        xls_df.rename_axis(self.code_key, inplace=True)

        group_char = None

        # only if both the index and column contain a valid value this line can be processed.
        # To check this in one go, first change the index to a column, drop the lines with
        # at least one nan, and then convert the first column back to the index
        xls_df = xls_df.reset_index().dropna(axis=0, how="any")
        xls_df.set_index(self.code_key, drop=True, inplace=True)
        # make sure the index is a string, not int (which could happen for the codes without '.'
        xls_df.index = xls_df.index.values.astype(str)

        # create new columns to store the level values stored in *level_names* (L0, L1, L2, L3)
        for name in self.level_names:
            # use 0 for the non existing level, not nan, such that we can maintain integers (using
            # nan will convert the format to floats)
            xls_df[name] = 0

        # loop over all the rows in the data base and see if we can get the level values
        for code, label in xls_df.iterrows():
            is_level0 = re.match("^\s*[a-zA-Z]", code)
            if bool(is_level0):
                # this is a row with the main character, indicating we are entering a new group
                group_char = code.strip()
                xls_df.ix[code, self.level_names[0]] = group_char
            else:
                # we have entered the group, now we assume we are analyse the code xx.xx.xx
                # where the code can have zero dots, one dot, or two dots
                digits = [int(v) for v in code.split('.')]

                # always store the group character + the first digits of the code
                xls_df.ix[code, self.level_names[0]] = group_char
                xls_df.ix[code, self.level_names[1]] = digits[0]

                if len(digits) > 1:
                    # in case we have at least two digits, also store the second level
                    xls_df.ix[code, self.level_names[2]] = digits[1]
                if len(digits) > 2:
                    # in case we have at least three digits, also store the third level
                    xls_df.ix[code, self.level_names[3]] = digits[2]

        logger.debug("Turn all dicts into a multindex data frame")
        logger.debug(xls_df.head())

        # we have stored all the levels into the data frame.Reset the index
        xls_df = xls_df.reset_index()
        xls_df.rename(columns={"index": self.code_key}, inplace=True)

        # make the level names the multi-index column of the main dataframe
        # and assign it to the *data* attribute of the class
        xls_df.set_index(self.level_names, inplace=True, drop=True)
        self.data = xls_df

        logger.info("Done")

    def create_group_per_level(self):
        """
        Loop over all the groups and create a dataframe per level

        Notes
        -----
        * The full multi-index data is stored in the *data* attribute; this method stores the
          values per levels in  the  *levels*  attribute
        * The individuals levels can be retrieved from the list as levels[0], levels[1], etc.
        """

        # select the separate levels section based on the 0 values in the dataframe

        # the levels attribute will contain all the data frames per level
        self.levels = list()

        codes = self.data.reset_index()
        for cnt, name in enumerate(self.level_names[1:]):
            # create a mask for level N based on the 0 in the level N + 1
            mask = codes[name].values == 0

            # select the levels for level N (from 0 until the current level)
            if cnt == 0:
                # only for the level with th A/B etc, we include the letter in the index
                level_selection = self.level_names[:1]
            else:
                # for the other levels we don't include the letter as it indicate the same
                # as the first 2 digits and thus is double.
                level_selection = self.level_names[1:cnt + 1]

            # make a selection of columns we want into the dataframe. At least the levels
            # plus the code key (xx.xx) and the label key (with the description)
            column_selection = level_selection + [self.code_key, self.label_key]

            # select the data from the main data frame
            level_df = codes.ix[mask, column_selection]
            prev_level_name = self.level_names[cnt]
            level_df = level_df[level_df[prev_level_name] != 0]
            level_df.reset_index(inplace=True, drop=True)
            level_df.set_index(level_selection, inplace=True, drop=True)

            # store the new selection in the levels list attribute.
            self.levels.append(level_df)

    def merge_groups(self, new_name, group_list):
        """
        Merge two or more groups into a new group *new_name*

        Parameters
        ----------
        new_name: str
            Name of the new group group after merging
        group_list: list of strings
            List of group names we want to merge. The groups to be merged can be given by their
            alphanumeric character 'A', 'B', or by a list of codes such as '01', '1.1', '3.13' etc.
            The list must contains strings, so the codes have to be given with quotes
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

        logger.debug("Done")

    def read_from_cache(self):
        """
        Read from the cache file
        """

        logger.info("Reading SBI data from cache file {}".format(self.cache_filename))
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
        logger.info("Writing to cache file {}".format(self.cache_filename))
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
        Get all the sbi groups (i.e., A, B, etc.) belonging to the sbi code array

        Parameters
        ----------
        code_array: np.array
            Array with strings with all the sbi numbers stored as strings or byte-array.

        Notes
        -----
        * Each value in the code_array is a four or five character string; the first pair of digits
          refer to the main group of the sbi, the second pair of digits refer to the sub group of
          the sbi code, and the optional fifth digit refers to last subsub group of the sbi code

        Returns
        -------
        nd.array
            Array with all the sbi groups
        """

        sbi_group = list()
        for code_str in code_array:
            # get the first two digits of the string
            main = int(code_str[0:2])

            # get the second pair of digits from the string. In case is does not exist, set 0
            try:
                second = int(code_str[2:4])
            except (IndexError, ValueError):
                second = 0
            try:
                third = int(code_str[4:])
            except (IndexError, ValueError):
                third = 0

            # store the digits as tuples in a list (example : (1, 2, 0))
            sbi_group.append((main, second, third))

        # create a multiindex array with all the indices obtained from the sbi codes
        mi = pd.MultiIndex.from_tuples(sbi_group)

        # remove the first level of the sbi multindex data array which contains
        # the alphanumeric character (A, B,) adn set that a column
        data = self.data.reset_index().set_index(self.level_names[1:])

        # since the alphanumeric first level must be removed, the levels A,0,0,0 and B,0,0,0
        # referring to the main title of each group have the same index: 0,0,0. Therefore,
        # remove the duplicates and keep the first only.
        data.drop_duplicates(inplace=True)

        # now select all the indices using the multi-index. Note the sbi_group is as long as the
        # size of the input string array *code_array*
        sbi_group = data.loc[mi, self.level_names[0]]

        return sbi_group.values
