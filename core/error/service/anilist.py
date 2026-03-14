class AnilistError(Exception):
    """Base class for all Anilist exceptions."""
    pass


class AnilistUserError(AnilistError):
    """Base class for all Anilist User-related exceptions."""
    pass


class AnilistUserNoMediaCollectionError(AnilistUserError):
    """Exception for no media collection in Anilist user."""
    pass


class AnilistUserNotFoundError(AnilistUserError):
    """Exception for Anilist user not found."""
    pass


class AnilistMediaNotFoundError(AnilistUserError):
    """Exception for Anilist media not found."""
    pass


class AnilistNoUserError(AnilistUserError):
    """Exception for no Anilist user found."""
    pass


class AnilistNoRefreshUserError(AnilistUserError):
    """Exception for refresh error in Anilist user."""
    pass
