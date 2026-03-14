class ServerError(Exception):
    """Base class for server-related exceptions."""
    pass


class ServerRunningError(ServerError):
    """Exception for errors occurring while the server is running."""
    pass


class ClientSecretNotProvidedError(ServerError):
    """Exception for missing client secret."""
    pass


class ServerFailedToStartError(ServerError):
    """Exception for failure to start the server."""
    pass
