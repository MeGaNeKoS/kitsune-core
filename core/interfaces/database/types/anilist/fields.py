from typing import TypedDict, Optional, List, Dict

from core.interfaces.database.types.anilist import User
from core.interfaces.database.types.anilist.enums import AnilistMediaListStatus


class TokenResponse(TypedDict):
    token_type: str
    expires_in: int
    access_token: str
    refresh_token: str


class TransformedTokenResponse(TypedDict):
    token_type: str
    expired_at: Optional[float]
    access_token: str
    refresh_token: str


class AnilistCredsInfo(TypedDict):
    token_data: TransformedTokenResponse
    user_data: User


class PageInfo(TypedDict):
    total: int
    currentPage: int
    perPage: int
    hasNextPage: bool


class DefaultMediaTitleFields(TypedDict):
    romaji: str
    english: str
    native: str


class DefaultAiringScheduleFields(TypedDict):
    airingAt: int
    episode: int


class FuzzyDate(TypedDict):
    year: int
    month: int
    day: int


class Trailer(TypedDict):
    id: str
    site: str
    thumbnail: str


class CoverImage(TypedDict):
    extraLarge: str
    large: str
    medium: str
    color: str


class DefaultMediaFields(TypedDict):
    id: int
    idMal: int
    type: str
    format: str
    status: str
    description: str
    startDate: FuzzyDate
    endDate: FuzzyDate
    season: str
    seasonYear: int
    episodes: int
    duration: int
    chapters: int
    volumes: int
    countryOfOrigin: str
    isLicensed: bool
    source: str
    hashtag: str
    trailer: Trailer
    updatedAt: int
    coverImage: CoverImage
    bannerImage: str
    genres: List[str]
    synonyms: List[str]
    averageScore: int
    meanScore: int
    popularity: int
    isLocked: bool
    trending: int
    isFavouriteBlocked: bool
    isAdult: bool
    siteUrl: str
    modNotes: str
    title: DefaultMediaTitleFields
    nextAiringEpisode: DefaultAiringScheduleFields


class DefaultUserEntryFields(TypedDict):
    id: int
    userId: int
    mediaId: int
    status: AnilistMediaListStatus
    score: float
    progress: int
    progressVolumes: int
    repeat: int
    priority: int
    private: bool
    notes: str
    hiddenFromStatusLists: bool
    customLists: List
    advancedScores: Dict
    startedAt: FuzzyDate
    completedAt: FuzzyDate
    updatedAt: int
    createdAt: int
