# -*- coding: utf-8 -*-
"""cdnetworks.service"""

__author__  = "Adrien DELLE CAVE"
__license__ = """
    Copyright (C) 2018  fjord-technologies

    This program is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 2 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License along
    with this program; if not, write to the Free Software Foundation, Inc.,
    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA..
"""

import abc

class CDNetworksServices(dict):
    def register(self, service):
        if not isinstance(service, CDNetworksServiceBase):
            raise TypeError("Invalid Service class. (class: %r)" % service)
        return dict.__setitem__(self, service.SERVICE_NAME, service)

SERVICES = CDNetworksServices()


class CDNetworksServiceBase(object):
    __metaclass__ = abc.ABCMeta

    @abc.abstractproperty
    def SERVICE_NAME(self):
        return

    def __init__(self):
        self.session = None

    def init(self, session):
        self.session = session
        return self

    def logout(self):
        return self.session.logout()

    def _build_uri(self, *args):
        return self.session._build_uri(*args)
