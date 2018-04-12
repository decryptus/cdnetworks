import logging

from cdnetworks.session import Session

DEFAULT_SESSION = None

def setup_default_session(**kwargs):
    global DEFAULT_SESSION
    DEFAULT_SESSION = Session(**kwargs)

def _get_default_session():
    if DEFAULT_SESSION is None:
        setup_default_session()

    return DEFAULT_SESSION

def service(name, **kwargs):
    return _get_default_session(**kwargs).service(name)
