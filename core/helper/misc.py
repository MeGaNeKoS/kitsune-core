import threading


def sort_dict(d):
    """ Recursively sort dictionary keys. """
    if isinstance(d, dict):
        return {k: sort_dict(v) for k, v in sorted(d.items())}
    elif isinstance(d, list):
        return [sort_dict(v) for v in d]
    else:
        return d


class TokenContainer:
    """
    A thread-safe container for storing and sharing a token between threads.

    This container is designed for use in scenarios where a token needs to be
    accessed or modified by multiple threads safely. It is particularly useful
    in OAuth processes where a token is exchanged between a server and a
    client/main application thread.

    Attributes:
        lock (threading.RLock): A reentrant lock for ensuring thread-safe operations.
        _token: The token that is stored in the container. It's private to enforce access through getter and setter.

    Methods:
        token: Property method to get or set the token value in a thread-safe manner.
    """

    def __init__(self):
        self.lock = threading.RLock()
        self._token = None

    @property
    def token(self):
        """
        The token property, provides a thread-safe way to access or update the token.

        Returns:
            The current value of the token.

        When setting the token, ensures that the token update is thread-safe.
        """
        with self.lock:
            return self._token

    @token.setter
    def token(self, token):
        """
        Sets the token in a thread-safe manner.

        Parameters:
            token: The new value to set for the token.
        """
        with self.lock:
            self._token = token
