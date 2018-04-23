import json
import logging
import requests
import time

from cdnetworks.service import CDNetworksServiceBase, SERVICES
from sonicprobe.libs import urisup


_DEFAULT_VERSION        = "v1"
_DEFAULT_API_PATH       = "api/rest/config/cdns"
DEPLOY_TYPE_STAGING     = 'staging'
DEPLOY_TYPE_PRODUCTION  = 'production'

DEPLOY_TYPES            = (DEPLOY_TYPE_STAGING,
                           DEPLOY_TYPE_PRODUCTION)

DNS_SERVERS             = ('ns1.cdnetdns.net',
                           'ns2.cdnetdns.net')


VALUE_TYPES             = {'MX': ('data', 'value'),
                           'RP': ('mailbox_name', 'domain_name'),
                           'SRV': ('priority', 'weight', 'port', 'target')}

LOG                     = logging.getLogger('cdnetworks.cdns')


class CDNetworksCDNS(CDNetworksServiceBase):
    SERVICE_NAME = 'cdns'

    @staticmethod
    def get_default_version():
        return _DEFAULT_VERSION

    @staticmethod
    def get_default_api_path():
        return _DEFAULT_API_PATH

    @staticmethod
    def _valid_deploy_type(deploy_type, domain_id):
        if not deploy_type:
            return

        if deploy_type not in DEPLOY_TYPES:
            raise ValueError("invalid deploy_type: %r, domain_id: %r" % (deploy_type, domain_id))

    @staticmethod
    def _build_uniq_value(record):
        rr          = record.copy()
        rr['value'] = unicode(rr.get('value', ''))

        if 'record_type' in rr:
            xtype       = rr['record_type']
            rr['value'] = rr['value'].rstrip('.')
        elif 'type' in rr:
            xtype       = rr['type']
        else:
            return rr['value']

        if xtype not in VALUE_TYPES:
            return rr['value']

        r = []

        for v in VALUE_TYPES[xtype]:
            r.append("%s" % (rr.get(v, '')))

        r = ':'.join(r)

        if r.strip(':') == '':
            return ''

        return unicode(r)

    @staticmethod
    def _is_frozen_record(record):
        if record.get('record_type') == 'NS' \
          and record.get('host_name') == '@' \
          and record.get('value', '').rstrip('.') in DNS_SERVERS:
           return True

        return False

    def _mk_api_call(self, path, method = 'get', raw_results = False, retry = 1, **kwargs):
        params = None
        data   = None

        if method == 'post':
            data = kwargs
            data['output'] = 'json'
            data['sessionToken'] = self.session.token
            data['submit_type'] = method.upper()
        else:
            params = kwargs
            params['output'] = 'json'
            params['sessionToken'] = self.session.token
            params['submit_type'] = method.upper()

        r = None

        try:
            r = getattr(requests, method)(self._build_uri("/%s/%s/%s" % (self.get_default_api_path(),
                                                                         self.get_default_version(),
                                                                         path)),
                                          params = params,
                                          data   = data)
            if raw_results:
                return r

            if not r or r.status_code != 200:
                raise LookupError("unable to get %r" % path)

            res  = r.json()
            if not res:
                raise LookupError("invalid response for %r" % path)

            item = res[res.keys()[0]]
            if item.get('resultCode') == 102 and retry:
                self.session.login()
                return self._mk_api_call(path        = path,
                                         method      = method,
                                         raw_results = raw_results,
                                         retry       = 0,
                                         **kwargs)
            elif item.get('resultCode') != 0:
                raise LookupError("invalid result on %r. (code: %r, result: %r)"
                                  % (path,
                                     item.get('resultCode'),
                                     item.get('resultMsg')))
            return item
        except Exception:
            raise
        finally:
            if r:
                r.close()

    def list_domains(self, page = 1, limit = 25, name = None):
        params = {'page':  page,
                  'limit': limit}

        if name:
            params['name'] = name

        return self._mk_api_call("domains/list", method = 'get', **params)

    def search_domains(self, name, page = 1, limit = 25):
        return self._mk_api_call("domains/list",
                                 method = 'get',
                                 **{'name': name,
                                    'page': page,
                                    'limit': limit})

    def get_domain_by_id(self, domain_id):
        r = self._mk_api_call("domains/%d/list" % domain_id,
                              method = 'get')

        if r and r['domains']['domains']:
            return r['domains']['domains'][0]

    def update_domain_ttl(self, domain_id, ttl):
        return self._mk_api_call("domains/%s/edit",
                                 method = 'post',
                                 **{'ttl': ttl})

    def get_records(self, domain_id, record_type = None, record_id = None, record_name = None):
        params = {}
        if record_name is not None:
            if record_name is '':
                record_name = '@'
            params['name'] = record_name

        path   = "domains/%d/records" % domain_id

        if record_type:
            path += "/%s" % record_type
            if record_id:
                path += "/%d" % record_id

        path  += "/list"

        return self._mk_api_call(path, method = 'get', **params)

    def find_records(self, domain_id, record = {}):
        r   = []
        rr  = record.copy()

        if rr.get('host_name') is '':
            rr['host_name'] = '@'

        res = self.get_records(domain_id,
                               rr.get('record_type'),
                               rr.get('record_id'),
                               rr.get('host_name'))

        if not res or 'records' not in res:
            return r

        ref = res['records']

        if rr.get('record_type'):
            if rr['record_type'] not in ref:
                return r

            r = list(ref[rr['record_type']])
        else:
            for rrtype, rrvalue in ref.iteritems():
                for rrv in rrvalue:
                    r.append(rrv)

        value = self._build_uniq_value(rr)

        if not rr.get('record_id') \
           and rr.get('host_name') is None \
           and not value:
            return r

        nr = list(r)

        for nrr in nr:
            if rr.get('record_id') \
               and long(nrr['record_id']) != long(rr['record_id']):
                r.remove(nrr)
                continue

            if rr.get('host_name') is not None \
               and nrr['name'] != rr['host_name']:
                r.remove(nrr)
                continue

            if value and self._build_uniq_value(nrr) != value:
                r.remove(nrr)

        return r

    def create_records(self, domain_id, records, deploy_type = None):
        self._valid_deploy_type(deploy_type, domain_id)

        r    = {'result': None,
                'deploy': None}

        r['result'] = self._mk_api_call("domains/%d/records/add" % domain_id,
                                        method = 'post',
                                        **{'records': json.dumps(records)})

        if deploy_type:
            r['deploy'] = self.deploy(domain_id, deploy_type)

        return r

    def update_records(self, domain_id, records, record_type = None, record_id = None, deploy_type = None):
        self._valid_deploy_type(deploy_type, domain_id)

        r    = {'result': None,
                'deploy': None}

        path  = "domains/%d/records" % domain_id

        if record_type and record_id:
            path += "/%s/%d" % (record_type, record_id)

        path += "/edit"

        r['result'] = self._mk_api_call(path,
                                        method = 'post',
                                        **{'records': json.dumps(records)})

        if deploy_type:
            r['deploy'] = self.deploy(domain_id, deploy_type)

        return r

    def change_records(self, domain_id, records, deploy_type = None):
        self._valid_deploy_type(deploy_type, domain_id)

        actions = {'create': [],
                   'update': [],
                   'delete': {}}

        results = {'create': [],
                   'update': [],
                   'delete': [],
                   'deploy': None}

        for record in records:
            if 'action' not in record:
                raise KeyError("missing action for record: %r" % record)
            action = record.pop('action')

            if self._is_frozen_record(record):
                continue
            elif action == 'create':
                actions['create'].append(record)
                continue
            elif action == 'purge':
                if not record.get('record_type') or not record.get('host_name'):
                    raise ValueError("unable to purge, missing record_type or host_name for record: %r" % record)

                res = self.find_records(domain_id,
                                        record = {'record_type': record['record_type'],
                                                  'host_name':   record['host_name']})
                if res:
                    for row in res:
                        actions['delete'][str(row['record_id'])] = row
                continue

            if action not in ('upsert', 'delete'):
                raise ValueError("action unknown: %r" % action)

            if not record.get('record_id') and record.get('host_name') is None:
                raise ValueError("missing record_id and host_name for record: %r" % record)
            else:
                res = self.find_records(domain_id, record)

            if res and len(res) == 1:
                if action == 'delete':
                    actions['delete'][str(res[0]['record_id'])] = res[0]
                else:
                    if not record.get('record_id'):
                        record['record_id'] = res[0]['record_id']
                    actions['update'].append(record)
            elif action != 'upsert':
                raise LookupError("unable to find record: %r" % record)
            else:
                if record['record_type'] in ('NS', 'TXT'):
                    if record.get('record_id'):
                        actions['update'].append(record)
                        continue

                    res = self.find_records(domain_id, record)
                    if res and len(res) == 1:
                        record['record_id'] = res[0]['record_id']
                        actions['update'].append(record)
                    else:
                        actions['create'].append(record)
                else:
                    res = self.find_records(domain_id, record)
                    if res and len(res) == 1:
                        actions['delete'][str(res[0]['record_id'])] = res[0]
                    actions['create'].append(record)

        for record in actions['delete'].itervalues():
            results['delete'].append(self.delete_record(domain_id, record['type'], record['record_id']))

        for action in ('update', 'create'):
            for record in actions[action]:
                results[action].append(getattr(self, "%s_records" % action)(domain_id, [record]))

        if deploy_type:
            results['deploy'] = self.deploy(domain_id, deploy_type)

        return results

    def delete_record(self, domain_id, record_type, record_id, deploy_type = None):
        self._valid_deploy_type(deploy_type, domain_id)

        r    = {'result': None,
                'deploy': None}

        path = "domains/%s/records/%s/%d/delete" % (domain_id, record_type, record_id)

        r['result'] = self._mk_api_call(path,
                                        method = 'post')

        if deploy_type:
            r['deploy'] = self.deploy(domain_id, deploy_type)

        return r

    def _api_deploy(self, domain_id):
        return self._mk_api_call("domains/%d/deploy" % domain_id,
                                 method = 'post')

    def deploy(self, domain_id, deploy_type):
        self._valid_deploy_type(deploy_type, domain_id)

        r = dict(zip(DEPLOY_TYPES, len(DEPLOY_TYPES) * ['']))

        while True:
            domain = self.get_domain_by_id(domain_id)
            if not domain:
                raise LookupError("unable to find domain: %r" % domain_id)

            if domain['status_code'] == 0:
                r[DEPLOY_TYPE_STAGING] = self._api_deploy(domain_id)
                time.sleep(1)
                continue
            elif domain['status_code'] == 1:
                time.sleep(1)
                continue
            elif domain['status_code'] == -2:
                raise LookupError("unable to deploy to %r: %r" % (DEPLOY_TYPE_STAGING, domain))

            if deploy_type == DEPLOY_TYPE_STAGING:
                break

            if domain['status_code'] == 2:
                r[DEPLOY_TYPE_PRODUCTION] = self._api_deploy(domain_id)
                time.sleep(1)
                continue
            elif domain['status_code'] == 3:
                time.sleep(1)
                continue
            elif domain['status_code'] == -4:
                raise LookupError("unable to deploy to %r: %r" % (DEPLOY_TYPE_PRODUCTION, domain))
            elif domain['status_code'] == 4:
                break

        return r

if __name__ != "__main__":
    def _start():
        SERVICES.register(CDNetworksCDNS())
    _start()
