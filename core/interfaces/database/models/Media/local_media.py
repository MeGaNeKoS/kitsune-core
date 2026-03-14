import time

from sqlalchemy import Column, Integer, String, Float, Text, Enum, event
from sqlalchemy.orm import relationship, Session

from core.interfaces.database.base import Base
from core.interfaces.database.const.table_name import TableNames
from core.interfaces.database.types.media import MediaType, MediaStatus


class LocalMedia(Base):
    __tablename__ = TableNames.LocalMedia.value

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String, nullable=False)
    media_type = Column(Enum(MediaType), nullable=False, default=MediaType.ANIME)
    status = Column(Enum(MediaStatus), nullable=False, default=MediaStatus.PLANNED)
    progress = Column(Integer, nullable=False, default=0)
    total_episodes = Column(Integer, nullable=True)
    score = Column(Float, nullable=True)
    start_date = Column(Integer, nullable=True)  # unix timestamp
    end_date = Column(Integer, nullable=True)  # unix timestamp
    notes = Column(Text, nullable=True)
    file_path = Column(String, unique=True, nullable=True)
    created_at = Column(Integer, nullable=False, default=lambda: int(time.time()))
    updated_at = Column(Integer, nullable=False, default=lambda: int(time.time()),
                        onupdate=lambda: int(time.time()))

    # Relationships
    service_mappings = relationship("ServiceMediaMapping", back_populates="local_media",
                                   cascade="all, delete-orphan")

    @classmethod
    def before_flush_listener(cls, session: Session, flush_context, instances):
        for instance in session.dirty:
            if isinstance(instance, cls):
                instance.updated_at = int(time.time())


event.listen(Session, 'before_flush', LocalMedia.before_flush_listener)
