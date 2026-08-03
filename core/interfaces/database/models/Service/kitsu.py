"""Kitsu user list entry - stores the user's anime list entries from Kitsu."""

from datetime import datetime

from sqlalchemy import Column, Integer, ForeignKey, Float, String, Boolean, JSON, event
from sqlalchemy.orm import relationship
from sqlalchemy.orm.attributes import get_history

from core.interfaces.database.base import Base
from core.interfaces.database.const.table_name import TableNames
from core.interfaces.database.models.Media.kitsu import KitsuMedia


class KitsuUserEntry(Base):
    __tablename__ = TableNames.KitsuUser.value

    # Kitsu library entries have their own ID
    id = Column(Integer, primary_key=True)

    user_id = Column(ForeignKey(f'{TableNames.ServiceCreds.value}.identifier'), primary_key=True)
    media_id = Column(Integer, ForeignKey(f'{TableNames.KitsuMedia.value}.id'), primary_key=True)
    media = relationship(KitsuMedia, uselist=False, lazy='select', viewonly=True)

    status = Column(String)     # current, completed, on_hold, dropped, planned
    progress = Column(Integer)  # episodes watched
    score = Column(Float)       # rating (Kitsu uses various rating systems, store raw)
    is_reconsuming = Column(Boolean, default=False)
    reconsume_count = Column(Integer, default=0)
    notes = Column(String, default="")
    updated_at = Column(Integer)  # Unix timestamp

    # Local sync tracking (same pattern as AnilistUserEntry and MALUserEntry)
    local_updated_at = Column(Integer)
    is_deleted = Column(Boolean, default=False)
    updated_fields = Column(JSON)

    tracked_fields = ['status', 'progress', 'score', 'is_reconsuming',
                      'reconsume_count', 'updated_at']

    @classmethod
    def parse_data(cls, data: dict, user_id: str) -> 'KitsuUserEntry':
        """Parse Kitsu API response into a KitsuUserEntry instance.

        Expects data in the form:
            {"id": ..., "attributes": {"status": ..., "progress": ..., "ratingTwenty": ..., ...},
             "relationships": {"anime": {"data": {"id": ...}}}}
        Or a pre-normalized dict with top-level keys.
        """
        attrs = data.get("attributes", data)
        # Get media_id from relationships or directly
        media_id = None
        rels = data.get("relationships", {})
        anime_rel = rels.get("anime", {}).get("data", {})
        if anime_rel:
            media_id = int(anime_rel.get("id", 0))
        if not media_id:
            media_id = data.get("media_id") or attrs.get("media_id")

        # Parse updated_at
        updated = attrs.get("updatedAt") or attrs.get("updated_at", "")
        updated_ts = 0
        if updated:
            try:
                from datetime import datetime as dt
                if isinstance(updated, str):
                    updated_ts = int(dt.fromisoformat(updated.replace("Z", "+00:00")).timestamp())
                elif isinstance(updated, (int, float)):
                    updated_ts = int(updated)
            except Exception:
                pass

        return cls(
            id=int(data.get("id", 0)),
            user_id=user_id,
            media_id=media_id,
            status=attrs.get("status", "planned"),
            progress=attrs.get("progress", 0),
            score=attrs.get("ratingTwenty") or attrs.get("score"),
            is_reconsuming=attrs.get("reconsuming", False),
            reconsume_count=attrs.get("reconsumeCount", 0),
            notes=attrs.get("notes", ""),
            updated_at=updated_ts,
            local_updated_at=updated_ts,
            is_deleted=False,
            updated_fields={},
        )

    @staticmethod
    def track_changes(mapper, connection, target):
        if target.updated_fields is None:
            target.updated_fields = {}

        for column in KitsuUserEntry.tracked_fields:
            hist = get_history(target, column)
            if hist.has_changes():
                target.updated_fields[column] = getattr(target, column)

        if target.updated_fields:
            target.local_updated_at = int(datetime.now().timestamp())


event.listen(KitsuUserEntry, 'before_update', KitsuUserEntry.track_changes)
