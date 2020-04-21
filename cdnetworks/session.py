# -*- coding: utf-8 -*-
"""cdnetworks.session"""

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

import os
import requests

from sonicprobe.libs import urisup

from cdnetworks.services import *
from cdnetworks.service import SERVICES


_DEFAULT_ENDPOINT = "https://openapi.cdnetworks.com"
_DEFAULT_TIMEOUT  = 30


class Session(object):
    def __init__(self, username = None, password = None, endpoint = None, timeout = None):
        self.endpoint             = None
        self.username             = None
        self.password             = None
        self.timeout              = None
        self.token                = None
        self.svc_group_name       = None
        self.svc_group_identifier = None

        if endpoint:
            self.endpoint = endpoint
        elif os.environ.get('CDNETWORKS_ENDPOINT'):
            self.endpoint = os.environ['CDNETWORKS_ENDPOINT']
        else:
            self.endpoint = self.get_default_endpoint()

        if timeout:
            self.timeout = timeout
        elif os.environ.get('CDNETWORKS_TIMEOUT'):
            self.timeout = os.environ['CDNETWORKS_TIMEOUT']
        else:
            self.timeout = self.get_default_timeout()

        if username:
            self.username = username
        elif os.environ.get('CDNETWORKS_USERNAME'):
            self.username = os.environ['CDNETWORKS_USERNAME']
        else:
            raise ValueError("missing cdnetworks username")

        if password:
            self.password = password
        elif os.environ.get('CDNETWORKS_PASSWORD'):
            self.password = os.environ['CDNETWORKS_PASSWORD']
        else:
            raise ValueError("missing cdnetworks password")

    def _build_uri(self, path = None, query = None, fragment = None):
        uri = list(urisup.uri_help_split(self.endpoint))
        uri[2:5] = (path, query, fragment)

        return urisup.uri_help_unsplit(uri)

    @staticmethod
    def get_default_endpoint():
        return _DEFAULT_ENDPOINT

    @staticmethod
    def get_default_timeout():
        return _DEFAULT_TIMEOUT

    def login(self):
        r = requests.post(self._build_uri("/api/rest/login"),
                          data    = {'user': self.username,
                                     'pass': self.password,
                                     'submit_type': 'POST',
                                     'output': 'json'},
                          timeout = self.timeout)
        if not r or r.status_code != 200:
            raise LookupError("unable to login on %r" % self.endpoint)

        res                         = r.json()
        if not res or 'loginResponse' not in res:
            raise LookupError("invalid login response on %r" % self.endpoint)

        if res['loginResponse'].get('resultCode') != 0:
            raise LookupError("invalid result on login. (code: %r, result: %r)"
                              % (res['loginResponse'].get('resultCode'),
                                 res['loginResponse'].get('resultMsg')))

        self.token                  = res['loginResponse']['session'][0]['sessionToken']
        self.svc_group_name         = res['loginResponse']['session'][0]['svcGroupName']
        self.svc_group_identifier   = res['loginResponse']['session'][0]['svcGroupIdentifier']

        return self

    def service(self, service_name):
        self.login()
        if service_name not in SERVICES:
            raise ValueError("invalid service: %r" % service_name)

        return SERVICES[service_name].init(self)

    def logout(self):
        if not self.token:
            raise ValueError("missing session token to logout")

        r   = requests.post(self._build_uri("/api/rest/logout"),
                            data    = {'sessionToken': self.token,
                                       'submit_type':  'POST',
                                       'output':       'json'},
                            timeout = self.timeout)
        if not r or r.status_code != 200:
            raise LookupError("unable to logout on %r" % self.endpoint)

        res = r.json()
        if not res or 'logoutResponse' not in res:
            raise LookupError("invalid response on logout")

        if res['logoutResponse'].get('resultCode') != 0:
            raise LookupError("invalid result on logout. (code: %r, result: %r)"
                              % (res['logoutResponse'].get('resultCode'),
                                 res['logoutResponse'].get('resultMsg')))

        return self
