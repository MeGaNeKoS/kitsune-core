class RejectError(Exception):
    """Raised when there is a reject condition."""
    pass


class NotFoundError(Exception):
    """Raised when there is a reject condition."""
    pass


class ThreadTermination(Exception):
    """
    Raised when a thread want to refused to run due to some critical configuration error.
    """
    pass
