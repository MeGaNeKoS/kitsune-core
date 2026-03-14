import logging
import threading
import time

from core.interfaces.torrent.client.client import Client
from core.interfaces.torrent.client.enums import ClientMapping, ClientDefault, DownloadStrategy, ClientConfig


class RateLimitedClient:
    """
    This class is used to limit the rate of calls to the client.
    Some clients may not return the correct information if the calls are too fast.
    Or under heavy load.
    """
    _sync_event = threading.Event()

    module_logger = logging.getLogger(__name__)

    def __init__(self, client, rate_limit):
        self.client = client
        self.rate_limit = rate_limit * 1000  # convert to milliseconds
        self.last_call = time.time()
        self._sync_lock = threading.RLock()

    def __getattr__(self, attr):
        func = self.client.__getattribute__(attr)

        if not callable(func):
            return func

        def hooked(*args, **kwargs):
            with self._sync_lock:
                elapsed_time = time.time() - self.last_call
                wait_time = self.rate_limit / 1000 - elapsed_time
                if wait_time > 0:
                    self._sync_event.wait(timeout=wait_time)

                if self._sync_event.is_set():
                    self.module_logger.info("Client is shutting down, aborting call")
                    return

                result = func(*args, **kwargs)
                self.last_call = time.time()

                return result

        return hooked

    @classmethod
    def shutdown(cls):
        cls._sync_event.set()
