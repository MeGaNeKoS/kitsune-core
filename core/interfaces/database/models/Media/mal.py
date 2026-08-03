"""MAL media metadata cache - stores anime data fetched from MyAnimeList API."""

from sqlalchemy import Column, Integer, String, Float, JSON

from core.interfaces.database.base import Base
from core.interfaces.database.const.table_name import TableNames


class MALMedia(Base):
    __tablename__ = TableNames.MALMedia.value

    id = Column(Integer, primary_key=True)  # MAL anime ID
    title = Column(String)
    picture = Column(JSON)        # {"medium": url, "large": url}
    media_type = Column(String)   # tv, movie, ova, ona, special, music
    status = Column(String)       # finished_airing, currently_airing, not_yet_aired
    num_episodes = Column(Integer)
    mean = Column(Float)          # Average score 0-10
    synopsis = Column(String)
    season = Column(String)       # spring, summer, fall, winter
    season_year = Column(Integer)
    genres = Column(JSON)         # ["Action", "Adventure", ...]
    studios = Column(JSON)        # ["Studio Name", ...]
    source = Column(String)       # manga, light_novel, original, etc.
    rating = Column(String)       # pg_13, r, etc.

    @classmethod
    def from_api(cls, data: dict, session) -> "MALMedia":
        """Parse MAL API response and store/update in DB."""
        pic = data.get("main_picture") or data.get("picture") or {}
        season_data = data.get("start_season", {})
        genres_raw = data.get("genres", [])
        studios_raw = data.get("studios", [])

        media = cls(
            id=data.get("id"),
            title=data.get("title", ""),
            picture=pic if isinstance(pic, dict) else {"medium": str(pic)},
            media_type=data.get("media_type") or data.get("format", "").lower(),
            status=data.get("status", ""),
            num_episodes=data.get("num_episodes") or data.get("episodes"),
            mean=data.get("mean"),
            synopsis=data.get("synopsis") or data.get("description", ""),
            season=season_data.get("season", "") if isinstance(season_data, dict) else "",
            season_year=season_data.get("year") if isinstance(season_data, dict) else None,
            genres=[g.get("name", g) if isinstance(g, dict) else str(g) for g in genres_raw],
            studios=[s.get("name", s) if isinstance(s, dict) else str(s) for s in studios_raw],
            source=data.get("source", ""),
            rating=data.get("rating", ""),
        )
        session.merge(media)
        return media
