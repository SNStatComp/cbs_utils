"""
A collection of utilities to read from several data formats

* *StatLineTable*: class to read from Opendata.cbs.nl and store the table into a Pandas DataFrame
* *SbiInfo*: Class to read from a sbi Excel file and store all coding in a Pandas DataFrame

@Author: EVLT
"""

import collections
import json
import logging
import os
import re
import sqlite3
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

try:
    from tabulate import tabulate
except ImportError as err:
    logger.warning(err)


class DataProperties(object):
    """
    Class to hold the properties of an OpenData dataobject
    """

    def __init__(self, indicator_dict):
        self.id = indicator_dict.get("ID")
        self.position = indicator_dict.get("Position")
        self.parent_id = indicator_dict.get("ParentID")
        self.type = indicator_dict.get("Type")
        self.key = indicator_dict.get("Key")
        self.title = indicator_dict.get("Title")
        self.description = indicator_dict.get("Description")

        self.data_type = indicator_dict.get("Datatype")
        self.unit = indicator_dict.get("Unit")
        self.decimals = indicator_dict.get("Decimals")
        self.default = indicator_dict.get("Default")


class StatLineTable(object):
    """
    Read a statline table and save it as a Pandas dataframe

    Parameters
    ----------
    table_id: str
        ID of the table to read, e.g. '84408NED'. The table ID can be found in the URL of the
        corresponding opendata URL. In this example: `OpenData`_
    reset: bool
        In case opendata is read, all the files are written to cache. The next time you run the
        function, the data is read from cache, except when *reset* is True. In that case the
        data is read from OpenData again and the cache is refreshed
    cache_dir_name: str
        Name of the cache directory (default: "cache")
    max_levels: int
        Maximum number of levels to take into account (default: 5)
    to_sql: bool
        If True, store the generated table to sqlite. Each table is stored to a table inside
        a sqlite database. Default = False
    to_xls: bool
        If True, store to Excel. Each table is stored to a seperate tab. Default = False
    to_pickle: bool
        If True, store the tables to pickle. In case a picke file exist, not even the downloaded
        cache file are read, but the converted tables are directly obtained from the pickle files.
        Default = True
    write_questions_only: bool
        Only write the questions
    reset_pickles: bool
        By default, the opendata is stored to cache first and then converted from the json format
        to a proper DataFrame. This DataFrame is stored to cache in case *to_pickle* is set to
        True. In case a pickle file is found in the case, the DataFrame is directly obtained from
        the case (speeding up processing time). If you want to regenerate the picke file, set this
        flag to true (or just empty the cache)
    section_key: str
        Default column name to refer to a section. Default = "Section"
    title_key: str
        Default column name to refer to a section. Default = "Title"
    value_key:
        Default column name to refer to a section. Default = "Value"

    Attributes
    ----------
    question_df: pd.DataFrame
        All the questions per dimension
    section_df: pd.DataFrame
        The names of the sections
    dimension_df: pd.DataFrame
        The names of the dimensions

    Examples
    --------

    >>> stat_line = StatLineTable(table_id="84408NED", to_sql=True)

    This reads the stat line table '84408NED' and stores the results to a sqlite database

    The dataframes are accessible as:

    >>> stat_line.question_df.info()
    <class 'pandas.core.frame.DataFrame'>
    Int64Index: 8064 entries, 1 to 192
    Data columns (total 18 columns):
    L0                                   8064 non-null object
    L1                                   8064 non-null object
    L2                                   7308 non-null object
    L3                                   3444 non-null object
    L4                                   672 non-null object
    Section                              8064 non-null object
    ID                                   8064 non-null object
    ParentID                             8064 non-null object
    Key                                  8064 non-null object
    Title                                8064 non-null object
    Description                          6594 non-null object
    Datatype                             8064 non-null object
    Unit                                 8064 non-null object
    Decimals                             8064 non-null object
    Default                              8064 non-null object
    BedrijfstakkenBranchesSBI2008        8064 non-null object
    BedrijfstakkenBranchesSBI2008_Key    8064 non-null object
    Values                               8064 non-null int64
    dtypes: int64(1), object(17)
    memory usage: 1.2+ MB


    .. _OpenData:
        https://opendata.cbs.nl/statline/#/CBS/nl/dataset/84404NED/table?ts=1560412027927

    """

    def __init__(self, table_id, reset=False, cache_dir_name="cache", max_levels=5,
                 to_sql=False, to_xls=False, to_pickle=True, write_questions_only=False,
                 reset_pickles=False, section_key="Section", title_key="Title", value_key="Value"):

        self.table_id = table_id
        self.reset = reset
        self.max_levels = max_levels

        self.cache_dir = Path(cache_dir_name)
        self.cache_dir.mkdir(exist_ok=True)
        self.output_directory = self.cache_dir / Path(self.table_id)
        self.output_directory.mkdir(exist_ok=True)

        self.connection = None

        self.typed_data_set = None
        self.table_infos = None
        self.data_properties = None
        self.dimensions = collections.OrderedDict()

        self.section_key = section_key
        self.title_key = title_key
        self.value_key = value_key

        self.question_df: pd.DataFrame = None
        self.section_df: pd.DataFrame = None
        self.dimension_df: pd.DataFrame = None
        self.level_ids: collections.OrderedDict = None

        self.pickle_files = dict()
        self.df_labels = ["question", "section", "dimensions"]
        for label in self.df_labels:
            file_name = "_".join([self.table_id, label]) + ".pkl"
            self.pickle_files[label] = self.cache_dir / Path(file_name)

        updated_dfs = False
        if self.pickle_files["question"].exists() and not (reset_pickles or self.reset):
            self.pkl_data(mode="read")
        else:
            self.read_table_data()
            self.initialize_dataframes()
            self.fill_question_list()
            self.fill_data()
            updated_dfs = True

        if to_sql:
            self.write_sql_data(write_questions_only=write_questions_only)
        if to_xls:
            self.write_xls_data(write_questions_only=write_questions_only)
        if to_pickle and updated_dfs:
            self.pkl_data(mode="write")

    def pkl_data(self, mode="read"):
        """
        Write all the data to pickle

        Parameters
        ----------
        mode: {"read", "write")
            Option to control reading or writing
        """

        assert mode in ("read", "write")

        if mode == "read":
            action = "Reading from"
        else:
            action = "Writing to"

        for label, pkl_file in self.pickle_files.items():
            # write the result
            logger.info(f"{action} pickle database {pkl_file}")
            if mode == "read":
                if label == "question":
                    self.question_df = pd.read_pickle(pkl_file)
                elif label == "section":
                    self.section_df = pd.read_pickle(pkl_file)
                elif label == "dimensions":
                    self.dimension_df = pd.read_pickle(pkl_file)
                else:
                    raise AssertionError("label must be question, section, or dimension")
            else:
                if label == "question":
                    self.question_df.to_pickle(pkl_file)
                elif label == "section":
                    self.section_df.to_pickle(pkl_file)
                elif label == "dimensions":
                    self.dimension_df.to_pickle(pkl_file)
                else:
                    raise AssertionError("label must be question, section, or dimension")

    def write_xls_data(self, write_questions_only=True):

        """
        Write all the data to excel. Each table is written to a seperate sheet
        """
        xls = self.cache_dir / Path(self.table_id + ".xls")
        logger.info(f"Writing to excel database {xls}")
        with pd.ExcelWriter(xls) as stream:
            self.question_df.to_excel(stream, sheet_name="Questions")
            if not write_questions_only:
                self.section_df.to_excel(stream, sheet_name="Sections")
                self.dimension_df.to_excel(stream, sheet_name="Dimensions")

    def write_sql_data(self, write_questions_only=True):

        """
        Write all the data to the sql lite database. Each table is written in the same database
        """
        # write the result
        sqlite_db = self.cache_dir / "sqlite.db"
        self.connection = sqlite3.connect(sqlite_db)
        logger.info(f"Writing to sqlite database {sqlite_db}")
        self.question_df.to_sql("_".join([self.table_id, "question"]), self.connection,
                                if_exists="replace")
        if not write_questions_only:
            # also write the help dataframes
            self.section_df.to_sql("_".join([self.table_id, "section"]), self.connection,
                                   if_exists="replace")
            self.dimension_df.to_sql("_".join([self.table_id, "dimension"]), self.connection,
                                     if_exists="replace")

    def read_table_data(self):
        """
        Read the open data tables
        """

        type_data_set_file = self.output_directory / Path("TypedDataSet.json")
        table_infos_file = self.output_directory / Path("TableInfos.json")
        data_properties_file = self.output_directory / Path("DataProperties.json")

        if not data_properties_file.exists() or self.reset:
            logger.info(f"Importing table {self.table_id} and store to {self.output_directory}")
            # We cannot import the cbsodata module when using the debugger in PyCharm, therefore
            # only call import here
            import cbsodata
            cbsodata.get_data(self.table_id, dir=str(self.output_directory))

        # now we get the data from the json files which have been dumped by get_data
        logger.info(f"Reading json {data_properties_file}")
        with open(data_properties_file, "r") as stream:
            self.data_properties = json.load(stream)

        logger.info(f"Reading json {type_data_set_file}")
        with open(type_data_set_file, "r") as stream:
            self.typed_data_set = json.load(stream)
        logger.info(f"Reading json {table_infos_file}")
        with open(table_infos_file, "r") as stream:
            self.table_infos = json.load(stream)

    def initialize_dataframes(self):
        """
        Create empty data frame for the questions, sections and dimensions

        Notes
        -----
        * The json structure reflect the structure of the questionnaire , which has modules (L0),
          section (L1), subsection (L2), paragraphs (L3). In the json file these can be identified
          as GroupTopics.
        * In this script, the current level of the topics are kept track of, such that we can group
          items that belong to the same level
        """

        # level ids is going to contain the level id of the last seen level L0 (module),
        # section (L1), subsection (L2) and paragraph (L3)
        self.level_ids = collections.OrderedDict()
        level_labels = [f"L{level}" for level in range(self.max_levels)]
        for label in level_labels:
            # initialise all levels to None
            self.level_ids[label] = None

        # the questions dataframe will contain a column for each variable in the Topics + the label
        # for the levels + one extra column called 'Section' in which we store the multiline string
        # giving the Module/Section/Subsection/Paragraph
        question_columns = level_labels + ["Section"]
        section_columns = list()
        dimension_columns = list()
        n_dim = 0
        n_sec = 0
        n_quest = 0

        for indicator in self.data_properties:
            if indicator["Type"] == "TopicGroup":
                n_sec += 1
                keys = [_ for _ in list(indicator.keys()) if _ not in section_columns]
                section_columns.extend(keys)
            elif indicator["Type"] == "Dimension":
                n_dim += 1
                keys = [_ for _ in list(indicator.keys()) if _ not in dimension_columns]
                dimension_columns.extend(keys)
            else:
                n_quest += 1
                keys = [_ for _ in list(indicator.keys()) if _ not in question_columns]
                question_columns.extend(keys)

        # create all the data frames. The question_df contains the questions, the section_df
        # all the sections, and the dimensions all the dimensions
        self.question_df = pd.DataFrame(index=range(1, n_quest), columns=question_columns)
        self.section_df = pd.DataFrame(index=range(1, n_sec), columns=section_columns)
        self.dimension_df = pd.DataFrame(index=range(1, n_dim), columns=dimension_columns)

    def fill_question_list(self):
        """
        Turns the json data structures into a flat dataframe

        Notes
        -----
        * The questions are stored in modules, which again can be stored in sections and subsections
          This method keeps track of the level of the current question
        """

        # loop over all the data properties and store the questions, topic and dimensions
        for indicator in self.data_properties:
            data_props = DataProperties(indicator_dict=indicator)

            if data_props.parent_id is None:
                # if parent_id is None, we are entering a new module. Store the ID of this module
                # to L0 in levels _id
                logger.debug(f"Entering new module {data_props.title}")
                self.level_ids["L0"] = data_props.id
            else:
                # we have entered a module, so there is a parent. Store now the level of this
                # question
                found_parent = False
                for parent_level, (label, id) in enumerate(self.level_ids.items()):
                    # each topic has a field parent, which is the level to which the question
                    # belongs to. For instance, the first question belong to the module L0
                    # in case the parent_id as stored in this topic is equal to a previous stored
                    # level in the level_ids (id) it means that we have found the parent. Store
                    # this level to the higher level id (if the parent is in L0, the new level will
                    # be stored in L1 for instance)
                    this_level = parent_level + 1
                    if data_props.parent_id == id:
                        self.level_ids[f"L{this_level}"] = data_props.id
                        found_parent = True
                    elif found_parent and this_level < len(self.level_ids):
                        # we have found the parent, make sure that all the higher levels are set
                        # to None
                        self.level_ids[f"L{this_level}"] = None

            if data_props.type == "Dimension":
                # the current block is a dimension. Store it to the dimensions_df
                logger.debug(f"Reading dimension properties {data_props.key}")
                for key, value in indicator.items():
                    self.dimension_df.loc[data_props.id, key] = value
            elif data_props.type == "TopicGroup":
                # the current block is a TopicGroup (such as a Module or a Section. Store it to
                # the sections_df
                logger.debug(f"Reading topic group properties {data_props.key}")
                for key, value in indicator.items():
                    self.section_df.loc[data_props.id, key] = value
            else:
                # The current block mush be a question because it is not a dimension and not a
                # section

                # get the index in the question_df from the position property of this block
                index = int(data_props.position)

                # copy all the values from the current dict  to the data frame
                for key, value in indicator.items():
                    self.question_df.loc[index, key] = value

                section_title = None
                for level, level_id in self.level_ids.items():
                    self.question_df.loc[index, level] = level_id

        # we have looped over all the block. Clean up the dataframes

        # remove all empty rows and some unwanted columns
        self.question_df.dropna(axis=0, inplace=True, how="all")
        self.question_df.drop(["odata.type", "Type", "Position"], axis=1, inplace=True)
        self.dimension_df.dropna(axis=0, inplace=True, how="all")
        self.dimension_df.dropna(axis=1, inplace=True, how="all")

        # the dimensions dataframe contains the variables of the axis (such as 'Bedrijven'). Create
        # a column in the question_df dataframe per dimension
        for dimension_key in self.dimension_df["Key"]:
            self.question_df.loc[:, dimension_key] = None
            # the dimension name is retrieved here. Each dimension has its own json datafile which
            # contains more properties about this dimension, such as the Description. Read the
            # json data file here, such as e.g. 'Bedrijven.json' and store in the dimensions dict
            dimension_file = self.output_directory / Path(f"{dimension_key}.json")
            with open(dimension_file, "r") as stream:
                self.dimensions[dimension_key] = pd.DataFrame(json.load(stream)).set_index("Key")

        # the section df contains all the TopicGroups which we have encountered, such that we can
        # keep track of all the module and section titles. Clean the data frame here and set the
        # ID as an index
        self.section_df.dropna(axis=0, inplace=True, how="all")
        self.section_df.dropna(axis=1, inplace=True, how="all")
        self.section_df.set_index("ID", inplace=True, drop=True)
        self.section_df.drop(["odata.type", "Type", "Key"], axis=1, inplace=True)

        # Based on the the level id which we have stored in the L0, L1, L2, L3 column we are going
        # to build a complete description of the module/section/subsection leading to the current
        # question
        level_labels = list(self.level_ids.keys())
        for index, row in self.question_df.iterrows():
            level_ids = row[level_labels]
            section_title = None
            for lev_id in level_ids.values:
                # loop over all the L0, L1, L2, L3 values stored in this row. In case that the
                # level is equal to the row ID, it means we are dealing with the current question
                # so we can stop
                if lev_id == row["ID"]:
                    break
                # If we passed this, it means we got a level L0, L1 which is refering to a module/
                # section title. Look up the title belong to the stored ID from the section df
                # and append it
                if section_title is None:
                    section_title = self.section_df.loc[lev_id, self.title_key]
                else:
                    section_title += "\n" + self.section_df.loc[lev_id, self.title_key]

            # we have build a whole module/section/subsection title for this question. Store it
            # to the Section column
            self.question_df.loc[index, self.section_key] = section_title

        # finally, we can drop any empty column in case we have any to make it cleaning
        self.question_df.dropna(axis=1, inplace=True, how="all")

        logger.debug("Done reading data ")

    def fill_data(self):
        """

        Fill the question_df with the values found in the 'TypedDataSet'.

        Notes
        -----
        * We must have a questions_df filled by 'fill_question_list' already. Now
        * We loop over all the dimensions and store a new data frame for each dimension value.
        """

        df_list = list()
        for typed_data_set in self.typed_data_set:

            # loop over all the variables of the current block (belonging to one dimension value,
            # such as 'Bedrijven van 10 en groter'
            values = list()
            for key, data in typed_data_set.items():
                if key == "ID":
                    # the first value is always an ID, Make a copy of the question dataframe to
                    # a new data frame which we can fill with values for this dimension
                    logger.debug(f"Collecting data of {data}")
                    df = self.question_df.copy()
                elif key in list(self.dimensions.keys()):
                    # the next rows contain dimension properties. Get the values and store those
                    # in the dimension column of are question dataframe. Store both the Title
                    # and the short key
                    df.loc[:, key] = self.dimensions[key].loc[data, self.title_key]
                    df.loc[:, key + "_Key"] = data
                else:
                    # the rest of the rows in this block are the values belonging to the questions
                    # store them in a list
                    values.append(data)

            # now copy the whole list of values to our question data frame and add them to a list
            df.loc[:, "Values"] = values
            df_list.append(df)

        # we have create a dataframe for each dimension. Now append all the data frames to one
        # big one
        logger.info("Merging all the dataframes")
        self.question_df = pd.concat(df_list, axis=0)

    def describe(self):
        """
        Show some information of  the question dataframe
        """

        if self.question_df is not None:
            logger.info("\n{}".format(self.question_df.info()))
        else:
            logger.info("Data frame with question is empty")


class SbiInfo(object):
    """
    Class to read the sbi coding as stored in the excel data file found on the intranet which can
    subsequently be used to classify sbi codes into there groups

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
    compression: str
        Type of compression to use when writing the pickle file. Default is *zip*

    Attributes
    ----------
    data: pd.Dataframe
        DataFrame that get the sbi codes

    Notes
    -----
    * The SBI file can be downloaded from the intranet_ and is a excel file containing all the SBI
      codes
    * The main purpose of this class is to classify sbi codes obtained from a btw file into there
      approriate group. The sbi codes are normally given as 5 digit string, e.g. '64191'. With
      this class this can be directly related to group K.
    * Also new user defined groups can be made from series of sbi codes, such as 'Banken'

    Examples
    --------

    A minimal example of the loading of a SBI file is:

    >>> file_name = '../../data/SBI 2008 versie 2018.xlsx'
    >>> sbi = SbiInfo(file_name=file_name)

    The Sbi code are now loaded to *data* attribute as a multiindex Pandas data frame.
    To have a look at the data, use the standard Pandas tools, such as *head*:

    >>> print(tabulate(sbi.data.head(20), headers="keys", tablefmt="psql"))
    +-------------------+---------+--------------------------------------------------------------------------+
    |                   | code    | Label                                                                    |
    |-------------------+---------+--------------------------------------------------------------------------|
    | ('A', 0, 0, 0, 0) | A       | Landbouw, bosbouw en visserij                                            |
    | ('A', 1, 0, 0, 0) | 01      | Landbouw, jacht en dienstverlening voor de landbouw en jacht             |
    | ('A', 1, 1, 0, 0) | 01.1    | Teelt van eenjarige gewassen                                             |
    | ('A', 1, 1, 1, 0) | 01.11   | Teelt van granen, peulvruchten en oliehoudende zaden                     |
    | ('A', 1, 1, 3, 0) | 01.13   | Teelt van groenten en wortel- en knolgewassen                            |
    | ('A', 1, 1, 3, 1) | 01.13.1 | Teelt van groenten in de volle grond                                     |
    | ('A', 1, 1, 3, 2) | 01.13.2 | Teelt van groenten onder glas                                            |
    | ('A', 1, 1, 3, 3) | 01.13.3 | Teelt van paddenstoelen                                                  |
    | ('A', 1, 1, 3, 4) | 01.13.4 | Teelt van aardappels en overige wortel- en knolgewassen                  |
    | ('A', 1, 1, 6, 0) | 01.16   | Teelt van vezelgewassen                                                  |
    | ('A', 1, 1, 9, 0) | 01.19   | Teelt van overige eenjarige gewassen                                     |
    | ('A', 1, 1, 9, 1) | 01.19.1 | Teelt van snijbloemen en snijheesters in de volle grond                  |
    | ('A', 1, 1, 9, 2) | 01.19.2 | Teelt van snijbloemen en snijheesters onder glas                         |
    | ('A', 1, 1, 9, 3) | 01.19.3 | Teelt van voedergewassen                                                 |
    | ('A', 1, 1, 9, 9) | 01.19.9 | Teelt van overige eenjarige gewassen (rest)                              |
    | ('A', 1, 2, 0, 0) | 01.2    | Teelt van meerjarige gewassen                                            |
    | ('A', 1, 2, 1, 0) | 01.21   | Druiventeelt                                                             |
    | ('A', 1, 2, 4, 0) | 01.24   | Teelt van appels, peren, pruimen, kersen en andere pit- en steenvruchten |
    | ('A', 1, 2, 4, 1) | 01.24.1 | Teelt van appels en peren                                                |
    | ('A', 1, 2, 4, 2) | 01.24.2 | Teelt van steenvruchten                                                  |
    +-------------------+---------+--------------------------------------------------------------------------+


    It is now easy to get a group, e.g. "F"

    >>> sbi_F = sbi.data.loc["F"]
    >>> print(tabulate(sbi_F.head(5), headers="keys", tablefmt="psql"))
    +---------------+--------+---------------------------------------------------------------+
    |               | code   | Label                                                         |
    |---------------+--------+---------------------------------------------------------------|
    | (0, 0, 0, 0)  | F      | Bouwnijverheid                                                |
    | (41, 0, 0, 0) | 41     | Algemene burgerlijke en utiliteitsbouw en projectontwikkeling |
    | (41, 1, 0, 0) | 41.1   | Projectontwikkeling                                           |
    | (41, 2, 0, 0) | 41.2   | Algemene burgerlijke en utiliteitsbouw                        |
    | (42, 0, 0, 0) | 42     | Grond-, water- en wegenbouw (geen grondverzet)                |
    +---------------+--------+---------------------------------------------------------------+


    Or to get a group based on the second level, e.g. all 64 codes. Note that you need to use
    the slice method from pandas. Use the slice(None) on the first level in order to capture the
    all range, and slice(42,42) to get the 42 levels only


    >>> sbi_64 = sbi.data.loc[(slice(None), slice(64, 64)), :]
    >>> print(tabulate(sbi_64, headers="keys", tablefmt="psql"))
    +--------------------+---------+-----------------------------------------------------------------+
    |                    | code    | Label                                                           |
    |--------------------+---------+-----------------------------------------------------------------|
    | ('K', 64, 0, 0, 0) | 64      | Financiële instellingen (geen verzekeringen en pensioenfondsen) |
    | ('K', 64, 1, 0, 0) | 64.1    | Geldscheppende financiële instellingen                          |
    | ('K', 64, 1, 1, 0) | 64.11   | Centrale banken                                                 |
    | ('K', 64, 1, 9, 0) | 64.19   | Overige geldscheppende financiële instellingen                  |
    | ('K', 64, 1, 9, 1) | 64.19.1 | Coöperatief georganiseerde banken                               |
    | ('K', 64, 1, 9, 2) | 64.19.2 | Effectenkredietinstellingen                                     |
    | ('K', 64, 1, 9, 3) | 64.19.3 | Spaarbanken                                                     |
    | ('K', 64, 1, 9, 4) | 64.19.4 | Algemene banken                                                 |
    | ('K', 64, 2, 0, 0) | 64.2    | Financiële holdings                                             |
    | ('K', 64, 3, 0, 0) | 64.3    | Beleggingsinstellingen                                          |
    | ('K', 64, 3, 0, 1) | 64.30.1 | Beleggingsinstellingen in financiële activa                     |
    | ('K', 64, 3, 0, 2) | 64.30.2 | Beleggingsinstellingen in vaste activa                          |
    | ('K', 64, 3, 0, 3) | 64.30.3 | Beleggingsinstellingen met beperkte toetreding                  |
    | ('K', 64, 9, 0, 0) | 64.9    | Kredietverstrekking en overige financiële intermediatie         |
    | ('K', 64, 9, 1, 0) | 64.91   | Financiële lease                                                |
    | ('K', 64, 9, 2, 0) | 64.92   | Overige kredietverstrekking                                     |
    | ('K', 64, 9, 2, 1) | 64.92.1 | Hypotheekbanken en bouwfondsen                                  |
    | ('K', 64, 9, 2, 2) | 64.92.2 | Volkskredietbanken en commerciële financieringsmaatschappijen   |
    | ('K', 64, 9, 2, 3) | 64.92.3 | Participatiemaatschappijen                                      |
    | ('K', 64, 9, 2, 4) | 64.92.4 | Wisselmakelaars en overige kredietverstrekking                  |
    | ('K', 64, 9, 9, 0) | 64.99   | Overige financiële intermediatie                                |
    +--------------------+---------+-----------------------------------------------------------------+

    The *create_sbi_group* method can also be used to add a new group consisting of a range of
    sbi code which we can defined by a dash separated string. In order to specify this group, a
    new column *group_key* and *group_label* is created which we can use to extract the set of
    values.

    >>> sbi.create_sbi_group(group_name="64.19-64.92", group_label="Banken" )
    >>> sbi.create_sbi_group(group_name="66.12-66.19", group_label="Financiële advisering" )
    >>> banken = sbi.data[sbi.data["group_label"] == "Banken"]
    >>> verzekeringen = sbi.data[sbi.data["group_label"] == "Financiële advisering"]
    >>> sbi_new_group = pd.concat([banken, verzekeringen], axis=0)

    At this point we have created a group of sbi codes with 'Banken' and 'Financiele advisering'
    Now we change the order of the columns first and then print it to screen

    >>> cn = sbi_new_group.columns.values
    >>> sbi_new_group = sbi_new_group[[cn[0], cn[2], cn[3], cn[1]]]
    >>> print(tabulate(sbi_new_group, headers="keys", tablefmt="psql"))
    +--------------------+---------+-------------+-----------------------+---------------------------------------------------------------------------------------------------------------------------------------------------------+
    |                    | code    | group_key   | group_label           | Label                                                                                                                                                   |
    |--------------------+---------+-------------+-----------------------+---------------------------------------------------------------------------------------------------------------------------------------------------------|
    | ('K', 64, 1, 9, 0) | 64.19   | 64.19-64.92 | Banken                | Overige geldscheppende financiële instellingen                                                                                                          |
    | ('K', 64, 1, 9, 1) | 64.19.1 | 64.19-64.92 | Banken                | Coöperatief georganiseerde banken                                                                                                                       |
    | ('K', 64, 1, 9, 2) | 64.19.2 | 64.19-64.92 | Banken                | Effectenkredietinstellingen                                                                                                                             |
    | ('K', 64, 1, 9, 3) | 64.19.3 | 64.19-64.92 | Banken                | Spaarbanken                                                                                                                                             |
    | ('K', 64, 1, 9, 4) | 64.19.4 | 64.19-64.92 | Banken                | Algemene banken                                                                                                                                         |
    | ('K', 64, 2, 0, 0) | 64.2    | 64.19-64.92 | Banken                | Financiële holdings                                                                                                                                     |
    | ('K', 64, 3, 0, 0) | 64.3    | 64.19-64.92 | Banken                | Beleggingsinstellingen                                                                                                                                  |
    | ('K', 64, 3, 0, 1) | 64.30.1 | 64.19-64.92 | Banken                | Beleggingsinstellingen in financiële activa                                                                                                             |
    | ('K', 64, 3, 0, 2) | 64.30.2 | 64.19-64.92 | Banken                | Beleggingsinstellingen in vaste activa                                                                                                                  |
    | ('K', 64, 3, 0, 3) | 64.30.3 | 64.19-64.92 | Banken                | Beleggingsinstellingen met beperkte toetreding                                                                                                          |
    | ('K', 64, 9, 0, 0) | 64.9    | 64.19-64.92 | Banken                | Kredietverstrekking en overige financiële intermediatie                                                                                                 |
    | ('K', 64, 9, 1, 0) | 64.91   | 64.19-64.92 | Banken                | Financiële lease                                                                                                                                        |
    | ('K', 64, 9, 2, 0) | 64.92   | 64.19-64.92 | Banken                | Overige kredietverstrekking                                                                                                                             |
    | ('K', 64, 9, 2, 1) | 64.92.1 | 64.19-64.92 | Banken                | Hypotheekbanken en bouwfondsen                                                                                                                          |
    | ('K', 64, 9, 2, 2) | 64.92.2 | 64.19-64.92 | Banken                | Volkskredietbanken en commerciële financieringsmaatschappijen                                                                                           |
    | ('K', 64, 9, 2, 3) | 64.92.3 | 64.19-64.92 | Banken                | Participatiemaatschappijen                                                                                                                              |
    | ('K', 64, 9, 2, 4) | 64.92.4 | 64.19-64.92 | Banken                | Wisselmakelaars en overige kredietverstrekking                                                                                                          |
    | ('K', 66, 1, 2, 0) | 66.12   | 66.12-66.19 | Financiële advisering | Commissionairs en makelaars in effecten, beleggingsadviseurs e.d.                                                                                       |
    | ('K', 66, 1, 9, 0) | 66.19   | 66.12-66.19 | Financiële advisering | Administratiekantoren voor aandelen en obligaties, marketmakers, hypotheek- en kredietbemiddeling, geldwisselkantoren, bank- en spaaragentschappen e.d. |
    | ('K', 66, 1, 9, 1) | 66.19.1 | 66.12-66.19 | Financiële advisering | Administratiekantoren voor aandelen en obligaties                                                                                                       |
    | ('K', 66, 1, 9, 2) | 66.19.2 | 66.12-66.19 | Financiële advisering | Marketmakers                                                                                                                                            |
    | ('K', 66, 1, 9, 3) | 66.19.3 | 66.12-66.19 | Financiële advisering | Hypotheek- en kredietbemiddeling, geldwisselkantoren, bank- en spaaragentschappen e.d.                                                                  |
    +--------------------+---------+-------------+-----------------------+---------------------------------------------------------------------------------------------------------------------------------------------------------+

    It can be seen that a new *group_key* column is created clustering the given sbi code range,
    along with a *group_label* column containing the description. With our reodering we made sure that
    the *Label* column is again at the end

    The main purpose of the *SbiInfo* class is to convert series of SBI codes which are obtained
    from a data file into sbi class. Lets say we have a data frame with sbi codes which are stored
    as five digit elements

    >>> sbi_codes = ["64191", "6419", "6619"]

    A quick classification of the codes can now be obtained as

    >>> conv = sbi.get_sbi_groups(sbi_codes, columns=["code", "group_key", "group_label"])
    >>> for code, key, label in conv: print(f"sbicode {code} belongs to group {key} ({label})")
    sbicode 64.19.1 belongs to group 64.19-64.92 (Banken)
    sbicode 64.19 belongs to group 64.19-64.92 (Banken)
    sbicode 66.19 belongs to group 66.12-66.19 (Financiële advisering)

    The *merge_groups*  method allows to merge groups or list of sbi codes to a new group. For
    instance, to merge the groups D and E to a new group 'D-E' do:

    >>> sbi.merge_groups(new_name='D-E', group_list=['D', 'E'])


    Also, you can merge based on a list of sbi codes as defined in the *code* field of the 'data'
    attributes

    >>> sbi.merge_groups(new_name='IC', group_list=['26.11',  '26.12',  '46.51', '46.52'])

    The new groups can be found in the data attribute.

    The merge groups is now replaced by the *create_sbi_group* method, but kept for backward
    compatibility

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
        xls_df.rename(columns={xls_df.columns[0]: self.code_key, xls_df.columns[1]: self.label_key},
                      inplace=True)

        group_char = None

        # only if both the index and column contain a valid value this line can be processed.
        # To check this in one go, first change the index to a column, drop the lines with
        # at least one nan, and then convert the first column back to the index
        xls_df = xls_df.reset_index().dropna(axis=0, how="any")
        xls_df.set_index(self.code_key, drop=True, inplace=True)
        xls_df.drop("index", inplace=True, axis=1)
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
                xls_df.loc[code, self.level_names[0]] = group_char
            else:
                # we have entered the group, now we assume we are analyse the code xx.xx.xx
                # where the code can have zero dots, one dot, or two dots. Use strip to remove
                # all the leading and trailing blancs
                digits = [v.strip() for v in code.split('.')]

                # always store the group character + the first digits of the code
                xls_df.loc[code, self.level_names[0]] = group_char

                # the fist digit stored as the first level
                xls_df.loc[code, self.level_names[1]] = int(digits[0])

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

                    xls_df.loc[code, self.level_names[2]] = int(number[0])
                    xls_df.loc[code, self.level_names[3]] = int(number[1])

                if len(digits) > 2:
                    # in case we have at least three digits, also store the third level
                    xls_df.loc[code, self.level_names[4]] = int(digits[2])

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
            level_df = codes.loc[mask, column_selection]
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
        ..deprecated
        
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
        self.data.loc[mask, main_level_name] = new_name

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
        Get the indices from the data dataframe usig the numerical selection string

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

        inx = pd.IndexSlice

        ii = sbi_code_to_indices(sbi_code_start)

        sbi_code_end = match.group(2)
        if sbi_code_end != "":
            sbi_code_end = sbi_code_end[1:]
            jj = sbi_code_to_indices(sbi_code_end)
        else:
            jj = None

        if jj is None:
            if ii[4] is not None:
                index = self.data.loc[inx[:, ii[1], ii[2], ii[3], ii[4]], :].index
            elif ii[3] is not None:
                index = self.data.loc[inx[:, ii[1], ii[2], ii[3], :], :].index
            elif ii[2] is not None:
                index = self.data.loc[inx[:, ii[1], ii[2], :, :], :].index
            elif ii[1] is not None:
                index = self.data.loc[inx[:, ii[1], :, :, :], :].index
            else:
                raise AssertionError("Something is wrong here")
        else:
            # jj is defined as well. We need a range.
            index = self.data.loc[inx[:, ii[1]:jj[1]], :].index
            if ii[2] is not None and ii[2] > 0:
                indexi2 = self.data.loc[inx[:, ii[1], :ii[2] - 1], :].index
                index = index.difference(indexi2)
            if ii[3] is not None and ii[3] > 0:
                index3 = self.data.loc[inx[:, ii[1], ii[2], :ii[3] - 1], :].index
                index = index.difference(index3)
            if ii[4] is not None and ii[4] > 0:
                index4 = self.data.loc[inx[:, ii[1], ii[2], :ii[3], :ii[4] - 1], :].index
                index = index.difference(index4)

            if jj[2] is not None:
                indexj2 = self.data.loc[inx[:, jj[1], jj[2] + 1:], :].index
                index = index.difference(indexj2)
            if jj[3] is not None:
                indexj3 = self.data.loc[inx[:, jj[1], jj[2], jj[3] + 1:], :].index
                index = index.difference(indexj3)
            if jj[4] is not None:
                indexj4 = self.data.loc[inx[:, jj[1], jj[2], jj[3], jj[4] + 1:], :].index
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

    def get_sbi_groups(self, code_array, columns="Grp"):
        """
        Get all the sbi groups (i.e., A, B, etc.) belonging to the sbi code array

        Parameters
        ----------
        code_array: np.array
            Array with strings with all the sbi numbers stored as 4 or 5 character strings or
            byte-arrays. Examples of the elements: '72431', '2781'. The dots are not included.
        columns: str or list
            The group names are assumed to be stored in these columns. You have to use the
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
            try:
                main = int(code_str[0:2])
            except (IndexError, ValueError):
                main = 0

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
        original_order = list(range(len(sbi_group)))
        sbi_df = pd.DataFrame(original_order, index=mi, columns=["original_order"])
        sbi_df.index.names = self.level_names[1:]

        sbi_df_unique = sbi_df.sort_index()
        sbi_df_unique.reset_index(inplace=True)
        sbi_df_unique.drop_duplicates(subset=sbi_df.index.names, inplace=True)
        sbi_df_unique.set_index(self.level_names[1:], inplace=True)
        sbi_df_unique.sort_index(inplace=True)

        # remove the first level of the sbi multindex data array which contains
        # the alphanumeric character (A, B,) adn set that a column
        data = self.data.reset_index()
        not_a_main_sbi = data[self.level_names[1]] != 0
        data = data[not_a_main_sbi]
        data.set_index(self.level_names[1:], inplace=True)
        data = data.sort_index()
        data_sbi = data.reindex(sbi_df_unique.index)

        diff = data_sbi.index.difference(data.index)
        if diff.values.size > 0:
            logger.info("The following entries were missing in the sbi codes:\n"
                        "{}".format(diff.to_series().values))

        # now select all the indices using the multi-index. Note the sbi_group is as long as the
        # size of the input string array *code_array*
        codes = data_sbi.loc[sbi_group]

        sbi_groups = codes[columns]

        return sbi_groups.values


def sbi_code_to_indices(code):
    """

    Turn a sbi code string into a index


    Parameters
    ----------
    code: str
        Sbi code string such as A10.1 (group A, level 10, sublevel 1), 92.19.2 (level 92, sublevel
        1, subsub level 9, subsubsub level 2. Note the number after the first dot is treated as
        2 digits, each for one sublevel.

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
