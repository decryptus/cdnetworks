# -*- coding: utf-8 -*-
# Copyright (C) 2018-2022 Adrien Delle Cave
# SPDX-License-Identifier: GPL-3.0-or-later
"""cdnetworks.services.cdns"""


import logging

from six import ensure_text, itervalues

from cdnetworks.service import CDNetworksServiceBase, SERVICES


_DEFAULT_API_PATH       = "api/clouddns/zones"
_DEFAULT_DEPLOY_TIMEOUT = 600

DEPLOY_TYPE_STAGING     = 'staging'
DEPLOY_TYPE_PRODUCTION  = 'production'

DEPLOY_TYPES            = (DEPLOY_TYPE_STAGING,
                           DEPLOY_TYPE_PRODUCTION)

DNS_SERVERS             = ('ns1.cdnetdns.net',
                           'ns2.cdnetdns.net')

VALUE_MX_TX             = ('data', 'value')
VALUE_MX_RX             = ('preference', 'value')
VALUE_RP                = ('mailbox_name', 'domain_name')
VALUE_SRV               = ('priority', 'weight', 'port', 'target')
VALUE_SOA_TX            = ('value',)
VALUE_SOA_RX            = ('email',)

VALUE_TYPES             = {'tx':
                           {'MX':  VALUE_MX_TX,
                            'RP':  VALUE_RP,
                            'SRV': VALUE_SRV,
                            'SOA': VALUE_SOA_TX},
                           'rx':
                           {'MX':  VALUE_MX_RX,
                            'RP':  VALUE_RP,
                            'SRV': VALUE_SRV,
                            'SOA': VALUE_SOA_RX}}

LOG                     = logging.getLogger('cdnetworks.cdns')


class CDNetworksCDNS(CDNetworksServiceBase):
    SERVICE_NAME = 'cdns'

    @staticmethod
    def get_default_api_path():
        return _DEFAULT_API_PATH

    @staticmethod
    def _parse_value(record, xfrom = 'tx'):
        if xfrom not in VALUE_TYPES:
            raise ValueError("unable to parse value, invalid from: %r" % xfrom)

        rr = record.copy()
        rr['value'] = ensure_text(rr.get('value', ''))

        if xfrom == 'tx':
            rr['value'] = rr['value'].rstrip('.')

        if 'type' in rr and rr['type'] in VALUE_TYPES[xfrom]:
            return ["%s" % rr.get(v, '') for v in VALUE_TYPES[xfrom][rr['type']]]

        return rr['value']

    @staticmethod
    def _build_uniq_value(record, xfrom = 'tx', sep = ':'):
        value = CDNetworksCDNS._parse_value(record, xfrom)
        if not isinstance(value, list):
            return value

        value = sep.join(value)

        if value.strip(sep) == '':
            return ''

        return ensure_text(value)

    @staticmethod
    def _build_soa_record(entry, record):
        email = entry.get('email')

        if record.get('email') and '@' in record['email']:
            email = record['email']
        elif record.get('value') and '@' in record['value']:
            email = record['value']

        return {'recordId': entry['recordId'],
                'value': email.strip('. '),
                'type': 'SOA',
                'ttl': record.get('ttl', entry['ttl'])}

    @staticmethod
    def _is_frozen_record(action, record):
        if action in ('create', 'delete') \
           and record.get('type') == 'SOA':
            return True

        if record.get('type') == 'NS' \
           and record.get('hostName') == '@' \
           and record.get('value', '').rstrip('.') in DNS_SERVERS:
            return True

        return False

    def list_zones(self, page = 1, page_size = 25, name = None):
        params = {'page': page,
                  'pageSize': page_size}

        if name:
            params['name'] = name

        return self.mk_api_call(params = params)

    def search_zones(self, name, page = 1, page_size = 25):
        return self.mk_api_call(params = {'name': name,
                                          'page': page,
                                          'pageSsize': page_size})

    def get_zone_by_id(self, zone_id):
        r = self.mk_api_call("%s" % zone_id,
                             method = 'get')

        if r and r.get('data'):
            return r['data']

        return None

    def update_zone_ttl(self, zone_id, ttl):
        return self.mk_api_call("%s" % zone_id,
                                method = 'put',
                                data = {'ttl': ttl})

    def get_records(self, zone_id, record_type = None, record_id = None, host_name = None):
        params = {}
        path = "%s/records" % zone_id

        if record_id:
            path += "/%s" % record_id

        if host_name is not None:
            if host_name == '':
                host_name = '@'

            params['hostName'] = host_name

        if record_type:
            params['types'] = record_type

        return self.mk_api_call(path, method = 'get', params = params)

    def find_records(self, zone_id, record = None):
        if not record:
            record = {}

        r   = []
        rr  = record.copy()

        if rr.get('hostName') == '':
            rr['hostName'] = '@'

        res = self.get_records(zone_id,
                               rr.get('type'),
                               rr.get('recordId'),
                               rr.get('hostName'))

        if not res or 'data' not in res:
            return r

        ref = res['data']

        if rr.get('type'):
            if ref.get('type') == rr['type']:
                return [ref]

            if rr['type'] not in ref:
                return r

            r = list(ref[rr['type']])
        else:
            for rrvalue in itervalues(ref):
                for rrv in rrvalue:
                    r.append(rrv)

        value = self._build_uniq_value(rr, 'tx')

        if not rr.get('recordId') \
           and rr.get('hostName') is None \
           and not value:
            return r

        nr = list(r)

        for nrr in nr:
            if rr.get('recordId') \
               and int(nrr['recordId']) != int(rr['recordId']):
                r.remove(nrr)
                continue

            if rr.get('hostName') is not None \
               and nrr.get('hostName') is not None \
               and nrr['hostName'] != rr['hostName']:
                r.remove(nrr)
                continue

            if value and self._build_uniq_value(nrr, 'rx') != value:
                r.remove(nrr)

        return r

    def create_records(self, zone_id, records, deployment = False):
        r = {'result': None,
             'deploy': None}

        for record in records:
            if record['type'] in ('RP', 'SRV') and not record.get('value'):
                record['value'] = self._build_uniq_value(record, 'rx', ' ')

        r['result'] = self.mk_api_call("%s/records" % zone_id,
                                       method = 'post',
                                       data = records)

        if deployment:
            r['deploy'] = self.deployment(zone_id, deployment)

        return r

    def update_records(self, zone_id, records, record_id = None, deployment = False):
        r = {'result': None,
             'deploy': None}

        path = "%s/records" % zone_id

        if record_id:
            path += "/%s" % record_id

        for record in records:
            if record['type'] in ('RP', 'SRV') and not record.get('value'):
                record['value'] = self._build_uniq_value(record, 'rx', ' ')

        r['result'] = self.mk_api_call(path,
                                       method = 'put',
                                       data = records)

        if deployment:
            r['deploy'] = self.deployment(zone_id, deployment)

        return r

    def change_records(self, zone_id, records, deployment = False, force = False):
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

            if self._is_frozen_record(action, record):
                continue

            if action == 'create':
                actions['create'].append(record)
                continue

            if action == 'purge':
                if not record.get('type') or not record.get('hostName'):
                    raise ValueError("unable to purge, missing type or hostName for record: %r" % record)

                res = self.find_records(zone_id,
                                        record = {'type': record['type'],
                                                  'hostName': record['hostName']})
                if res:
                    for row in res:
                        actions['delete'][str(row['recordId'])] = row
                continue

            if action not in ('upsert', 'delete'):
                raise ValueError("action unknown: %r" % action)

            if not record.get('recordId') and record.get('hostName') is None:
                raise ValueError("missing recordId and hostName for record: %r" % record)

            if record.get('type') == 'SOA':
                res = self.find_records(zone_id, {'type': 'SOA'})
            else:
                res = self.find_records(zone_id, record)

            if res and len(res) == 1:
                if action == 'delete':
                    actions['delete'][str(res[0]['recordId'])] = res[0]
                    continue

                if not record.get('recordId'):
                    record['recordId'] = res[0]['recordId']

                if res[0]['type'] == 'SOA':
                    actions['update'].append(self._build_soa_record(res[0], record))
                else:
                    actions['update'].append(record)
            elif record.get('type') == 'SOA':
                continue
            elif action != 'upsert':
                if force and action == 'delete':
                    LOG.warning("unable to find record: %r", record)
                    continue
                raise LookupError("unable to find record: %r" % record)
            else:
                if record.get('type') in ('NS', 'TXT'):
                    if record.get('recordId'):
                        actions['update'].append(record)
                        continue

                    res = self.find_records(zone_id, record)
                    if res and len(res) == 1:
                        record['recordId'] = res[0]['recordId']
                        actions['update'].append(record)
                    else:
                        actions['create'].append(record)
                else:
                    res = self.find_records(zone_id, record)
                    if res and len(res) == 1:
                        actions['delete'][str(res[0]['recordId'])] = res[0]
                    actions['create'].append(record)

        for record in itervalues(actions['delete']):
            results['delete'].append(self.delete_record(zone_id, record['recordId']))

        for action in ('update', 'create'):
            for record in actions[action]:
                results[action].append(getattr(self, "%s_records" % action)(zone_id, [record]))

        if deployment:
            results['deploy'] = self.deployment(zone_id, deployment)

        return results

    def delete_record(self, zone_id, record_id, deployment = None):
        r = {'result': None,
             'deploy': None}

        path = "%s/records/%s" % (zone_id, record_id)

        r['result'] = self.mk_api_call(path,
                                       method = 'delete')

        if deployment:
            r['deploy'] = self.deployment(zone_id, deployment)

        return r

    def _mk_api_call_deployment(self, zone_id, timeout):
        res = self.mk_api_call("%s/deployment" % zone_id,
                               method = 'post',
                               timeout = timeout)

        if res and res.get('data') and res['data'].get('phase'):
            return res

        raise ValueError("unable to deploy to %r" % res)

    def deployment(self, zone_id, deployment = DEPLOY_TYPE_STAGING, timeout = _DEFAULT_DEPLOY_TIMEOUT):
        if deployment not in DEPLOY_TYPES:
            raise ValueError("invalid deployment type: %r" % deployment)

        zone = self.get_zone_by_id(zone_id)
        if not zone:
            raise LookupError("unable to find zone: %r" % zone_id)

        if deployment == DEPLOY_TYPE_STAGING:
            return self._mk_api_call_deployment(zone_id, timeout)

        res = self._mk_api_call_deployment(zone_id, timeout)
        if res['data']['phase'] == 'In production':
            return True

        if res['data']['phase'] == 'Sent to Stage':
            return self.deployment(zone_id, deployment, timeout)

        raise LookupError("unable to deploy, error unknown, zone: %r" % zone['data']['name'])


if __name__ != "__main__":
    def _start():
        SERVICES.register(CDNetworksCDNS())
    _start()
