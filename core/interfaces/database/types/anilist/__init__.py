from typing import TypedDict, Optional

from core.interfaces.database.types.anilist.enums import UserTitleLanguage, ScoreFormat


class UserAvatar(TypedDict):
    large: Optional[str]
    medium: Optional[str]


class UserOptions(TypedDict):
    titleLanguage: UserTitleLanguage
    displayAdultContent: bool


class MediaListTypeOptions(TypedDict):
    sectionOrder: list[str]
    splitCompletedSectionByFormat: bool
    customLists: list[str]
    advancedScoring: list[str]
    advancedScoringEnabled: bool


class MediaListOptions(TypedDict):
    scoreFormat: ScoreFormat
    rowOrder: str
    useLegacyLists: bool
    animeList: MediaListTypeOptions
    mangaList: MediaListTypeOptions


class User(TypedDict):
    id: int
    name: str
    about: Optional[str]
    avatar: UserAvatar
    bannerImage: Optional[str]
    options: UserOptions
    mediaListOptions: MediaListOptions
