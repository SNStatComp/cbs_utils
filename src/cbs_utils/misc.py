"""
Some miscellaneous functions used throughout many cbs modules
"""

import argparse
import errno
import logging
import os
import pathlib
import re
import subprocess
import sys
import time

import numpy as np
import pandas as pd

try:
    import dateutil.parser as dparser
except ImportError:
    print("Warning: dateutil could not be imported. Some functions may fail")
    dparser = None

try:
    import yaml
except ImportError:
    print("Warning: yaml could not be imported. Some functions may fail")
    yaml = None

try:
    import yamlloader
except ImportError:
    print("Warning: yamlordereddictloader could not be imported. Some functions may fail")
    yamlloader = None

try:
    from src import Q_
except ImportError:
    Q_ = None

MSG_FORMAT = "{:30s} : {}"


class Chdir(object):
    """Class which allows to move to a directory, do something, and move back when done

    Parameters
    ----------
    new_path: str
        Location where you want to do something

    Notes
    -----
    Used on the Gompute cluster in the batch processing script to submit a job inside a directory
    and then move back to the higher directory in order to move to the next case

    Examples
    --------

    Go to a known directory (C:/)

    >>> os.chdir("C:/")
    >>> os.getcwd()
    'C:\\\\'

    With the Chdir command we move to the C:/Temp directory where we can do something.

    >>> with Chdir("C:/Windows") as d:
    ...    # in this block we can do something in the directory Temp.
    ...    os.getcwd()
    'C:\\\\Windows'

    We have left the block under Chdir, so we are back at the directory where we started

    >>> os.getcwd()
    'C:\\\\'

    """

    def __init__(self, new_path):
        self.newPath = new_path

    def __enter__(self):
        self.savedPath = os.getcwd()
        os.chdir(self.newPath)
        return self

    def __exit__(self, *args):
        os.chdir(self.savedPath)


class Timer(object):
    """Class to measure the time it takes execute a section of code

    Parameters
    ----------
    message : str
        a string to use to the output line
    name : str, optional
        The name of the routine timed.
    verbose : bool, optional
        if True, produce output
    units : str, optional
        time units to use. Default  'ms'
    n_digits : int, optional
        number of decimals to add to the timer units

    Example
    -------

    Use a `with` / `as` construction to enclose the section of code which need to be timed

    >>> from numpy import allclose
    >>> number_of_seconds = 1.0
    >>> logger = create_logger(console_log_format_clean=True)
    >>> with Timer(units="s", n_digits=0) as timer:
    ...    time.sleep(number_of_seconds)
    Elapsed time         routine              :          1 s
    >>> allclose(number_of_seconds, timer.secs, rtol=0.1)
    True
    """

    def __init__(self, message="Elapsed time", name="routine", verbose=True, units='ms', n_digits=0,
                 field_width=20):
        self.logger = get_logger(__name__)
        self.verbose = verbose
        self.message = message
        self.name = name
        self.units = units
        self.secs = None

        # build the format string. E.g. for field_with=20 and n_digits=1 and units=ms, this produces
        # the following
        # "{:<20s} : {:<20s} {:>10.1f} ms"
        self.format_string = "{:<" + \
                             "{}".format(field_width) + \
                             "s}" + \
                             " {:<" + \
                             "{}".format(field_width) + \
                             "s} : {:>" + "{}.{}".format(10, n_digits) + \
                             "f}" + \
                             " {}".format(self.units)

    def __enter__(self):
        self.start = time.time()
        return self

    def __exit__(self, *args):
        self.end = time.time()

        # start and end are in seconds. Convert time delta to nano seconds
        self.delta_time = np.timedelta64(int(1e9 * (self.end - self.start)), 'ns')

        self.secs = float(self.delta_time / np.timedelta64(1, "s"))

        # debug output
        self.logger.debug("Found delta time in ns: {}".format(self.delta_time))

        if self.verbose:
            # convert the delta time to the desired units
            duration = self.delta_time / np.timedelta64(1, self.units)

            # produce output
            self.logger.info(self.format_string.format(self.message, self.name, duration,
                                                       self.units))


class ConditionalDecorator(object):
    """
    Add a decorator to a function only if the condition is True

    Parameters
    ----------
    dec: decorator
        The decorator which you want to add when condition is true
    condition: bool
        Only add the decorator if this condition is True
    """

    def __init__(self, dec, condition):
        self.decorator = dec
        self.condition = condition

    def __call__(self, func):
        if not self.condition:
            # Return the function unchanged, not decorated.
            return func
        return self.decorator(func)


class PackageInfo(object):
    """
    A class to analyse the version properties of this package

    Parameters
    ----------
    module_object: :obj:`Module`
        reference to the module for which want to to store the properties

    """

    def __init__(self, module_object):
        self.module_object = module_object

        self.package_version = None
        self.git_sha = None
        self.python_version = None
        self.build_date = None
        self.bundle_dir = None

        if getattr(sys, 'frozen', False):
            # we are running in a bundle
            self.get_bundle_version()
        else:
            self.get_source_version()

    def get_bundle_version(self):
        """
        Get the version of the current package from the _version_frozen module which was
        written by the build_executable script.
        """
        try:
            import _version_frozen
        except ImportError:
            print("Could not load _version_frozen. All stay None")
        else:
            print("here with bundle {}".format(_version_frozen))
            self.bundle_dir = sys._MEIPASS
            self.package_version = _version_frozen.VERSIONTAG
            self.git_sha = _version_frozen.GIT_SHA
            self.python_version = _version_frozen.PYTHON_VERSION
            self.build_date = _version_frozen.BUILD_DATE

    def get_source_version(self):
        """
        Get the version of the current package via the versioneer approach

        """
        # we are running in a normal Python environment
        self.bundle_dir = os.path.dirname(os.path.abspath(self.module_object.__file__))
        self.package_version = self.module_object.__version__
        self.git_sha = self.module_object.__git_sha_key__
        self.python_version = get_python_version_number(sys.version_info)
        self.build_date = pd.to_datetime("now").strftime("%Y%m%d")


def valid_date(s):
    """ Check if supplied data *s* is a valid date for the format Year-Month-Day

    Parameters
    ----------
    s : str
        A valid date in the form of YYYY-MM-DD, so first the year, then the month, then the day

    Returns
    -------
    :class:`datetime`
        Date object with with the  year, month, day obtained from the valid string representation

    Raises
    ------
    argparse.ArgumentTypeError:

    Notes
    -----
    This is a helper function for the argument parser module `argparse` which allows you to check
    if the argument passed on the command line is a valid date.

    Examples
    --------

    This is the direct usage of `valid_date` to see if the date supplied is of format YYYY-MM-DD

    >>> try:
    ...     date = valid_date("1973-11-12")
    ... except argparse.ArgumentTypeError:
    ...     print("This date is invalid")
    ... else:
    ...     print("This date is valid")
    This date is valid

    In case an invalid date is supplied

    >>> try:
    ...     date = valid_date("1973-15-12")
    ... except argparse.ArgumentTypeError:
    ...     print("This date is invalid")
    ... else:
    ...     print("This date is valid")
    This date is invalid


    Here it is demonstrated how to add a '--startdate' command line option to the argparse parser
    which checks if a valid date is supplied

    >>> parser = argparse.ArgumentParser()
    >>> p = parser.add_argument("--startdate",
    ...                         help="The Start Date - format YYYY-MM-DD ",
    ...                         required=True,
    ...                         type=valid_date)

    References
    ----------

    https://stackoverflow.com/questions/25470844/specify-format-for-input-arguments-argparse-python
    """

    try:
        return time.strptime(s, "%Y-%m-%d")
    except ValueError:
        msg = "Not a valid date: '{0}'.\nSupply date as YYYY-MM-DD".format(s)
        raise argparse.ArgumentTypeError(msg)


def get_path_depth(path_name):
    """
    Get the depth of a path or file name

    Parameters
    ----------
    path_name : str
        Path name to get the depth from

    Returns
    -------
    int
        depth of the path


    Examples
    --------

    >>> get_path_depth("C:\Anaconda")
    1
    >>> get_path_depth("C:\Anaconda\share")
    2
    >>> get_path_depth("C:\Anaconda\share\pywafo")
    3
    >>> get_path_depth(".\imaginary\path\subdir\share")
    4
    """

    if os.path.isfile(path_name) and os.path.exists(path_name):
        current_path = os.path.split(path_name)[0]
    else:
        current_path = path_name
    depth = 0
    previous_path = current_path
    while current_path not in ("", "."):
        current_path = os.path.split(current_path)[0]
        if current_path == previous_path:
            # for a full path name we end at the root 'C:\'. Detect that be comparing with the
            # previous round
            break
        previous_path = current_path
        depth += 1

    return depth


def scan_base_directory(walk_dir=".",
                        supplied_file_list=None,
                        file_has_string_pattern="",
                        file_has_not_string_pattern="",
                        dir_has_string_pattern="",
                        dir_has_not_string_pattern="",
                        start_date_time=None,
                        end_date_time=None,
                        time_zone=None,
                        time_stamp_year_first=True,
                        time_stamp_day_first=False,
                        extension=None,
                        max_depth=None,
                        sort_file_base_names=False
                        ):
    """Recursively scan the directory `walk_dir` and get all files underneath obeying the search
    strings and/or date/time ranges

    Parameters
    ----------
    walk_dir : str, optional
        The base directory to start the import. Default = "."
    supplied_file_list: list, optional
        In case walk dir is not given we can explicitly pass a file list to analyse. Default = None
    dir_has_string_pattern : str, optional
        Requires the directory name to have this pattern (Default value = ""). This selection is
        only made on the first directory level below the walk_dir
    dir_has_not_string_pattern : str, optional
        Requires the directory name NOT to have this pattern (Default value = ""). This selection is
        only made on the first directory level below the walk_dir
    file_has_string_pattern : str, optional
        Requires the file name to have this pattern (Default value = "", i.e. matches all)
    file_has_not_string_pattern : str, optional
        Requires the file name NOT to have this pattern (Default value = "")
    extension : str or None, optional
        Extension of the file to match. If None, also matches. Default = None
    max_depth : int, optional
        Sets a maximum depth to which the search is carried out. Default = None, which does not
        limit the search depth. For deep file structures setting a limit to the search depth speeds
        up the search.
    sort_file_base_names: bool, option
        If True, sort the resulting file list alphabetically based on the file base name.
        Default = False
    start_date_time: DateTime or None, optional
        If given, get the date time from the current file name and only add the files with a
        date/time equal or large the *start_date_time*. Default is None
    end_date_time: DateTime or None, optional
        If given, get the date time from the current file name and only add the files with a
        date/time smaller than the *end_date_time*. Default is None
    time_zone:str or None, optional
        If given add this time zone to the file stamp. The start and end time should also have a
        time zone
    time_stamp_year_first: bool, optional
        Passed to the datetime parser. If true, the year is first in the date/time string.
        Default = True
    time_stamp_day_first: bool, optional
        Passed to the datetime parser. If true, the day is first in the date/time string.
        Default = False

    Returns
    -------
    list
        All the  file names found below the input directory `walk_dir` obeying all the search
        strings

    Examples
    --------

    Find all the python files under the share directory in the Anaconda installation folder

    >>> scan_dir = "C:\\Anaconda\\share"
    >>> file_list = scan_base_directory(scan_dir, extension='.py')

    Find all the python files under the share directory in the Anaconda installation folder
    belonging to the pywafo directory

    >>> file_list = scan_base_directory(scan_dir, extension='.py', dir_has_string_pattern="wafo")

    Note that wafo matches on the directory 'pywafo', which is the first directory level below the
    scan directory. However, if we would match on '^wafo' the returned list would be empty as the
    directory has to *start* with wafo.

    In order to get all the files with "test" in the name with a directory depth smaller than 3 do

    >>> file_list = scan_base_directory(scan_dir, extension='.py', dir_has_string_pattern="wafo",
    ...                                 file_has_string_pattern="test", max_depth=3)


    Test the date/time boundaries. First create a file list from 28 sep 2017 00:00 to 5:00 with a
    hour interval and convert it to a string list

    >>> file_names = ["AMS_{}.mdf".format(dt.strftime("%y%m%dT%H%M%S")) for dt in
    ...    pd.date_range("20170928T000000", "20170928T030000", freq="30min")]
    >>> for file_name in file_names:
    ...     print(file_name)
    AMS_170928T000000.mdf
    AMS_170928T003000.mdf
    AMS_170928T010000.mdf
    AMS_170928T013000.mdf
    AMS_170928T020000.mdf
    AMS_170928T023000.mdf
    AMS_170928T030000.mdf

    Use the scan_base_directory to get the files within a specific date/time range

    >>> file_selection = scan_base_directory(supplied_file_list=file_names,
    ...  start_date_time="20170928T010000", end_date_time="20170928T023000")

    >>> for file_name in file_selection:
    ...     print(file_name)
    AMS_170928T010000.mdf
    AMS_170928T013000.mdf
    AMS_170928T020000.mdf

    Note that the selected range run from 1 am until 2 am; the end_date_time of 2.30 am is not
    included

    """

    log = get_logger(__name__)

    # get the regular expression for the has_pattern and has_not_pattern of the files and
    # directories
    file_has_string = get_regex_pattern(file_has_string_pattern)
    file_has_not_string = get_regex_pattern(file_has_not_string_pattern)
    dir_has_string = get_regex_pattern(dir_has_string_pattern)
    dir_has_not_string = get_regex_pattern(dir_has_not_string_pattern)
    log.debug(MSG_FORMAT.format("file_has_string", file_has_string))
    log.debug(MSG_FORMAT.format("file_has_not_string", file_has_not_string))
    log.debug(MSG_FORMAT.format("dir_has_string", dir_has_string))
    log.debug(MSG_FORMAT.format("dir_has_not_string", dir_has_not_string))

    # use os.walk to recursively walk over all the file and directories
    top_directory = True
    file_list = list()
    log.debug("Scanning directory {}".format(walk_dir))
    for root, subdirs, files in os.walk(walk_dir, topdown=True):

        if supplied_file_list is not None:
            root = "."
            subdirs[:] = list()
            files = supplied_file_list

        log.debug("root={}  sub={} files={}".format(root, subdirs, files))
        log.debug(MSG_FORMAT.format("root", root))
        log.debug(MSG_FORMAT.format("sub dirs", subdirs))
        log.debug(MSG_FORMAT.format("files", files))
        # get the relative path towards the top directory (walk_dir)
        relative_path = os.path.relpath(root, walk_dir)

        depth = get_path_depth(relative_path)

        if root == walk_dir:
            top_directory = True
        else:
            top_directory = False

        # base on the first directory list we are going to make selection of directories to
        # process
        if top_directory:
            include_dirs = list()
            for subdir in subdirs:
                add_dir = False
                if dir_has_string is None or bool(dir_has_string.search(subdir)):
                    add_dir = True
                if add_dir and dir_has_not_string is not None:
                    if bool(dir_has_not_string.search(subdir)):
                        add_dir = False
                if add_dir:
                    include_dirs.append(subdir)
                # overrule the subdirectory list of os.walk:
                # http://stackoverflow.com/questions/19859840/excluding-directories-in-os-walk
                log.debug("Overruling subdirs with {}".format(include_dirs))
                subdirs[:] = include_dirs

        for filename in files:

            (filebase, ext) = os.path.splitext(filename)
            if extension is None or extension == ext:

                add_file = False

                if file_has_string is None or bool(file_has_string.search(filebase)):
                    # if has_string is none, the search pattern was either empty or invalid (which
                    # happens during typing the regex in the edit_box). In this case, always add the
                    # file. If not none, filter on the regex, so only add the file if the search
                    # pattern is in the filename
                    add_file = True

                # do not add the file in case the has_not string edit has been set (!="") and if the
                # file contains the pattern
                if add_file and file_has_not_string is not None:
                    if bool(file_has_not_string.search(filebase)):
                        # in case we want to exclude the file, the has_not search pattern must be
                        # valid so may not be None
                        add_file = False

                if add_file and (start_date_time is not None or end_date_time is not None):
                    # we have supplied a start time or a end time. See if we can get a date time
                    # from the file name
                    file_time_stamp = get_time_stamp_from_string(
                        string_with_date_time=filebase, yearfirst=time_stamp_year_first,
                        dayfirst=time_stamp_day_first, timezone=time_zone)

                    if file_time_stamp is not None:
                        # we found a file time stamp. Compare it with the start time
                        if start_date_time is not None:
                            if isinstance(start_date_time, str):
                                # in case the start time was supplied as a string
                                start_date_time = get_time_stamp_from_string(
                                    string_with_date_time=start_date_time,
                                    yearfirst=time_stamp_year_first,
                                    dayfirst=time_stamp_day_first, timezone=time_zone)

                            if file_time_stamp < start_date_time:
                                # the file time stamp is smaller, so don't add it
                                add_file = False
                        # if a end time is supplied. Also compare it with the end time
                        if end_date_time is not None:
                            if isinstance(end_date_time, str):
                                end_date_time = get_time_stamp_from_string(
                                    string_with_date_time=end_date_time,
                                    yearfirst=time_stamp_year_first,
                                    dayfirst=time_stamp_day_first, timezone=time_zone)
                            if file_time_stamp >= end_date_time:
                                # the file time stamp is larger, so don't add it
                                add_file = False

                if dir_has_string is not None and top_directory:
                    # in case we have specified a directory name with a string search, exclude the
                    # top directory
                    add_file = False

                if max_depth is not None and depth > max_depth:
                    add_file = False

                # create the full base name file
                file_name_to_add = os.path.join(walk_dir, relative_path, filebase)

                # get the path to the stl relative to the selected scan directory
                if add_file:
                    log.debug("Adding file {}".format(filebase))
                    file_list.append(clear_path(file_name_to_add + ext))

    # sort on the file name. First split the file base from the path, because if the file are in
    # different directories, the first file is not necessarily the oldest
    if sort_file_base_names:
        df = pd.DataFrame(data=file_list, index=[os.path.split(f)[1] for f in file_list],
                          columns=["file_list"])
        df.sort_index(inplace=True)
        file_list = df.file_list.values

    return file_list


def make_directory(directory):
    """Create a directory in case it does not yet exist.

    Parameters
    ----------
    directory : str
        Name of the directory to create

    Notes
    -----
    This function is used to create directories without checking if it already exist. If the
    directory already exists, we can silently continue.

    Raises
    ------
    OSError
        The OSError is only raised if it is not an `EEXIST` error. This implies that the creation
        of the directory failed due to another reason than the directory already being present.
        It could be that the file system is full or that we may not have write permission

    """
    logger = get_logger(__name__)
    try:
        os.makedirs(directory)
        logger.debug("Created directory : {}".format(directory))
    except OSError as exc:
        # an OSError was raised, see what is the cause
        if exc.errno == errno.EEXIST and os.path.isdir(directory):
            # the output directory already exists, that is ok so just continue
            logger.debug(
                "Directory {} already exists. No problem, we just continue".format(directory))
        else:
            # something else was wrong. Raise an error
            logger.warning(
                "Failed to create the directory {} because raised:\n{}".format(directory, exc))
            raise


def get_logger(name):
    """Get the logger of the current level and set the level based on the main routine. Then return
    it

    Parameters
    ----------
    name : str
        the name of the logger to set.

    Returns
    -------
    type
        log: a handle of the current logger

    Notes
    -----
    This routine is used on top of each function to get the handle to the current logger and
    automatically set the verbosity level of the logger based on the main function

    Examples
    --------

    Assume you define a function which need to generate logging information based on the logger
    created in the main program. In that case you can do

    >>> def small_function():
    ...    logger = get_logger(__name__)
    ...    logger.info("Inside 'small_function' This is information to the user")
    ...    logger.debug("Inside 'small_function' This is some debugging stuff")
    ...    logger.warning("Inside 'small_function' This is a warning")
    ...    logger.critical("Inside 'small_function' The world is collapsing!")

    The logger can be created in the main program using the create_logger routine

    >>> def main(logging_level):
    ...     main_logger = create_logger(console_log_level=logging_level)
    ...     main_logger.info("Some information in the main")
    ...     main_logger.debug("Now we are calling the function")
    ...     small_function()
    ...     main_logger.debug("We are back in the main function")

    Let's call the main fuction in DEBUGGING mode

    >>> main(logging.DEBUG)
      INFO : Some information in the main
     DEBUG : Now we are calling the function
      INFO : Inside 'small_function' This is information to the user
     DEBUG : Inside 'small_function' This is some debugging stuff
    WARNING : Inside 'small_function' This is a warning
    CRITICAL : Inside 'small_function' The world is collapsing!
     DEBUG : We are back in the main function


    You can see that the logging level inside the `small_function` is obtained from the main level.
    Do the same but now in the normal information mode

    >>> main(logging.INFO)
      INFO : Some information in the main
      INFO : Inside 'small_function' This is information to the user
    WARNING : Inside 'small_function' This is a warning
    CRITICAL : Inside 'small_function' The world is collapsing!

    We can call in the silent mode, suppressing all debugging and normal info, but not Warnings

    >>> main(logging.WARNING)
    WARNING : Inside 'small_function' This is a warning
    CRITICAL : Inside 'small_function' The world is collapsing!

    Finally, to suppress everything except for critical warnings

    >>> main(logging.CRITICAL)
    CRITICAL : Inside 'small_function' The world is collapsing!

    """
    # the logger is based on the current main routine
    log = logging.getLogger(name)
    log.setLevel(logging.getLogger("__main__").getEffectiveLevel())
    return log


def is_exe(fpath):
    """Test if a file is an executable

    Parameters
    ----------
    fpath : str
        return true or false:

    Returns
    -------
    bool
        In case `fpath` is a file that can be executed return True, else False

    Notes
    -----
    This function can only be used on Linux file systems as the `which` command is used to identity
    the location of the program.
    """
    # use system command 'which' to locate the full location of the file
    p = subprocess.Popen("which {}".format(fpath), shell=True, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT)
    p_list = p.stdout.read().splitlines()
    if p_list:
        # which return a path so copy it to fpath
        fpath = p_list[0]
    return os.path.isfile(fpath) and os.access(fpath, os.X_OK)


def clear_path(path_name):
    """routine to clear spurious dots and slashes from a path name
     example bla/././oke becomes bla/oke

    Parameters
    ----------
    path_name :
        return: clear_path as a string

    Returns
    -------
    type
        clear_path as a string

    Examples
    --------

    >>> long_path = os.path.join(".", "..", "ok", "yoo", ".", ".", "") + "/"
    >>> print(long_path)
    .\..\ok\\yoo\.\.\/
    >>> print(clear_path(long_path))
    ..\\ok\\yoo

    """
    return str(pathlib.PurePath(path_name))


def create_logger(name="root",
                  log_file=None,
                  console_log_level=logging.INFO,
                  console_log_format_long=False,
                  console_log_format_clean=False,
                  file_log_level=logging.INFO,
                  file_log_format_long=True,
                  redirect_stderr=True
                  ):
    """Create a console logger

    Parameters
    ----------
    name : str, optional
        Name of the logger. Default = "root"
    log_file : str, optional
        The name of the log file in case we want to write it to file. If it is not specified, no
        file is created
    console_log_level: int, optional
        The level of the console output. Defaults to logging.INFO
    console_log_format_long : bool
        Use a long informative format for the logging output to the console
    console_log_format_clean : bool
        Use a very clean format for the logging output.  If given together with
        consosl_log_format_long an
        AssertionError is raised
    file_log_level: int, optional
        In case the log file is used, specify the log level. Can be different from the console log
        level. Defaults to logging.INFO
    file_log_format_long: bool, optional
        Use a longer format for the file output. Default to True
    redirect_stderr: bool, optional
        If True the stderr output is written to a file with .err extension in stated of .out.
        Default = True

    Returns
    -------
    object
        The handle to the logger which we can use to create output to the screen using the logging
        module

    Examples
    --------

    Create a logger at the verbosity level, so no debug information is generated

    >>> logger = create_logger()
    >>> logger.debug("This is a debug message")

    The info and warning message are both plotted

    >>> logger.info("This is a information message")
      INFO : This is a information message
    >>> logger.warning("This is a warning message")
    WARNING : This is a warning message

    Create a logger at the debug level

    >>> logger = create_logger(console_log_level=logging.DEBUG)
    >>> logger.debug("This is a debug message")
     DEBUG : This is a debug message
    >>> logger.info("This is a information message")
      INFO : This is a information message
    >>> logger.warning("This is a warning message")
    WARNING : This is a warning message

    Create a logger at the warning level. All output is suppressed, except for the warnings

    >>> logger = create_logger(console_log_level=logging.WARNING)
    >>> logger.debug("This is a debug message")
    >>> logger.info("This is a information message")
    >>> logger.warning("This is a warning message")
    WARNING : This is a warning message

    It is also possible to redirect the output to a file. The file name given without an extension,
    as two file are created: one with the extension .out and one with the extension .err, for the
    normal user generated out put and system errors output respectively.

    >>> data_dir = os.path.join(os.path.split(__file__)[0], "..", "..", "data")
    >>> file_name = os.path.join(data_dir, "log_file")
    >>> logger = create_logger(log_file=file_name,  console_log_level=logging.INFO,
    ... file_log_level=logging.DEBUG, file_log_format_long=False)
    >>> logger.debug("This is a debug message")
    >>> logger.info("This is a information message")
      INFO : This is a information message
    >>> logger.warning("This is a warning message")
    WARNING : This is a warning message
    >>> print("system normal message")
    system normal message
    >>> print("system error message", file=sys.stderr)

    At this point, two files have been generated, log_file.out and log_file.err. The first contains
    the normal logging output whereas the second contains error message generated by other packages
    which do not use the logging module. Note that the normal print statement shows up in the
    console but not in the file, whereas the second print statement to the stderr output does not
    show on the screen but is written to log_file.err

    To show the contents of the generated files we do

    >>> with open(file_name+".out", "r") as fp:
    ...   for line in fp.readlines():
    ...       print(line.strip())
    DEBUG : This is a debug message
    INFO : This is a information message
    WARNING : This is a warning message
    >>> sys.stderr.flush()  # forces to flush the stderr output buffer to file
    >>> with open(file_name + ".err", "r") as fp:
    ...   for line in fp.readlines():
    ...       print(line.strip())
    system error message

    References
    ----------
    https://docs.python.org/3/library/logging.html#levels

    """

    # start with creating the logger with a DEBUG level
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    logger.handlers = []

    # create a console handle with a console log level which may be higher than the current level
    ch = logging.StreamHandler(stream=sys.stdout)
    ch.setLevel(console_log_level)

    fh = None

    # create file handler if a file name is given with more info
    if log_file is not None:
        log_file_out = log_file + ".out"
        fh = logging.FileHandler(log_file_out, mode='w')
        fh.setLevel(file_log_level)

        if redirect_stderr:
            error_file = log_file + ".err"
            sys.stderr = open(error_file, 'w')

    formatter_long = logging.Formatter('[%(asctime)s] %(levelname)8s --- %(message)s ' +
                                       '(%(filename)s:%(lineno)s)', datefmt='%Y-%m-%d %H:%M:%S')
    formatter_normal = logging.Formatter('%(levelname)6s : %(message)s')

    formatter_short = logging.Formatter('%(message)s')

    if console_log_format_clean and console_log_format_long:
        raise AssertionError("Can only specify either a long or a short logging format. Not both "
                             "at the same time")

    # create formatter and add it to the handlers for the console output
    if console_log_format_long:
        formatter_cons = formatter_long
    elif console_log_format_clean:
        formatter_cons = formatter_short
    else:
        formatter_cons = formatter_normal

    ch.setFormatter(formatter_cons)

    if log_file is not None:
        if file_log_format_long:
            formatter_file = formatter_long
        else:
            formatter_file = formatter_normal

        # create console handler with a higher log level
        fh.setFormatter(formatter_file)

        # add the handlers to the logger
        logger.addHandler(fh)

    logger.addHandler(ch)
    if log_file:
        logger.addHandler(fh)

    return logger


def delete_module(modname, paranoid=None):
    """Delete a module from memory which loaded before

    Parameters
    ----------
    modname : str
        The name of the module to remove

    paranoid : list or None
         (Default value = None)
    """
    from sys import modules
    try:
        thismod = modules[modname]
    except KeyError:
        raise ValueError(modname)
    these_symbols = dir(thismod)
    if paranoid:
        try:
            paranoid[:]  # sequence support
        except IndexError:
            raise ValueError('must supply a finite list for paranoid')
        else:
            these_symbols = paranoid[:]
    del modules[modname]
    for mod in list(modules.values()):
        try:
            delattr(mod, modname)
        except AttributeError:
            pass
        if paranoid:
            for symbol in these_symbols:
                if symbol[:2] == '__':  # ignore special symbols
                    continue
                try:
                    delattr(mod, symbol)
                except AttributeError:
                    pass


def get_clean_version(version):
    """turns the full version string into a clean one without the build

    Parameters
    ----------
    version : str
        The version string as return from versioneer.

    Returns
    -------
    str
        The clean version string

    Notes
    -----
    The version string matches the following regular expression

        "([.|\d]+)([+]*)(.*)"

    This function return the clean version string given by the part "([.|\d]+)"

    Examples
    --------

    >>> get_clean_version("1.3")
    '1.3'
    >>> get_clean_version("2.5+dev.g43429")
    '2.5'
    >>> get_clean_version("4.3.1+dev.g43429-dirty")
    '4.3.1'

    """
    match = re.search("([.|\d]+)([+]*)(.*)", version)
    if bool(match):
        version = match.group(1)
    else:
        version = version
    return version


def read_settings_file(file_name):
    """Read the yaml file to get the setup information.

    Parameters
    ----------
    file_name : str
        Name of the configuration file. Can be a full path name as well

    Returns
    -------
    dict
        All the settings as obtained from the yaml configuration file

    Notes
    -----
    The file name of the yaml file is searched for in the following order

    1. The current directory where the script is executed. If a full path is given, this will be
       accepted too.
    2. The directory where the original script is located.

    In this way, a default settings file can be put in the script directory and the user does not
    need to copy it except a setting values needs to be changed

    Raises
    ------
    AssertionError:
        In case the file can not be found
    """

    logger = get_logger(__name__)

    if os.path.exists(file_name):
        logger.info("Loading configuration file {}".format(file_name))
        configuration_file = file_name
    else:
        logger.info("Loading configuration file from script dir {}".format(__name__))
        configuration_file = os.path.join(os.path.split(__file__)[0], os.path.split(file_name)[1])
    try:
        logger.debug("Trying to read configuration file {}".format(configuration_file))
        with open(configuration_file, "r") as stream:
            settings = yaml.load(stream=stream, Loader=yamlloader.ordereddict.CLoader)
    except IOError as err:
        raise AssertionError("Configuration file can not be found in either current directory of "
                             "script directory. Goodbye. {}".format(err))

    return settings


def get_python_version_number(version_info):
    """Script to turn the version info as obtained with sys.version_info into a digit number

    Parameters
    ----------
    version_info :
        return: a string with the current python version as a clear digit, i.e. 3.5.3

    Returns
    -------
    type
        a string with the current python version as a clear digit, i.e. 3.5.3

    Examples
    --------
    >>> version_string = get_python_version_number(sys.version_info)

    """

    python_version = "{:d}".format(version_info.major)
    if version_info.minor != "":
        python_version += ".{:d}".format(version_info.minor)
    if version_info.micro != "":
        python_version += ".{:d}".format(version_info.micro)

    return python_version


def get_regex_pattern(search_pattern):
    """Routine to turn a string into a regular expression which can be used to match a string

    Parameters
    ----------
    search_pattern : str
        A regular expression in the form of a string

    Returns
    -------
    None or compiled regular expression
        A regular expression as return by the re.compile fucntion or None in case a invalid regular
        expression was given

    Notes
    -----
    An empty string or an invalid search_pattern will yield a None return

    """
    regular_expresion = None
    if search_pattern != "":
        try:
            regular_expresion = re.compile("{}".format(search_pattern))
        except re.error:
            regular_expresion = None
    return regular_expresion


def clear_argument_list(argv):
    """
    Small utility to remove the \'\\\\r\' character from the last argument of the argv list
    appearing in cygwin

    Parameters
    ----------
    argv : list
        The argument list stored in `sys.argv`

    Returns
    -------
    list
        Cleared argument list

    """
    new_argv = list()
    for arg in argv:
        # replace the '\r' character with a empty space
        arg = re.sub("\r", "", arg)
        if arg != "":
            # only add the argument if it is not empty
            new_argv.append(arg)
    return new_argv


def query_yes_no(question, default_answer="no"):
    """Ask a yes/no question via raw_input() and return their answer.

    Parameters
    ----------
    question : str
        A question to ask the user
    default_answer : str, optional
        A default answer that is given when only return is hit. Default to 'no'

    Returns
    -------
    str:
        "yes" or "no", depending on the input of the user
    """
    log = get_logger(__name__)
    valid = {"yes": "yes", "y": "yes", "ye": "yes",
             "no": "no", "n": "no"}
    if not default_answer:
        prompt = " [y/n] "
    elif default_answer == "yes":
        prompt = " [Y/n] "
    elif default_answer == "no":
        prompt = " [y/N] "
    else:
        raise ValueError("invalid default answer: '%s'" % default_answer)

    while 1:
        # sys.stdout.write(question + prompt)
        log.warning(question + prompt)
        choice = input().lower()
        if default_answer is not None and choice == '':
            return default_answer
        elif choice in list(valid.keys()):
            return valid[choice]
        else:
            sys.stdout.write("Please respond with 'yes' or 'no' "
                             "(or 'y' or 'n').\n")


def print_banner(title, top_symbol="-", bottom_symbol=None, side_symbol=None, width=80,
                 to_stdout=False, no_top_and_bottom=False):
    """Create a banner for plotting a bigger title above each section in the log output

    Parameters
    ----------
    title :
        The title to plot
    top_symbol : str
        the symbol used for the top line. Default value = "-"
    bottom_symbol : str
        the symbol used for the bottom line. Assume same as top if None is given
        (Default value = None)
    side_symbol : str
        The side symbol. Assume same as top if None is given, except if top is -, then take |
        (Default value = None)
    width : int
        the width of the banner (Default value = 80)
    no_top_and_bottom : bool
        make a simple print without the top and bottom line (Default value = False)
    to_stdout : bool, optional
        Print the banner to the standard output of the console instead of the logging system.
        Defaults to False

    Examples
    --------

    >>> logger = create_logger(console_log_format_clean=True)
    >>> print_banner("This is the start of a section")
    <BLANKLINE>
    --------------------------------------------------------------------------------
    | This is the start of a section                                               |
    --------------------------------------------------------------------------------

    Notes
    -----

    Unless the option 'to_stdout' is set to True, the banner is printed via the logging system.
    Therefore, a logger needs to be created first using `create_logger`

    """
    logger = get_logger(__name__)

    logger.debug("message debug in print_banner")

    if bottom_symbol is None:
        bottom_symbol = top_symbol

    if side_symbol is None:
        if bool(re.match("-", top_symbol)):
            side_symbol = "|"
        else:
            side_symbol = top_symbol

    if not no_top_and_bottom:
        message_string = "{}\n" + "{} ".format(side_symbol) + "{:" + "{:d}".format(width - 4) \
                         + "}" + " {}".format(side_symbol) + "\n{}"
        message = message_string.format(top_symbol * width, title, bottom_symbol * width)
    else:
        message_string = "{} ".format(side_symbol) + "{:" + "{:d}".format(width - 4) + "}"
        message = message_string.format(title)
    if to_stdout:
        print("\n{}".format(message))
        sys.stdout.flush()
    else:
        logger.info("\n{}".format(message))


def move_script_path_to_back_of_search_path(script_file, append_at_the_end=True):
    """Move the name of a script to the front or the back of the search path

    Parameters
    ----------
    script_file : str
        Name of the script to move

    append_at_the_end: bool, optional, default=True
        Append the name of the script to the end. In case this flag is false, the script file is
        prepended to the path

    Returns
    -------
    list:
        The new system path stored in a list

    Notes
    -----
    This script is sometimes required if the __version string is messing up with
    another __version string

    Examples
    --------

    sys.path = move_script_path_to_back_of_search_path(__file__)
    """
    script_file = os.path.realpath(script_file)
    path_to_script = os.path.split(script_file)[0]
    path_to_script_forward = re.sub("\\\\", "/", path_to_script)
    new_sys_path = list()
    for path in sys.path:
        path_forward = re.sub("\\\\", "/", path)
        if path_forward != path_to_script_forward:
            new_sys_path.append(path)

    if append_at_the_end:
        new_sys_path.append(path_to_script)
    else:
        new_sys_path = [path_to_script] + new_sys_path
    return new_sys_path


def read_value_from_dict_if_valid(dictionary, key, default_value=None):
    """small routine to read a value from a dictionary. If the value is not set, just return the
    default value

    Parameters
    ----------
    dictionary :
        dictionary which is supposed to carry this key field
    key :
        the name of the field to read the value from
    default_value :
        default value in case we fail to read the key field (if it does not exist)

    Returns
    -------
    type
        value of the key field or the default value

    """
    try:
        value = dictionary[key]
    except KeyError:
        value = default_value

    return value


def set_value_if_valid(value, new_value):
    """small routine to set a value on if it is not none. Otherwise the original value is taken

    Parameters
    ----------
    value :
        the original value which you can pre-define with a default value
    new_value :
        the new value. Only set this if it is not none

    Returns
    -------
    type
        net value or the original if new_value was None

    """

    if new_value is not None:
        value = new_value

    return value


def compare_objects(obj1, obj2, counter=0, max_recursion_depth=4):
    """
    Compare if two object are equal

    Parameters
    ----------
    obj1: class
        first object
    obj2: class
        second object
    counter: int
        Current recursion depth. Keeps track of how many time we have recursively called this
        function
    max_recursion_depth: int
        Maximum depth to which we are comparing the objects.


    Notes
    -----
    * This function compares all the attributes of two object to see if their values are the same
    * An attribute field may be another object which we also want to compare with the same
      attribute of the other object. This is done by recursively calling this function again.
    * Due to the recursive call mechanism we may end up in a infinite loop. To prevent this,
      a maximum recursion depth can be given.
    * The test function *test_sequence_tool* of the *sequence_tool_utils* module uses this
      function to compare to *SequenceToolSummary* objects

    Raises
    ------
    AssertionError:
        In case on of the object fields is not equal

    """
    for att in dir(obj1):
        if att.startswith("_"):
            continue
        val1 = getattr(obj1, att)
        val2 = getattr(obj2, att)
        try:
            np.testing.assert_equal(val1, val2)
        except AssertionError:
            if type(val1) is str or type(val1) is list:
                raise
            counter += 1
            if counter < max_recursion_depth:
                compare_objects(val1, val2)
            else:
                continue


def set_default_dimension(parse_value, default_dimension=None, force_default_units=False):
    """
    Add a *pint* dimension to a value


    Parameters
    ----------
    parse_value: ndarray or str or float
        Value with optional a dimension written in the form of a str. Can be an array or list of
        strings as well
    default_dimension: str
        Required default dimension
    force_default_units: bool
        If true the only allowed dimension is the default dimension. Raise an error in case this is
        not the case. Default = False

    Returns
    -------
    :obj:`Quantity`
        Value with the quantity as give by the default

    Raises
    ------
    AssertionError
        In case the dimension of the *parse_value* argument is not not but:

        1. Its dimensionality is not the same as the dimensionality of the *default_dimension*
        2. Its units is not the same as the unit of the *default_dimension* and the
           *force_default_units* flag is set to *True*

    Notes
    -----
    * This function is a add-on to the *pint* module, a package to define, operate and manipulate
      physical quantities: https://pypi.python.org/pypi/Pint.
    * This function is used to add a dimension to a value which is parsed from a text file.
    * It is checked if the value given in the text file has dimension already, for example that
      it was given as "1.0 m/s".
    * If a dimension was given already: check if the dimensionality (in this case: Length/Time)
      is the same as the dimensionality of the *default_dimension* input argument.
    * In case the input value does not have an explicit dimension, the dimension given by
      *default_dimension* is added to the value.
    * This function works on both scalar and list values

    Examples
    --------

    Assume we want to read input values from a text file as plain numbers and we want to add a
    default dimension of *meter* to it in case the value do not have an explicit dimension yet.
    Just do

    >>> logger = create_logger(console_log_level=logging.CRITICAL)
    >>> value_without_dimension = 1.0  # this is the values as we read from the text file
    >>> value_with_dimension = set_default_dimension(value_without_dimension, "meter")
    >>> print(value_with_dimension)
    1.0 meter

    The variable *value_with_dimension* is now a pint quantity which carries the dimension meter.

    In case the input variable already has a dimension, we should also be able to use this
    *function*. The only requirement is that the dimensionality is the same. So this should work

    >>> value_with_dimension = set_default_dimension("2.5 meter", "meter")
    >>> print(value_with_dimension)
    2.5 meter

    This should work as well

    >>> value_with_dimension = set_default_dimension("5.0 mm", "meter")
    >>> print(value_with_dimension)
    5.0 millimeter

    But this fails as the dimensionality of the input argument is not corresponding with the
    dimensionality of the default dimension

    >>> try:
    ...    value_with_dimension = set_default_dimension("5.0 mm", "second")
    ... except AssertionError:
    ...    print("This fails because the dimensionality is not the same")
    This fails because the dimensionality is not the same

    This function should also work for arrays and list

    >>> values_without_dimension = np.linspace(0, 1, num=5, endpoint=True)
    >>> values_with_dimension = set_default_dimension(values_without_dimension, "meter/second^2")
    >>> print(values_with_dimension)
    [0.   0.25 0.5  0.75 1.  ] meter / second ** 2

    Notes
    -----
    * Hz are not converted to rad/s as expected. Therefore do not try to use this to convert
      Hz -> rad/s
    * If the input argument *parse_val* is None, a None is returned as output as well

    """
    logger = get_logger(__name__)
    if default_dimension is not None:
        def_unit_val = Q_(1, default_dimension)
    else:
        def_unit_val = None
    dimensionless_unit_val = Q_("1")
    dimensionless = dimensionless_unit_val.dimensionality

    if parse_value is not None:
        # in case no dimensions are given with the parse_value argument, impose them

        if isinstance(parse_value, (list, tuple, np.ndarray)):
            # to properly deal with arrays and list first check if we have one
            v = Q_(parse_value[0])
            # if this is allowed we have and array. Check the value and dimension of the first
            # element
            if v.dimensionality == dimensionless and v.units == dimensionless_unit_val.units:
                if not isinstance(parse_value[0], type(dimensionless_unit_val)):
                    # there are no dimensions. Just convert the array, add the dimensions later
                    ret_val = Q_(parse_value)
                else:
                    # we have added the quantity to the parse_value already. Just copy it
                    ret_val = parse_value
            else:
                # The element have a dimension, to convert the array in a bare array without
                # dimensions and copy the dimension type to the default.  Then we can just do the
                # conversion below
                parse_value = np.array([Q_(x).magnitude for x in parse_value])
                ret_val = Q_(parse_value)
                if def_unit_val is not None and v.dimensionality != def_unit_val.dimensionality:
                    raise AssertionError(
                        "The first value of the array given has a dimension with a different "
                        "dimensionality as the default dimension. Found {}. Expected {}"
                        "".format(v.dimensionality, def_unit_val.dimensionality))

                def_unit_val = v.units
        elif not isinstance(parse_value, type(dimensionless_unit_val)):
            # the parse_value is not yet a quantity objects
            ret_val = Q_(parse_value)
        else:
            # the parser value is a quantity already. Just copy it
            ret_val = parse_value

        if ret_val.dimensionality == dimensionless and ret_val.units == dimensionless_unit_val.units:
            # if no dimension is given, add the default dimension
            ret_val = Q_(np.asarray(parse_value), default_dimension)
            if ret_val.dimensionality != dimensionless:
                logger.debug("A dimensionless value was and a default dimension was imposed "
                             "{} -> {}.".format(parse_value, ret_val))
        elif def_unit_val is not None:
            # check if the dimensionality is the same as the def_units
            if ret_val.dimensionality != def_unit_val.dimensionality:
                raise AssertionError(
                    "Value given has a dimension with a different dimensionality as the default "
                    "dimension\nFound {}. Expected {}".format(ret_val.dimensionality,
                                                              def_unit_val.dimensionality))

        # we want to force the units. Check it
        if force_default_units:
            if ret_val.units != def_unit_val.units:
                raise AssertionError(
                    "The dimensions given to the value do not match the default units. \n"
                    "Found {}. Expected {}\nPlease fix or set *only_default_units_allowed* "
                    "to False".format(ret_val.units, def_unit_val.units))
    else:
        # in case a none value is given as input just return none as output
        ret_val = None

    return ret_val


def get_value_magnitude(value, convert_to_base_units=True):
    """
    Get the magnitude of value with *Pint* dimension in terms of its base units or just return a
    float if *value* does not have a dimension

    Parameters
    ----------
    value: Quantity or float or None
        A value with a Pint dimension or a normal float. In both cases, the value without
        dimension is returned
    convert_to_base_units: bool, optional
        Before turning the value into a magnitude first turn the quantity into its SI base units.
        Default = True

    Returns
    -------
    float or None
        Magnitude of the value in case a Pint Quantity was added to the input or just the value
        itself. If *convert_to_base_units* was set to True the value is first converted to its SI
        base units

    Examples
    --------
    Assume we have a value with a pint dimension

    >>> velocity = Q_("2.5 m/s")
    >>> print("Current velocity with dimension is: {}".format(velocity))
    Current velocity with dimension is: 2.5 meter / second

    We can now get the magnitude of *velocity* using this function as

    >>> velocity_mag = get_value_magnitude(velocity)
    >>> print("Velocity without dimension is: {}".format(velocity_mag))
    Velocity without dimension is: 2.5

    In case the input argument of the *get_value_magnitude* is a float and does not have a
    dimension, the value itself is returned

    >>> velocity_mag2 = get_value_magnitude(velocity_mag)
    >>> print("Velocity without dimension is: {}".format(velocity_mag2))
    Velocity without dimension is: 2.5

    In case we have a dimension in none SI units, the value  is by default first converted to its
    SI base units.

    >>> velocity_knots = Q_("1 knot")
    >>> velocity_mag = get_value_magnitude(velocity_knots)
    >>> print("Velocity {} is converted to its magnitude in m/s: {:.2f}"
    ...       "".format(velocity_knots, velocity_mag))
    Velocity 1 knot is converted to its magnitude in m/s: 0.51

    In case that the *convert_to_base_units* flag is False we just get the magnitude in the same
    units as the input argument

    >>> velocity_knots = Q_("2.5 knot")
    >>> velocity_mag = get_value_magnitude(velocity_knots, convert_to_base_units=False)
    >>> print("Velocity {} is converted to its magnitude in knots: {:.2f}"
    ... "".format(velocity_knots, velocity_mag))
    Velocity 2.5 knot is converted to its magnitude in knots: 2.50

    Notes
    -----
    * This function is used inside other functions in which it is not know before hand if an input
      argument is passed with or without a Pint dimension and we only are interested in the
      magnitude of the value. Use this function to get the magnitude
    """

    try:
        if convert_to_base_units:
            value = value.to_base_units()
        value_mag = value.magnitude
    except AttributeError:
        value_mag = value

    return value_mag


def get_time_stamp_from_string(string_with_date_time, yearfirst=True, dayfirst=False,
                               timezone=None):
    """
    Try to get a date/time stamp from a string

    Parameters
    ----------
    string_with_date_time: str
        The string to analyses
    yearfirst: bool, optional
        if true put the year first. See *dateutils.parser*. Default = True
    dayfirst: bool, optional
        if true put the day first. See *dateutils.parser*. Default = False
    timezone: str or None, optional
        if given try to add this time zone:w

    Returns
    -------
    :obj:`DateTime`
        Pandas data time string

    Examples
    --------

    The  date time in the file 'AMSBALDER_160929T000000' is  29 sep 2016 and does not have a
    time zone specification. The returned time stamp does also not have a time zone

    >>> file_name="AMSBALDER_160929T000000"
    >>> time_stamp =get_time_stamp_from_string(string_with_date_time=file_name)
    >>> print("File name {} has time stamp {}".format(file_name, time_stamp))
    File name AMSBALDER_160929T000000 has time stamp 2016-09-29 00:00:00

    We can also force to add a time zone. The Etc/GMT-2 time zone is UTC + 2 time zone which is
    the central europe summer time (CEST) or the Europe/Amsterdam Summer time.

    >>> time_stamp =get_time_stamp_from_string(string_with_date_time=file_name,
    ...                                        timezone="Etc/GMT-2")
    >>> print("File name {} has time stamp {}".format(file_name, time_stamp))
    File name AMSBALDER_160929T000000 has time stamp 2016-09-29 00:00:00+02:00

    This time we assume the file name already contains a time zone, 2 hours + UTC. Since we
    already have a time zone, the *timezone* option can only convert the date time to the specified
    time zone.

    >>> file_name="AMSBALDER_160929T000000+02"
    >>> time_stamp =get_time_stamp_from_string(string_with_date_time=file_name,
    ...                                        timezone="Etc/GMT-2")
    >>> print("File name {} has time stamp {}".format(file_name, time_stamp))
    File name AMSBALDER_160929T000000+02 has time stamp 2016-09-29 00:00:00+02:00

    In case the time zone given by the *timezone* options differs with the time zone in the file
    name, the time zone is converted

    >>> file_name="AMSBALDER_160929T000000+00"
    >>> time_stamp =get_time_stamp_from_string(string_with_date_time=file_name,
    ...                                        timezone="Etc/GMT-2")
    >>> print("File name {} has time stamp {}".format(file_name, time_stamp))
    File name AMSBALDER_160929T000000+00 has time stamp 2016-09-29 02:00:00+02:00

    """
    try:
        file_time_stamp = dparser.parse(string_with_date_time, fuzzy=True,
                                        yearfirst=yearfirst,
                                        dayfirst=dayfirst)
        file_time_stamp = pd.Timestamp(file_time_stamp)
    except ValueError:
        file_time_stamp = None
    else:
        # we have found a time stamp. See if we have to add a time zone
        if timezone is not None:
            try:
                file_time_stamp = file_time_stamp.tz_localize(timezone)
            except TypeError:
                # a time zone was present already. Then try to convert it
                file_time_stamp = file_time_stamp.tz_convert(timezone)

    return file_time_stamp
