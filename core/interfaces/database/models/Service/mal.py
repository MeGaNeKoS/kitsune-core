"""MAL user list entry - stores the user's anime list entries from MyAnimeList."""

from datetime import datetime

from sqlalchemy import Column, Integer, ForeignKey, Float, String, Boolean, JSON, event
from sqlalchemy.orm import relationship
from sqlalchemy.orm.attributes import get_history

from core.interfaces.database.base import Base
from core.interfaces.database.const.table_name import TableNames
from core.interfaces.database.models.Media.mal import MALMedia


class MALUserEntry(Base):
    __tablename__ = TableNames.MALUser.value

    # MAL doesn't have a list entry ID separate from media ID,
    # so we use (user_id, media_id) as composite PK
    user_id = Column(ForeignKey(f'{TableNames.ServiceCreds.value}.identifier'), primary_key=True)
    media_id = Column(Integer, ForeignKey(f'{TableNames.MALMedia.value}.id'), primary_key=True)
    media = relationship(MALMedia, uselist=False, lazy='select', viewonly=True)

    status = Column(String)  # watching, completed, on_hold, dropped, plan_to_watch
    score = Column(Integer)  # 0-10
    progress = Column(Integer)  # num_episodes_watched
    is_rewatching = Column(Boolean, default=False)
    num_times_rewatched = Column(Integer, default=0)
    priority = Column(Integer, default=0)
    tags = Column(String, default="")
    comments = Column(String, default="")
    updated_at = Column(Integer)  # Unix timestamp

    # Local sync tracking (same pattern as AnilistUserEntry)
    local_updated_at = Column(Integer)
    is_deleted = Column(Boolean, default=False)
    updated_fields = Column(JSON)

    tracked_fields = ['status', 'score', 'progress', 'is_rewatching',
                      'num_times_rewatched', 'updated_at']

    @classmethod
    def parse_data(cls, data: dict, user_id: str) -> 'MALUserEntry':
        """Parse MAL API response into a MALUserEntry instance."""
        status_data = data.get("my_list_status") or data.get("list_status") or {}
        updated = status_data.get("updated_at", "")

        # Convert ISO timestamp to unix
        updated_ts = 0
        if updated:
            try:
                from datetime import datetime as dt
                updated_ts = int(dt.fromisoformat(updated.replace("Z", "+00:00")).timestamp())
            except Exception:
                pass

        return cls(
            user_id=user_id,
            media_id=data.get("id") or data.get("node", {}).get("id"),
            status=status_data.get("status", "plan_to_watch"),
            score=status_data.get("score", 0),
            progress=status_data.get("num_episodes_watched", 0),
            is_rewatching=status_data.get("is_rewatching", False),
            num_times_rewatched=status_data.get("num_times_rewatched", 0),
            priority=status_data.get("priority", 0),
            tags=status_data.get("tags", ""),
            comments=status_data.get("comments", ""),
            updated_at=updated_ts,
            local_updated_at=updated_ts,
            is_deleted=False,
            updated_fields={},
        )

    @staticmethod
    def track_changes(mapper, connection, target):
        if target.updated_fields is None:
            target.updated_fields = {}

        for column in MALUserEntry.tracked_fields:
            hist = get_history(target, column)
            if hist.has_changes():
                target.updated_fields[column] = getattr(target, column)

        if target.updated_fields:
            target.local_updated_at = int(datetime.now().timestamp())


event.listen(MALUserEntry, 'before_update', MALUserEntry.track_changes)
