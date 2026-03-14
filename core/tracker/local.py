import logging
from typing import Optional

from devlog import log_on_error
from sqlalchemy.orm import Session

from core.interfaces.tracker.local import BaseLocalTracker
from core.interfaces.database.models.Media.local_media import LocalMedia
from core.interfaces.database.models.Media.service_mapping import ServiceMediaMapping
from core.interfaces.database.types.media import MediaType, MediaStatus
from core.interfaces.database.const.service import ServiceName

logger = logging.getLogger(__name__)


class LocalTracker(BaseLocalTracker):

    def __init__(self, session: Session):
        self._session = session

    def _to_dict(self, entry: LocalMedia) -> dict:
        return {
            "id": entry.id,
            "title": entry.title,
            "media_type": entry.media_type.value if entry.media_type else None,
            "status": entry.status.value if entry.status else None,
            "progress": entry.progress,
            "total_episodes": entry.total_episodes,
            "score": entry.score,
            "start_date": entry.start_date,
            "end_date": entry.end_date,
            "notes": entry.notes,
            "file_path": entry.file_path,
            "created_at": entry.created_at,
            "updated_at": entry.updated_at,
        }

    def _mapping_to_dict(self, mapping: ServiceMediaMapping) -> dict:
        return {
            "id": mapping.id,
            "local_media_id": mapping.local_media_id,
            "service_name": mapping.service_name.value,
            "service_media_id": mapping.service_media_id,
        }

    def _get_entry_or_raise(self, media_id: int) -> LocalMedia:
        entry = self._session.query(LocalMedia).get(media_id)
        if not entry:
            raise ValueError(f"Media entry {media_id} not found")
        return entry

    def get_entry(self, media_id: int) -> dict:
        return self._to_dict(self._get_entry_or_raise(media_id))

    def list_entries(self, status: Optional[MediaStatus] = None,
                     media_type: Optional[MediaType] = None) -> list[dict]:
        query = self._session.query(LocalMedia)
        if status is not None:
            query = query.filter(LocalMedia.status == status)
        if media_type is not None:
            query = query.filter(LocalMedia.media_type == media_type)
        return [self._to_dict(e) for e in query.all()]

    @log_on_error(logging.ERROR, "Failed to add entry: {error!r}")
    def add_entry(self, title: str, media_type: MediaType = MediaType.ANIME,
                  **kwargs) -> dict:
        entry = LocalMedia(title=title, media_type=media_type, **kwargs)
        self._session.add(entry)
        self._session.commit()
        return self._to_dict(entry)

    def update_progress(self, media_id: int, progress: int) -> dict:
        entry = self._get_entry_or_raise(media_id)
        entry.progress = progress
        if entry.total_episodes and progress >= entry.total_episodes:
            entry.status = MediaStatus.COMPLETED
        elif entry.status == MediaStatus.PLANNED and progress > 0:
            entry.status = MediaStatus.WATCHING
        self._session.commit()
        return self._to_dict(entry)

    def update_status(self, media_id: int, status: MediaStatus) -> dict:
        entry = self._get_entry_or_raise(media_id)
        entry.status = status
        self._session.commit()
        return self._to_dict(entry)

    def update_entry(self, media_id: int, **kwargs) -> dict:
        entry = self._get_entry_or_raise(media_id)
        for key, value in kwargs.items():
            if hasattr(entry, key):
                setattr(entry, key, value)
            else:
                raise ValueError(f"Unknown field: {key}")
        self._session.commit()
        return self._to_dict(entry)

    def delete_entry(self, media_id: int) -> bool:
        entry = self._session.query(LocalMedia).get(media_id)
        if not entry:
            return False
        self._session.delete(entry)
        self._session.commit()
        return True

    def search(self, query: str) -> list[dict]:
        results = self._session.query(LocalMedia).filter(
            LocalMedia.title.ilike(f"%{query}%")
        ).all()
        return [self._to_dict(e) for e in results]

    def link_service(self, media_id: int, service_name: str,
                     service_media_id: str) -> dict:
        self._get_entry_or_raise(media_id)  # verify exists
        svc = ServiceName(service_name)
        # Check for existing mapping
        existing = self._session.query(ServiceMediaMapping).filter_by(
            local_media_id=media_id, service_name=svc
        ).first()
        if existing:
            existing.service_media_id = service_media_id
        else:
            existing = ServiceMediaMapping(
                local_media_id=media_id,
                service_name=svc,
                service_media_id=service_media_id,
            )
            self._session.add(existing)
        self._session.commit()
        return self._mapping_to_dict(existing)

    def unlink_service(self, media_id: int, service_name: str) -> bool:
        svc = ServiceName(service_name)
        mapping = self._session.query(ServiceMediaMapping).filter_by(
            local_media_id=media_id, service_name=svc
        ).first()
        if not mapping:
            return False
        self._session.delete(mapping)
        self._session.commit()
        return True

    def get_service_mapping(self, media_id: int) -> list[dict]:
        mappings = self._session.query(ServiceMediaMapping).filter_by(
            local_media_id=media_id
        ).all()
        return [self._mapping_to_dict(m) for m in mappings]
