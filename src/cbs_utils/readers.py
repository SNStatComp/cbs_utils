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
                 code_key='code',
                 label_key='Label',
                 compression="zip"
                 ):
        # start with reading the excel data base
        self.code_key = code_key
        self.label_key = label_key
        self.cache_filetype = cache_filetype
        self.cache_filename = cache_filename + cache_filetype
        self.compression = compression
        self.level_names = ['Grp', 'L1', 'L2', 'L3', "L4"]

        self.info = None
        self.levels = list()
        self.data = None

        try:
            file_extension = os.path.splitext(self.cache_filename)[1][1:]
        except IndexError:
            file_extension = ""

        if compression and compression != file_extension:
            # in case we are compressing the data, add the extension if it was not there yet
            self.cache_filename += "." + compression

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

            01.1   Teelt van eenjarige gewassen
            01.11	Teelt van granen, peulvruchten en oliehoudende zaden
            01.13	Teelt van groenten en wortel- en knolgewassen an eenjarige gewassen
            01.13.1	Teelt van groenten in de volle grond
            01.13.2	Teelt van groenten onder glas
            :

            0.2     Bosbouw, exploitatie van bossen en dienstverlening voor de bosbouw

            :
            :

            B       Winning van delfstoffen

            6       Winning van aardolie en aardgas

            Note that the first digit are the main group, but that first number after the dot
            can have one digit for the first level, and in case there are two digits the second
            digits indicate the second level of the first group. The number after the second dot
            then give the third level. This means that the hierarchy of the list should be

            01     Landbouw, jacht en dienstverlening voor de landbouw en jacht

            01.1        Teelt van eenjarige gewassen
            01.1.1	        Teelt van granen, peulvruchten en oliehoudende zaden
            01.1.3	        Teelt van groenten en wortel- en knolgewassen an eenjarige gewassen
            01.1.3.1	        Teelt van groenten in de volle grond
            01.1.3.2	        Teelt van groenten onder glas

            02    Bosbouw, exploitatie van bossen en dienstverlening voor de bosbouw

            02.1        Bosbouw
            02.1.0          Bosbouw

            etc

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
                # where the code can have zero dots, one dot, or two dots. Use strip to remove
                # all the leading and trailing blancs
                digits = [v.strip() for v in code.split('.')]

                # always store the group character + the first digits of the code
                xls_df.ix[code, self.level_names[0]] = group_char

                # the fist ditit stored as the first level
                xls_df.ix[code, self.level_names[1]] = int(digits[0])

                if len(digits) > 1:
                    # in case we have at least two digits, also store the second level. See note
                    # above that we can have two levels in this number
                    if len(digits[1]) == 1:
                        # in case we have a single digit, append a zero
                        number = digits[1] + "0"
                    elif len(digits[1]) == 2:
                        number = digits[1]
                    else:
                        raise AssertionError("Should at max have two digits")

                    xls_df.ix[code, self.level_names[2]] = int(number[0])
                    xls_df.ix[code, self.level_names[3]] = int(number[1])

                if len(digits) > 2:
                    # in case we have at least three digits, also store the third level
                    xls_df.ix[code, self.level_names[4]] = int(digits[2])

        logger.debug("Turn all dicts into a multindex data frame")
        logger.debug(xls_df.head())

        # we have stored all the levels into the data frame.Reset the index
        xls_df = xls_df.reset_index()
        xls_df.rename(columns={"index": self.code_key}, inplace=True)

        # remove all the duplicated indices
        xls_df.drop_duplicates(self.level_names, keep="first", inplace=True)

        # make the level names the multi-index column of the main dataframe
        # and assign it to the *data* attribute of the class
        xls_df.set_index(self.level_names, inplace=True, drop=True)
        self.data = xls_df

        logger.info("Done")

    def create_group_per_level(self):
        """
        Loop over all the groups and create a dataframe per level. Not really used anymore

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

            # finally, remove the duplicated indices in this level (i.e. all the subgroups)
            level_df = level_df[~level_df.index.duplicated(keep="first")]

            # store the new selection in the levels list attribute.
            self.levels.append(level_df)

    def merge_groups(self, new_name, group_list):
        """
        Deprecated
        ----------
        Not used anymore, now use create_sbi_group

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

    def create_sbi_group(self,
                         group_name,
                         group_label=None,
                         indices=None,
                         level_0=None,
                         level_1=None,
                         level_2=None,
                         level_3=None,
                         level_4=None,
                         name_column_key="group_key",
                         label_column_key="group_label"):
        """
        Based on the first level 0, make mergers of a range of levels

        Parameters
        ----------
        group_name: str
            Column name added to the dataframe with the group key
        group_label: str or None
            Column name added to the dataframe with the group description
        level_0: list or str
            List of characters or single str for the first level sbi code  to include
        level_1: list or int
            List of integers or single int for the first digit level of sbi code. Default = None
        level_2: list or int
            List of integers or single int for the second digit level of sbi code. Default = None
        level_3: list or int
            List of integers or single int for the third digit level of sbi code. Default = None
        level_4: list or int
            List of integers or single int for the fourth digit level of sbi code. Default = None
        name_column_key: str
            Name of the column to store the group name. If it does not yet exist, create it
        label_column_key: str
            Name of the column to store the group label. If it does not yet exist, create it

        """

        # the pandas slicer for creating slices on the index
        ind_slice = pd.IndexSlice

        # create empty column to store the group name if it does not yet exist
        if name_column_key not in self.data.columns.values:
            self.data[name_column_key] = ""
        # create empty column to store the label name if it does not yet exist
        if label_column_key is not None and label_column_key not in self.data.columns.values:
            self.data[label_column_key] = ""

        levels = [level_0, level_1, level_2, level_3, level_4]
        if sum([bool(l) for l in levels]) == 0:
            # all the levels are None (therefore the sum is zero). Set levels to None
            levels = None

        if levels is not None:
            # store all the level list passed via the input argument into a single list

            # get all the levels of the level we want to make groups for.
            level_sets = [set(self.data.index.get_level_values(lvl)) for lvl in range(len(levels))]
            # loop over all the level passed via the input argument and  create a list of indices
            # for each level. In case a level is None, just add all the indicides of that level
            ind = list()
            for cnt, level in enumerate(levels):
                if level is None:
                    # the level is None, so add all the indices of this level
                    ind.append(level_sets[cnt])
                else:
                    if not isinstance(level, list):
                        # make sure the level is a list, even only one value is given
                        level = [level]
                    # add all the indices for this level that intersect with our input level values
                    ind.append(level_sets[cnt].intersection(set(level)))

            # create a index to slice the data frame with
            index = ind_slice[ind[0], ind[1], ind[2], ind[3], ind[4]]
        elif indices is not None:
            # not validated
            index = pd.MultiIndex.from_tuples(indices)
        else:

            index = self.get_index_from_string(group_name)

        # set all values of the name_column_key with the indices given by the levels to 'group_name'
        self.data.loc[index, name_column_key] = group_name

        # do the same for the label_column in case a group label has been passed via the input
        if group_label is not None:
            self.data.loc[index, label_column_key] = group_label

        # Done, now the data frame has labeled all the indices of sbi codes
        logger.debug("Done")

    def get_index_from_string(self, index_range):

        # first check if we did not give group characters
        match = re.match("^[A-Z]", index_range)
        if bool(match):
            # started with a alphanumerical character. Use the group_string branch
            return self.get_index_from_group_string(index_range)
        else:
            # started with a number. Use the numerical string branch
            return self.get_index_from_numerical_string(index_range)

    def get_index_from_group_string(self, index_range):
        """
        Get the indices from the data dataframe usig the alphanumeric selection string

        Parameters
        ----------
        index_range: str
            Alphanumeric selection, such as 'A' (returns indices of group A), 'AQ' (returns all
            indices of group A and Q), or 'A-C' (return indices from group A, B, and C

        Returns
        -------
        Index:
            Multiindex of all the items that belong to the group
        """

        # first check if we did not give group characters
        match = re.match("([A-Z])([-[A-Z]*]*)", index_range)
        assert match, "No match found at all for alphanumeric"

        fl = match.group(1)
        make_range = False
        try:
            el = match.group(2)
            # check if the next character is a dash. If so, make a range
            if re.match("^-", el):
                el = el[1:]
                make_range = True
        except IndexError:
            el = None

        ind = pd.IndexSlice

        if el is None:
            # only one char was given. Just return the indices for this character
            index = self.data.loc[ind[fl], :].index
        else:
            # two chars are given, so return the indices for a range
            if make_range:
                index = self.data.loc[ind[fl:el], :].index
            else:
                index = self.data.loc[ind[list(index_range)], :].index

        return index

    def get_index_from_numerical_string(self, index_range):
        """
        Get the indices from the data dataframe usig the nunerical selection string

        Parameters
        ----------
        index_range: str
            Numerical selection, such as '10' (returns indices of group 10), '10-12' (returns all
            indices of group 10, 11, 12) or more complex, such as 62.19-62.93.4 which returns all
            indices between 62.1.9 and 62.9.3.4

        Returns
        -------
        Index:
            Multiindex of all the items that belong to the group
        """

        match = re.match("([\d\.]+)([-[\d\.]*]*)", index_range)
        assert match, "No match found at all"

        sbi_code_start = match.group(1)

        ind = pd.IndexSlice

        ii = sbi_code_to_indices(sbi_code_start)

        sbi_code_end = match.group(2)
        if sbi_code_end != "":
            sbi_code_end = sbi_code_end[1:]
            jj = sbi_code_to_indices(sbi_code_end)
        else:
            jj = None

        if jj is None:
            if ii[4] is not None:
                index = self.data.loc[ind[:, ii[1], ii[2], ii[3], ii[4]], :].index
            elif ii[3] is not None:
                index = self.data.loc[ind[:, ii[1], ii[2], ii[3], :], :].index
            elif ii[2] is not None:
                index = self.data.loc[ind[:, ii[1], ii[2], :, :], :].index
            elif ii[1] is not None:
                index = self.data.loc[ind[:, ii[1], :, :, :], :].index
            else:
                raise AssertionError("Something is wrong here")
        else:
            # jj is defined as well. We need a range.
            index = self.data.loc[ind[:, ii[1]:jj[1]], :].index
            if ii[2] is not None and ii[2] > 0:
                indexi2 = self.data.loc[ind[:, ii[1], :ii[2] - 1], :].index
                index = index.difference(indexi2)
            if ii[3] is not None and ii[3] > 0:
                index3 = self.data.loc[ind[:, ii[1], ii[2], :ii[3] - 1], :].index
                index = index.difference(index3)
            if ii[4] is not None and ii[4] > 0:
                index4 = self.data.loc[ind[:, ii[1], ii[2], :ii[3], :ii[4] - 1], :].index
                index = index.difference(index4)

            if jj[2] is not None:
                indexj2 = self.data.loc[ind[:, jj[1], jj[2] + 1:], :].index
                index = index.difference(indexj2)
            if jj[3] is not None:
                indexj3 = self.data.loc[ind[:, jj[1], jj[2], jj[3] + 1:], :].index
                index = index.difference(indexj3)
            if jj[4] is not None:
                indexj4 = self.data.loc[ind[:, jj[1], jj[2], jj[3], jj[4] + 1:], :].index
                index = index.difference(indexj4)

        return index

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
                             format="fixed",
                             complib=self.compression)
        elif self.cache_filetype == ".pkl":
            self.data.to_pickle(self.cache_filename, compression=self.compression)
        else:
            raise ValueError("Only implemented for hdf and pkl")

    def get_sbi_groups(self, code_array, name_column_key="Grp"):
        """
        Get all the sbi groups (i.e., A, B, etc.) belonging to the sbi code array

        Parameters
        ----------
        code_array: np.array
            Array with strings with all the sbi numbers stored as 4 or 5 character strings or
            byte-arrays. Examples of the elements: '72431', '2781'. The dots are not included.
        name_column_key: str
            The group names are assumed to be stored in this column. You have to use the
            *create_sbi_group* method to do this

        Notes
        -----
        * Each value in the code_array is a four or five character string; the first pair of digits
          refer to the main group of the sbi, the second pair of digits refer to the first and
          second sub groups of the sbi code, respectively, and the optional fifth digit refers to
          last subsub group of the sbi code.
        * Example: 6210 is main group 62, subgroup 1, subsubgroup 0. 74283, is main group 74,
          sub group 2, subsub group 8, and subsubsubgroup 3
        * For each code_str the row is obtained from the data dataframe as we have set the indices
          to the subgroups as multiindex. In the example above this is (74, 2, 8, 3).
        * Then the group string is obtained from the column *name_column_key*. The default refers
          to *Grp*, which the main group, A, B, etc. However, with the *create_sbi_group* we may
          have defined a new colunm in the dataframe in *new_column_key* which cotain a new ordering
          of group, such as the group '72-74', '28-30', etc. In that case, if we set the
          *name_column_key* parametr to this columns, and array of strings corresponding to these
          new groups is return

        Returns
        -------
        nd.array
            Array with all the sbi groups names
        """

        sbi_group = list()
        for code_str in code_array:
            try:
                code_str = code_str.decode()
            except AttributeError:
                # probably already a proper string
                pass
            # get the first two digits of the string
            main = int(code_str[0:2])

            # get the second pair of digits from the string. In case is does not exist, set 0
            try:
                second = int(code_str[2])
            except (IndexError, ValueError):
                second = 0
            try:
                third = int(code_str[3])
            except (IndexError, ValueError):
                third = 0
            try:
                fourth = int(code_str[4:])
            except (IndexError, ValueError):
                fourth = 0

            # store the digits as tuples in a list (example : (1, 2, 2, 4))
            sbi_group.append((main, second, third, fourth))

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
        sbi_group = data.loc[(mi), name_column_key]

        return sbi_group.values


def sbi_code_to_indices(code):
    """

    Turn a sbi code string into a index


    Parameters
    ----------
    code: str
        Sbi code string such as A10.1 (group A, level 10, sublevel 1), 92.19.2 (level 92, sublevel
        1, subsub level 9, subsubsub level 2. Note the nuber after the first dot is treated as
        2 digits, each for one sublelve.

    Returns
    -------
    list:
        List of 5 items, each for one sub level. Example the string A10.12.4 becomes
        (A, 10, 1, 2, 4). In case less sub level are given, the list if extended with None.

    """
    levels = list()

    match = re.match("([A-Z])", code)
    if bool(match):
        levels.append(match.group(1))
        code = code[1:]
    else:
        levels.append(None)

    if len(code) > 0:
        digits = [v.strip() for v in code.split('.')]

        levels.append(int(digits[0]))

        if len(digits) > 1:
            # in case we have at least two digits, also store the second level. See note
            # above that we can have two levels in this number
            if len(digits[1]) == 1:
                # in case we have a single digit, append a zero
                number = digits[1] + "0"
            elif len(digits[1]) == 2:
                number = digits[1]
            else:
                raise AssertionError("Should at max have two digits")

            levels.append(int(number[0]))
            levels.append(int(number[1]))

        if len(digits) > 2:
            # in case we have at least three digits, also store the third level
            levels.append(int(digits[2]))

    # fill up with None up to the forth level
    while len(levels) < 5:
        levels.append(None)

    return levels
