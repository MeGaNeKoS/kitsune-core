from sqlalchemy import Column, Enum, JSON, String, event, Connection, and_
from sqlalchemy.orm import Mapper, Session, relationship, foreign, backref

from core.interfaces.database.base import Base
from core.interfaces.database.const.service import ServiceName
from core.interfaces.database.const.table_name import TableNames
from core.interfaces.database.models.Service.anilist import AnilistUserEntry


class ServiceCreds(Base):
    """
    ServiceCreds model, used to store credentials for various services.
        This is a composite PK table, with the PK being (identifier, service_name).
        This is to allow multiple users to use the same service, and to allow a user to use multiple services.

    This might be changed in the future, each service might have their own table, but for now this is fine.
    """
    __tablename__ = TableNames.ServiceCreds.value

    identifier = Column(String, nullable=False, primary_key=True)
    service_name = Column(Enum(ServiceName), nullable=False, primary_key=True)
    additional_info = Column(JSON)

    anilist_entries = relationship(AnilistUserEntry, uselist=True, lazy='select', viewonly=True,
                                   primaryjoin=and_(identifier == foreign(AnilistUserEntry.user_id),
                                                    service_name == ServiceName.ANILIST),
                                   backref=backref('user', uselist=False, viewonly=True),
                                   )

    @property
    def entries(self):
        if self.service_name == ServiceName.ANILIST:
            return self.anilist_entries
        return None

    @staticmethod
    def after_delete_listener(mapper: Mapper, connection: Connection, target: 'ServiceCreds'):
        """
            Listener to act after a ServiceCreds instance is deleted.
            This required due to we cant set a cascade delete when we only part of the composite PK on the Entry table.
            And storing both of them as FK would be redundant, and storage inefficient.
        """
        if target.service_name == ServiceName.ANILIST:
            with Session(bind=connection) as session:
                session.query(AnilistUserEntry).filter_by(user_id=target.identifier).delete()
                session.commit()


event.listen(ServiceCreds, 'after_delete', ServiceCreds.after_delete_listener)
