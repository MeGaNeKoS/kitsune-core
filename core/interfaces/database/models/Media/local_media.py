from sqlalchemy import Column, Integer, ForeignKey, String

from core.interfaces.database import Base
from core.interfaces.database.const.table_name import TableNames


class LocalMedia(Base):
    __tablename__ = TableNames.LocalMedia.value

    media_id = Column(Integer,
                      ForeignKey(f"{TableNames.MediaRelations.value}.id", ondelete="CASCADE"),
                      nullable=False,
                      unique=True)
    sequence_number = Column(Integer, unique=True)
    file_path = Column(String, unique=True)
