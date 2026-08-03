import time

from sqlalchemy import Column, Integer, String, ForeignKey

from core.interfaces.database.base import Base
from core.interfaces.database.const.table_name import TableNames


class TitleAlias(Base):
    """User-defined synonym: maps a normalized detected title to a local library entry.

    When the user corrects a misdetection, the detected title is stored here
    so future detections of the same title resolve instantly.
    """

    __tablename__ = TableNames.TitleAlias.value

    id = Column(Integer, primary_key=True, autoincrement=True)
    normalized_title = Column(String, nullable=False, unique=True, index=True)
    local_media_id = Column(
        Integer,
        ForeignKey(f"{TableNames.LocalMedia.value}.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at = Column(Integer, nullable=False, default=lambda: int(time.time()))
