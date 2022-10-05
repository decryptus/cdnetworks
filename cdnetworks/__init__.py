# -*- coding: utf-8 -*-
# Copyright (C) 2018-2022 Adrien Delle Cave
# SPDX-License-Identifier: GPL-3.0-or-later
"""cdnetworks"""


import logging

from cdnetworks.services import *
from cdnetworks.service import SERVICES


def service(name, **kwargs):
    if name not in SERVICES:
        raise ValueError("invalid service: %r" % name)

    return SERVICES[name].init(**kwargs)
