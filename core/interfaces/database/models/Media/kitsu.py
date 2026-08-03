"""Kitsu media metadata cache - stores anime data fetched from Kitsu API."""

from sqlalchemy import Column, Integer, String, Float, JSON

from core.interfaces.database.base import Base
from core.interfaces.database.const.table_name import TableNames


class KitsuMedia(Base):
    __tablename__ = TableNames.KitsuMedia.value

    id = Column(Integer, primary_key=True)  # Kitsu anime ID
    title = Column(String)
    canonical_title = Column(String)
    titles = Column(JSON)         # {"en": ..., "en_jp": ..., "ja_jp": ...}
    poster_image = Column(JSON)   # {"tiny": url, "small": url, "medium": url, "large": url, "original": url}
    cover_image = Column(JSON)    # {"tiny": url, "small": url, "large": url, "original": url}
    media_type = Column(String)   # TV, movie, OVA, ONA, special, music
    status = Column(String)       # current, finished, tba, unreleased, upcoming
    episode_count = Column(Integer)
    average_rating = Column(Float)
    synopsis = Column(String)
    start_date = Column(String)   # YYYY-MM-DD
    end_date = Column(String)
    subtype = Column(String)      # TV, movie, OVA, ONA, special, music

    @classmethod
    def from_api(cls, data: dict, session) -> "KitsuMedia":
        """Parse Kitsu API response and store/update in DB."""
        attrs = data.get("attributes", data)
        poster = attrs.get("posterImage") or {}
        cover = attrs.get("coverImage") or {}

        media = cls(
            id=int(data.get("id", 0)),
            title=attrs.get("canonicalTitle", ""),
            canonical_title=attrs.get("canonicalTitle", ""),
            titles=attrs.get("titles"),
            poster_image=poster if isinstance(poster, dict) else {},
            cover_image=cover if isinstance(cover, dict) else {},
            media_type=attrs.get("showType", ""),
            status=attrs.get("status", ""),
            episode_count=attrs.get("episodeCount"),
            average_rating=float(attrs["averageRating"]) if attrs.get("averageRating") else None,
            synopsis=attrs.get("synopsis", ""),
            start_date=attrs.get("startDate", ""),
            end_date=attrs.get("endDate", ""),
            subtype=attrs.get("subtype", ""),
        )
        session.merge(media)
        return media
