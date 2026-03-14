from datetime import datetime

from sqlalchemy import Column, Integer, ForeignKey, Float, Boolean, Text, JSON, Enum, event
from sqlalchemy.orm import relationship
from sqlalchemy.orm.attributes import get_history

from core.interfaces.database.base import Base
from core.interfaces.database.const.anilist import QueryNames
from core.interfaces.database.const.table_name import TableNames
from core.interfaces.database.models.Media import AnilistMedia
from core.interfaces.database.types.anilist.enums import AnilistMediaListStatus


class AnilistUserEntry(Base):
    __tablename__ = TableNames.AnilistUser.value
    id = Column(Integer, primary_key=True)

    user_id = Column(ForeignKey(f'{TableNames.ServiceCreds.value}.identifier'), primary_key=True)

    media_id = Column(Integer, ForeignKey(f'{TableNames.AnilistMedia.value}.id'), primary_key=True)
    media = relationship(AnilistMedia, uselist=False, lazy='select', backref='users', viewonly=True)

    status = Column(Enum(AnilistMediaListStatus))
    scoreRaw = Column(Float)
    progress = Column(Integer)
    progress_volumes = Column(Integer)
    repeat = Column(Integer)
    priority = Column(Integer)
    private = Column(Boolean)
    notes = Column(Text)
    hidden_from_status_lists = Column(Boolean)
    custom_lists = Column(JSON)
    advanced_scores = Column(JSON)
    started_at = Column(JSON)
    completed_at = Column(JSON)
    updated_at = Column(Integer)
    created_at = Column(Integer)

    # Local data to track sync status
    local_updated_at = Column(Integer)
    # To mark that the entry is deleted but not synced yet
    is_deleted = Column(Boolean, default=False)
    # Tracks fields updated locally for synchronization
    updated_fields = Column(JSON)

    _fragment = f"""fragment {QueryNames.MediaListFragmentName.value} on MediaList {{
            id
            userId
            mediaId
            status
            score(format: POINT_100)
            progress
            progressVolumes
            repeat
            priority
            private
            notes
            hiddenFromStatusLists
            customLists(asArray: true)
            advancedScores
            startedAt {{
                year
                month
                day
            }}
            completedAt {{
                year
                month
                day
            }}
            updatedAt
            createdAt
        }}""".strip()

    tracked_fields = ['status', 'scoreRaw', 'progress', 'progress_volumes',
                      'repeat', 'priority', 'private', 'notes',
                      'hidden_from_status_lists', 'custom_lists',
                      'advanced_scores', 'started_at', 'completed_at',
                      'updated_at', 'created_at']

    @classmethod
    def parse_data(cls, data: dict) -> 'AnilistUserEntry':
        """
        Parses data from an AniList GraphQL query response into AnilistUserEntry instances.
        For this matter, we not automatically update the database, but instead return the instance.

        Note on Synchronization Strategy:
            The synchronization of data between local and remote servers is crucial, especially
            in scenarios where updates occur in both places. The fields 'local_updated_at' and
            'updated_at' help track when local and remote updates happen, respectively.
            Two strategies to consider:
            1. Last Write Wins (LWW): Directly push all local changes to the server. Simpler,
               but may lead to overwriting recent remote updates.
            2. Merge Before Push: Fetch current data from the server, compare with local changes,
               and resolve conflicts before syncing. More complex, but ensures data accuracy.
            The application needs to implement a conflict resolution strategy for effective data
            synchronization. The 'updated_fields' field is crucial in this process as it tracks
            which fields have been updated locally. This tracking is essential to identify and
            resolve any conflicts during synchronization, ensuring data integrity and consistency.
        """

        entry = cls(
            id=data.get('id'),
            user_id=str(data.get('userId')),
            media_id=data.get('mediaId'),
            status=data.get('status'),
            scoreRaw=data.get('score'),
            progress=data.get('progress', 0),
            progress_volumes=data.get('progressVolumes', 0),
            repeat=data.get('repeat', 0),
            priority=data.get('priority', 0),
            private=data.get('private', False),
            notes=data.get('notes', ''),
            hidden_from_status_lists=data.get('hiddenFromStatusLists', False),
            custom_lists=data.get('customLists', {}),
            advanced_scores=data.get('advancedScores', {}),
            started_at=data.get('startedAt'),
            completed_at=data.get('completedAt'),
            updated_at=data.get('updatedAt', 0),
            created_at=data.get('createdAt', 0),

            # Local data to track sync status
            local_updated_at=data.get('updatedAt', 0),
            is_deleted=False,
            updated_fields={}
        )

        return entry

    @classmethod
    def fragment(cls):
        return cls._fragment

    @staticmethod
    def track_changes(mapper, connection, target):
        # Initialize updated_fields if not present
        if target.updated_fields is None:
            target.updated_fields = {}

        # Check for changes in each tracked field
        for column in AnilistUserEntry.tracked_fields:
            hist = get_history(target, column)
            if hist.has_changes():
                target.updated_fields[column] = getattr(target, column)

        # Update local_updated_at if there are any changes
        if target.updated_fields:
            target.local_updated_at = int(datetime.now().timestamp())


event.listen(AnilistUserEntry, 'before_update', AnilistUserEntry.track_changes)
