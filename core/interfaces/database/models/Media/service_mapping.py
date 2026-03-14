from sqlalchemy import Column, Integer, String, Enum, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from core.interfaces.database.base import Base
from core.interfaces.database.const.service import ServiceName
from core.interfaces.database.const.table_name import TableNames


class ServiceMediaMapping(Base):
    __tablename__ = TableNames.ServiceMediaMapping.value

    id = Column(Integer, primary_key=True, autoincrement=True)
    local_media_id = Column(Integer,
                            ForeignKey(f"{TableNames.LocalMedia.value}.id", ondelete="CASCADE"),
                            nullable=False)
    service_name = Column(Enum(ServiceName), nullable=False)
    service_media_id = Column(String, nullable=False)

    __table_args__ = (
        UniqueConstraint("local_media_id", "service_name",
                         name="uq_local_service"),
    )

    # Relationships
    local_media = relationship("LocalMedia", back_populates="service_mappings")
