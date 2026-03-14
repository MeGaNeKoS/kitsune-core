from typing import Tuple

from sqlalchemy import Column, Integer, String, ForeignKey, JSON, Boolean, Enum
from sqlalchemy.orm import relationship, backref, Session

from core.interfaces.database.base import Base
from core.interfaces.database.const.anilist import QueryNames
from core.interfaces.database.const.table_name import TableNames
from core.interfaces.database.types.anilist.enums import AnilistMediaType, AnilistMediaFormat, AnilistMediaStatus, \
    AnilistMediaSeason, AnilistMediaSource


class AnilistMediaTitle(Base):
    __tablename__ = TableNames.AnilistMediaTitle.value

    media_id = Column(Integer, ForeignKey(f'{TableNames.AnilistMedia.value}.id', ondelete="CASCADE"), primary_key=True)
    romaji = Column(String)
    english = Column(String)
    native = Column(String)

    _fragment = f"""fragment {QueryNames.MediaTitleFragmentNames.value} on MediaTitle {{
  romaji
  english
  native
}}""".strip()

    @classmethod
    def fragment(cls):
        return cls._fragment


class AnilistAiringSchedule(Base):
    __tablename__ = TableNames.AnilistAiringSchedule.value
    """
    This table is used for scheduler as well to automatically update the media entry.
    """
    airingAt = Column(Integer, nullable=False)
    episode = Column(Integer, nullable=False)
    media_id = Column(Integer, ForeignKey(f"{TableNames.AnilistMedia.value}.id", ondelete="CASCADE"), primary_key=True)

    _fragment = f"""fragment {QueryNames.MediaAiringScheduleFragmentName.value} on AiringSchedule {{
    airingAt
    episode
}}""".strip()

    @classmethod
    def fragment(cls):
        return cls._fragment


class AnilistMedia(Base):
    __tablename__ = TableNames.AnilistMedia.value

    id = Column(Integer, primary_key=True)
    idMal = Column(Integer)

    title = relationship(AnilistMediaTitle, backref=backref("media", lazy="select"), uselist=False, lazy="joined")

    type = Column(Enum(AnilistMediaType))
    format = Column(Enum(AnilistMediaFormat))
    status = Column(Enum(AnilistMediaStatus))
    description = Column(String)
    startDate = Column(JSON)
    endDate = Column(JSON)
    season = Column(Enum(AnilistMediaSeason))
    seasonYear = Column(Integer)
    episodes = Column(Integer)
    duration = Column(Integer)
    chapters = Column(Integer)
    volumes = Column(Integer)
    countryOfOrigin = Column(String)  # ISO 3166-1 alpha-2 country code
    isLicensed = Column(Boolean)
    source = Column(Enum(AnilistMediaSource))
    hashtag = Column(String)
    trailer = Column(JSON)
    updatedAt = Column(Integer)
    coverImage = Column(JSON)
    bannerImage = Column(String)
    genres = Column(JSON)
    synonyms = Column(JSON)
    averageScore = Column(Integer)
    meanScore = Column(Integer)
    popularity = Column(Integer)
    isLocked = Column(Boolean)
    trending = Column(Integer)
    # tags, relations, characters, staff, studios, etc., need to be defined if they are special types or relationships
    isFavouriteBlocked = Column(Boolean, nullable=False, default=False)
    isAdult = Column(Boolean)
    # nextAiringEpisode, airingSchedule, trends, etc., need to be defined if they are special types or relationships
    nextAiringEpisode = relationship(AnilistAiringSchedule, backref=backref("media", lazy="select"),
                                     uselist=False, lazy="joined")
    siteUrl = Column(String)
    modNotes = Column(String)

    _fragment = f"""fragment {QueryNames.MediaFragmentName.value} on Media {{
    id
    idMal
    type
    format
    status
    description
    startDate {{
        year
        month
        day
    }}
    endDate {{
        year
        month
        day
    }}
    season
    seasonYear
    episodes
    duration
    chapters
    volumes
    countryOfOrigin
    isLicensed
    source
    hashtag
    trailer {{
        id
        site
        thumbnail
    }}
    updatedAt
    coverImage {{
        extraLarge
        large
        medium
        color
    }}
    bannerImage
    genres
    synonyms
    averageScore
    meanScore
    popularity
    isLocked
    trending
    isFavouriteBlocked
    isAdult
    siteUrl
    modNotes
    title {{
        ...{QueryNames.MediaTitleFragmentNames.value}
    }}
    nextAiringEpisode {{
        ...{QueryNames.MediaAiringScheduleFragmentName.value}
    }}
}}
{AnilistMediaTitle.fragment()}
{AnilistAiringSchedule.fragment()}""".strip()

    @classmethod
    def parse_data(cls, data: dict) -> Tuple['AnilistMedia', 'AnilistMediaTitle', 'AnilistAiringSchedule']:
        """
        This method parses the data from the API and returns a tuple of AnilistMedia, AnilistMediaTitle and
        AnilistAiringSchedule.
        The caller should save the data to the database. manually if using this method.
        :param data: Dictionary containing media item data.
        :return:
        """
        media = cls(id=data.get('id'),
                    idMal=data.get('idMal'),
                    type=data.get('type'),
                    format=data.get('format'),
                    status=data.get('status'),
                    description=data.get('description'),
                    startDate=data.get('startDate'),
                    endDate=data.get('endDate'),
                    season=data.get('season'),
                    seasonYear=data.get('seasonYear'),
                    episodes=data.get('episodes'),
                    duration=data.get('duration'),
                    chapters=data.get('chapters'),
                    volumes=data.get('volumes'),
                    countryOfOrigin=data.get('countryOfOrigin'),
                    isLicensed=data.get('isLicensed'),
                    source=data.get('source'),
                    hashtag=data.get('hashtag'),
                    trailer=data.get('trailer'),
                    updatedAt=data.get('updatedAt'),
                    coverImages=data.get('coverImage'),
                    bannerImage=data.get('bannerImage'),
                    genres=data.get('genres'),
                    synonyms=data.get('synonyms'),
                    averageScore=data.get('averageScore'),
                    meanScore=data.get('meanScore'),
                    popularity=data.get('popularity'),
                    isLocked=data.get('isLocked'),
                    trending=data.get('trending'),
                    isFavouriteBlocked=data.get('isFavouriteBlocked'),
                    isAdult=data.get('isAdult'),
                    siteUrl=data.get('siteUrl'),
                    modNotes=data.get('modNotes')
                    )

        title_data = data.get('title')
        title = AnilistMediaTitle(media_id=data.get('id'),
                                  romaji=title_data.get('romaji'),
                                  english=title_data.get('english'),
                                  native=title_data.get('native')
                                  )

        airing_data = data.get('nextAiringEpisode')
        next_airing_schedule = AnilistAiringSchedule(media_id=data.get('id'),
                                                     airingAt=airing_data.get('airingAt'),
                                                     episode=airing_data.get('episode')
                                                     )
        return media, title, next_airing_schedule

    @classmethod
    def parse_store_data(cls, data: dict, session: Session) -> 'AnilistMedia':
        """
        Parses a dictionary of data and returns an instance of AnilistMedia.
        :param data: Dictionary containing media item data.
        :param session: SQLAlchemy session.
        :return: An instance of AnilistMedia.
        """

        media, title, next_airing_schedule = cls.parse_data(data)

        session.merge(media)
        session.merge(title)
        session.merge(next_airing_schedule)

        return media

    @classmethod
    def fragment(cls):
        return cls._fragment
