=========
cbs_utils
=========

A collection of generic classes and function which can be used by other CBS Python scripts.


Description
===========

This module contains the following categories

* **misc** - a set of miscellaneous classes and functions
* **readers**  - tools to read standard data file:
      - *SbiInfo*: Reader of the SBI classification file. Can be used to classify list of sbi codes
      - *StatLineTable*: Reader of the open data StatLine tables. Turned into a pandas data frame
* **plotting** - Some cbs color definitions
* **web_scraping** - Web scraping utilities and classes
* **string_measures** - Some string utilities

Documentation
=============
* Intranet documentation: docs_
* Internet documentation: readthedocs_

Unit Test
=========
In order to run the standard unit test do

    python setup.py test

Installation
============

Installation of the CBS package can be done under linux using pip as

directory X:\ (X is the network drive installation folder_)

* In the conda command terminal, go to the location where you have downloaded the repository and run

    pip install  -e cbs_utils --prefix=X:\

* In case you want to install the package in your user environment do

    pip install  -e cbs_utils --user

Installation of the CBS package can be done under windows in the the directory X:\ (X is the network drive
installation folder_)  as

* In the conda command terminal, go to the location where you have downloaded the repository and run

    cd cbs_utils

    python setup.py sdist

* In case you want to install the package in your user environment do

    pip install cbs_utils --no-index --find-links dist/cbs_utils_versionnumber.tgz --prefix=X:\

* For upgrading the package the upgrade option *-U* needs to be supplied

    pip install  cbs_utils-0.4.9.py3-none-any.whl --prefix=X:\ -U

* To install the documentation first create a directory X:/docs/cbs_utils and then go into the
  *cbs_utils* directory and run

    python setup.py docs --build-dir X:/docs/cbs_utils

Requires
========

At least the following packages are required for this module to run

* numpy
* pathlib
* yamlloader
* pandas
* pint
* statsmodels

Examples
========

Some example recipes to use the package can be found here

* Web Scraping With cbs_utils:
    - :download:`../examples/web_scraping_examples.html` (static html)
    - :download:`../examples/web_scraping_examples.ipynb` (jupyter notebook)

Contributing
============

In case you want to contribute to this package or just have a look at the total pacakge you can do
the following

1. Open the git terminal and go to your working directory
2. Clone the repository from the github_::

    git clone http://github/git/Python_repositories/cbs_utils.git

3. Go the newly created cbs_utils directory *or* open it  in PyCharm as a new project
4. Create a new branch for your own developments::

    git checkout -b dev_my_name

5. Start doing your work and when done do::

    git add .
    git commit -m 'my developments'

6. Push your work to the development repository as your personal branch::

    git push -u origin dev_my_name

7. Notify the owner of this package

.. _github:
    http://github/git/Python_repositories/cbs_utils.git

.. _folder:
    \\cbsp.nl\Productie\Secundair\DecentraleTools\Output\CBS_Python\Python3.6

.. _docs:
    \\cbsp.nl\Productie\Secundair\DecentraleTools\Output\CBS_Python\Python3.6\docs\cbs_utils\html

.. _readthedocs:
    https://cbs-utils.readthedocs.io/en/latest/

Note
====

This project has been set up using PyScaffold 3.0.3. For details and usage
information on PyScaffold see http://pyscaffold.org/.


