# -*- coding: utf-8 -*-
# Copyright (C) 2018-2022 Adrien Delle Cave
# SPDX-License-Identifier: GPL-3.0-or-later
"""cdnetworks.service"""


import abc
import os

import base64
import hmac

from hashlib import sha256
from datetime import datetime

import logging

import requests

from sonicprobe.libs import urisup


LOG = logging.getLogger('cdnetworks.service')


class CDNetworksServices(dict):
    def register(self, service):
        if not isinstance(service, CDNetworksServiceBase):
            raise TypeError("Invalid Service class. (class: %r)" % service)
        return dict.__setitem__(self, service.SERVICE_NAME, service)

SERVICES = CDNetworksServices()

_DEFAULT_ACCEPT   = "application/json"
_DEFAULT_ENDPOINT = "https://api.cdnetworks.com"
_DEFAULT_TIMEOUT  = 60

_DATE_FORMAT_GMT  = '%a, %d %b %Y %H:%M:%S GMT'

class CDNetworksServiceBase(object):
    __metaclass__ = abc.ABCMeta

    @abc.abstractproperty
    def SERVICE_NAME(self):
        return

    def __init__(self):
        self.username = None
        self.api_key  = None
        self.endpoint = None
        self.accept   = None
        self.timeout  = None

    @staticmethod
    @abc.abstractmethod
    def get_default_api_path():
        return

    @staticmethod
    def get_default_accept():
        return _DEFAULT_ACCEPT

    @staticmethod
    def get_default_endpoint():
        return _DEFAULT_ENDPOINT

    @staticmethod
    def get_default_timeout():
        return _DEFAULT_TIMEOUT

    @staticmethod
    def get_date():
        return datetime.utcnow().strftime(_DATE_FORMAT_GMT)

    def get_auth(self, date):
        signed_api_key = base64.b64encode(
          hmac.new(self.api_key.encode('utf-8'), date.encode('utf-8'), sha256).digest())

        return base64.b64encode(("%s:%s" % (self.username, signed_api_key.decode())).encode('utf-8'))

    def build_api_uri(self, path = None, query = None, fragment = None):
        uri = list(urisup.uri_help_split(self.endpoint))
        uri[2:5] = (path, query, fragment)

        return urisup.uri_help_unsplit(uri)

    def mk_api_headers(self, date = None, auth = None):
        if not date:
            date = self.get_date()

        if not auth:
            auth = self.get_auth(date)

        return {'Date': date,
                'Accept': self.accept,
                'Content-Type': self.accept,
                'Authorization': "Basic %s" % auth.decode()}

    def mk_api_call(self, path = "", method = 'get', raw_results = False, retry = 1, timeout = None, params = None, data = None):
        if path:
            path = "/%s" % path.strip('/')
        else:
            path = ""

        r = None

        try:
            uri = self.build_api_uri("/%s%s" % (self.get_default_api_path(), path))

            r = getattr(requests, method)(uri,
                                          params  = params,
                                          json    = data,
                                          headers = self.mk_api_headers(),
                                          timeout = timeout or self.timeout)

            if raw_results:
                return r

            if not r or r.status_code != 200 or not r.text:
                LOG.error("unable to call uri: %r. (params: %r, data: %r)", uri, params, data)
                raise LookupError("unable to call uri: %r. (response: %r)" % (uri, r.text))

            res  = r.json()
            if not res:
                raise LookupError("invalid response for %r" % path)

            if res.get('code') == '102' and retry:
                return self.mk_api_call(path        = path,
                                        method      = method,
                                        raw_results = raw_results,
                                        retry       = 0,
                                        timeout     = timeout,
                                        params      = params,
                                        data        = data)

            if res.get('code') != '0':
                raise LookupError("invalid result on %r. (code: %r, result: %r)"
                                  % (path,
                                     res.get('code'),
                                     res.get('message') or res.get('msg')))
            return res
        finally:
            if r:
                r.close()

    def init(self, username = None, api_key = None, endpoint = None, timeout = None, accept = None):
        if username:
            self.username = username
        elif os.environ.get('CDNETWORKS_USERNAME'):
            self.username = os.environ['CDNETWORKS_USERNAME']
        else:
            raise ValueError("missing cdnetworks username")

        if api_key:
            self.api_key = api_key
        elif os.environ.get('CDNETWORKS_API_KEY'):
            self.api_key = os.environ['CDNETWORKS_API_KEY']
        else:
            raise ValueError("missing cdnetworks api_key")

        if endpoint:
            self.endpoint = endpoint
        elif os.environ.get('CDNETWORKS_ENDPOINT'):
            self.endpoint = os.environ['CDNETWORKS_ENDPOINT']
        else:
            self.endpoint = self.get_default_endpoint()

        if accept:
            self.accept = accept
        elif os.environ.get('CDNETWORKS_ACCEPT'):
            self.accept = os.environ['CDNETWORKS_ACCEPT']
        else:
            self.accept = self.get_default_accept()

        if timeout:
            self.timeout = timeout
        elif os.environ.get('CDNETWORKS_TIMEOUT'):
            self.timeout = os.environ['CDNETWORKS_TIMEOUT']
        else:
            self.timeout = self.get_default_timeout()

        return self
