from sqlalchemy import Column, Integer, ForeignKey, event
from sqlalchemy.orm import relationship, Session, backref

from core.interfaces.database.base import Base
from core.interfaces.database.const.table_name import TableNames
from core.interfaces.database.models.Media.anilist import AnilistMedia
from core.interfaces.database.models.Media.local_media import LocalMedia


class MediaRelations(Base):
    __tablename__ = TableNames.MediaRelations.value

    id = Column(Integer, primary_key=True, autoincrement=True)  # Internal ID

    anilist_id = Column(Integer, ForeignKey(f"{TableNames.AnilistMedia.value}.id", ondelete="SET NULL"), nullable=True,
                        unique=True)
    anilist = relationship(AnilistMedia)
    local_media = relationship(LocalMedia, uselist=True, lazy='select', viewonly=True,
                               backref=backref('media', uselist=False, viewonly=True))

    def is_valid(self):
        """ Check if the instance has all null values in relevant fields. """
        if self.anilist_id is None:
            return False
        return True

    @classmethod
    def before_flush_listener(cls, session: Session, flush_context, instances):
        for instance in session.new | session.dirty:
            if isinstance(instance, cls) and not instance.is_valid():
                # Delete any invalid entries
                session.delete(instance)


event.listen(Session, 'before_flush', MediaRelations.before_flush_listener)
