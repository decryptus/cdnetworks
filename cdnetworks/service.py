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
