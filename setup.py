#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import os
from setuptools import find_packages, setup

requirements = [line.strip() for line in open('requirements.txt', 'r').readlines()]
version      = '0.3.1'

if os.path.isfile('VERSION'):
    version = open('VERSION', 'r').readline().strip() or version

setup(
    name                = 'cdnetworks',
    version             = version,
    description         = 'cdnetworks',
    author              = 'Adrien Delle Cave',
    author_email        = 'pypi@doowan.net',
    license             = 'License GPL-3',
    packages		    = find_packages(),
    install_requires    = requirements,
    url                 = 'https://github.com/decryptus/cdnetworks',
    python_requires     = '>=2.7, !=3.0.*, !=3.1.*, !=3.2.*, !=3.3.*, !=3.4.*',
    classifiers         = ['License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
                           'Natural Language :: English',
                           'Operating System :: Unix',
                           'Programming Language :: Python',
                           'Programming Language :: Python :: 2',
                           'Programming Language :: Python :: 2.7',
                           'Programming Language :: Python :: 3',
                           'Programming Language :: Python :: 3.5',
                           'Programming Language :: Python :: 3.6',
                           'Programming Language :: Python :: 3.7']
)
