=========
cbs_utils
=========


A collection of generic classes and function which can be used by other CBS Python scripts.


Description
===========

This module contains the following categories

* misc: a set of miscellaneous classes and functions


Notes
-----
* The documentation of this package can be found in the `docs`_ directory


Unit Test
=========
In order to run the standard unit test do

    python setup.py test

Installation
============

Installation at the CBS package directory X:\
(where X points to the network drive installation  `folder`_)
Note that you have to use the Anaconda cmd.exe prompt, not the power shell

* Create the installation package for the current checkout version of the source code

    python setup.py sdist

* Install the package at location X:/

    pip install cbs_utils --no-index --find-links ./dist/cbs_utils-0.1.1.tar.gz --prefix=X:\

* For upgrading the package the upgrade option *-U* needs to be supplied

    pip install cbs_utils --no-index --find-links ./dist/cbs_utils-0.1.1.post0.tar.gz --prefix=X: -U

* To install the documentation first create a directory X:/docs/cbs_utils and then do

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

* TODO

Contributing
============

In case you want to contribute to this package or just have a look at the total pacakge you can do
the following

1. Open the git terminal and go to your working directory
2. Clone the repository from the `github`_::

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

Note
====

This project has been set up using PyScaffold 3.0.3. For details and usage
information on PyScaffold see http://pyscaffold.org/.


