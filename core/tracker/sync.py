import logging

from devlog import log_on_start, log_on_error

from core.interfaces.tracker.local import BaseLocalTracker
from core.interfaces.tracker.service import BaseServiceTracker
from core.interfaces.tracker.sync import BaseSyncManager, SyncResult

logger = logging.getLogger(__name__)


class SyncManager(BaseSyncManager):

    @log_on_start(logging.INFO, "Syncing from service to local...")
    @log_on_error(logging.ERROR, "Sync from service failed: {error!r}")
    def sync_from_service(self, local: BaseLocalTracker,
                          service: BaseServiceTracker,
                          user_id: str) -> SyncResult:
        result = SyncResult(added=0, updated=0, deleted=0, conflicts=0, errors=[])
        service_name = service.get_name()

        try:
            remote_entries = service.get_user_list(user_id)
        except Exception as e:
            result["errors"].append(f"Failed to fetch user list: {e}")
            return result

        for remote in remote_entries:
            try:
                remote_id = str(remote.get("id", remote.get("media_id", "")))
                if not remote_id:
                    continue

                # Find local entry linked to this service ID
                local_entries = local.list_entries()
                linked_entry = None
                for entry in local_entries:
                    mappings = local.get_service_mapping(entry["id"])
                    for m in mappings:
                        if m["service_name"] == service_name and m["service_media_id"] == remote_id:
                            linked_entry = entry
                            break
                    if linked_entry:
                        break

                if linked_entry is None:
                    # Create new local entry
                    title = remote.get("title", remote.get("name", f"Unknown ({remote_id})"))
                    if isinstance(title, dict):
                        title = title.get("english") or title.get("romaji") or str(title)
                    new_entry = local.add_entry(title=title)
                    local.link_service(new_entry["id"], service_name, remote_id)
                    result["added"] += 1
                else:
                    # Update existing entry if remote has newer progress
                    remote_progress = remote.get("progress", 0) or 0
                    if remote_progress > linked_entry.get("progress", 0):
                        local.update_progress(linked_entry["id"], remote_progress)
                        result["updated"] += 1
                    elif remote_progress < linked_entry.get("progress", 0):
                        result["conflicts"] += 1

            except Exception as e:
                result["errors"].append(str(e))

        return result

    @log_on_start(logging.INFO, "Syncing from local to service...")
    @log_on_error(logging.ERROR, "Sync to service failed: {error!r}")
    def sync_to_service(self, local: BaseLocalTracker,
                        service: BaseServiceTracker,
                        user_id: str) -> SyncResult:
        result = SyncResult(added=0, updated=0, deleted=0, conflicts=0, errors=[])
        service_name = service.get_name()

        for entry in local.list_entries():
            try:
                mappings = local.get_service_mapping(entry["id"])
                mapping = next(
                    (m for m in mappings if m["service_name"] == service_name),
                    None
                )
                if not mapping:
                    continue  # not linked to this service

                service.update_entry(
                    media_id=mapping["service_media_id"],
                    progress=entry.get("progress", 0),
                    status=entry.get("status"),
                    score=entry.get("score"),
                )
                result["updated"] += 1
            except Exception as e:
                result["errors"].append(str(e))

        return result

    def resolve_conflict(self, local_entry: dict,
                         remote_entry: dict) -> dict:
        """Default: higher progress wins."""
        local_progress = local_entry.get("progress", 0) or 0
        remote_progress = remote_entry.get("progress", 0) or 0
        if remote_progress > local_progress:
            return remote_entry
        return local_entry
