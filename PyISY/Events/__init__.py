from .events import EventStream
from .eventsSSL import SSLEventStream

def get_stream(use_https):
    if use_https:
        return SSLEventStream
    else:
        return EventStream
