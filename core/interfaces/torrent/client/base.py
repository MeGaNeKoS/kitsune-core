import logging
from abc import ABC
from enum import Enum

from core.interfaces.torrent.client.enums import ClientMapping, DownloadStrategy, ClientDefault


class BaseClient(ABC):
    """
    This is the base class for all clients.
    Any method that called from the service(Download) thread should be implemented here.
    Otherwise, it should be implemented in the client class.
    """
    _name = None

    class AuthConfig(Enum):
        pass

    class CustomConfig(Enum):
        pass

    def __init__(self, **kwargs):
        self._logger = logging.getLogger(self.__module__)

        strategy = kwargs.pop(ClientMapping.DOWNLOAD_STRATEGY.value, DownloadStrategy.NORMAL.value)
        try:
            self.download_strategy = DownloadStrategy(strategy)
        except ValueError:
            self._logger.warning(
                f'Invalid download strategy: {strategy}, using {DownloadStrategy.NORMAL.value} instead.')
            self.download_strategy = DownloadStrategy.NORMAL

        self.base_retry_wait_second = kwargs.pop(ClientMapping.BASE_RETRY_WAIT_SECOND.value,
                                                 ClientDefault.BASE_RETRY_WAIT_SECOND.value)
        self.max_retry_wait_second = kwargs.pop(ClientMapping.MAX_RETRY_WAIT_SECOND.value,
                                                ClientDefault.MAX_RETRY_WAIT_SECOND.value)
        self.max_retries = kwargs.pop(ClientMapping.MAX_RETRY.value, ClientDefault.MAX_RETRY.value)
        # Additional config for client class.
        # For example, qbittorrent can have "category" and "tags" config
        self.config = kwargs.pop(ClientMapping.CONFIG.value, ClientDefault.CONFIG.value)
        # The following config required for reconnection upon changing the config
        # How the client initialized, like host, port, username, password.
        self.client_auth = kwargs.pop(ClientMapping.CLIENT_AUTH.value, ClientDefault.CLIENT_AUTH.value)
        self._wait_time = 1 / kwargs.pop(ClientMapping.REQUEST_PER_SECOND.value,
                                         ClientDefault.REQUEST_PER_SECOND.value)

        self.program_path = kwargs.pop(ClientMapping.PROGRAM_PATH.value,
                                       ClientDefault.PROGRAM_PATH.value)  # Program path attribute
        # Log unused kwargs
        for key, value in kwargs.items():
            self._logger.warning(f'Unused key in kwargs: [{key}] -> "{value}"')

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        if cls._name is None:
            raise NotImplementedError("Subclasses must define a '_name' attribute")
        if cls.AuthConfig is BaseClient.AuthConfig or not issubclass(cls.AuthConfig, Enum):
            raise NotImplementedError("Subclasses must define their own 'AuthConfig' Enum")
        if cls.CustomConfig is BaseClient.CustomConfig or not issubclass(cls.CustomConfig, Enum):
            raise NotImplementedError("Subclasses must define their own 'CustomConfig' Enum")

    @property
    def request_per_second(self):
        return 1 / self._wait_time

    @request_per_second.setter
    def request_per_second(self, value):
        self._wait_time = 1 / value

    def to_dict(self):
        """
        Convert the client to a json object.
        """
        return {
            ClientMapping.NAME.value: self._name,
            ClientMapping.BASE_RETRY_WAIT_SECOND.value: self.base_retry_wait_second,
            ClientMapping.CONFIG.value: self.config,
            ClientMapping.CLIENT_AUTH.value: self.client_auth,
            ClientMapping.DOWNLOAD_STRATEGY.value: self.download_strategy.value,
            ClientMapping.MAX_RETRY.value: self.max_retries,
            ClientMapping.MAX_RETRY_WAIT_SECOND.value: self.max_retry_wait_second,
            ClientMapping.PROGRAM_PATH.value: self.program_path,
            ClientMapping.REQUEST_PER_SECOND.value: self.request_per_second,
        }

    @classmethod
    def get_name(cls):
        """
        The internal name of the client.
        """
        return cls._name
