import logging
import os
import threading
import time
from weakref import WeakValueDictionary


class FileCacheManager:
    class_logger = logging.getLogger(__name__)
    max_fail = 5
    _instances = WeakValueDictionary()

    def __new__(cls, file_path, *args, **kwargs):
        instance = cls._instances.get(file_path)
        if instance is not None:
            return instance
        else:
            instance = super(FileCacheManager, cls).__new__(cls)
            cls._instances[file_path] = instance
            return instance

    def __init__(self, file_path: str, use_cache: bool = True, *, max_items: int = 100):
        self.file_path = file_path
        self._original_file_path = file_path
        self.use_cache = use_cache
        self.max_items = max_items
        self._file_cache: list[str] = []
        self._file_timestamp: float = 0.0
        self._cache_updated: bool = False
        self._lock = threading.RLock()
        self._fail = 0

    def get_file_path(self):
        return self._original_file_path

    def read_file(self) -> list[str]:
        with self._lock:
            current_timestamp = os.path.getmtime(self.file_path) or 0

            if self.use_cache and self._file_timestamp == current_timestamp:
                return self._file_cache
            else:
                return self._read_from_file_and_update_cache()

    def append_to_cache(self, new_content: str):
        with self._lock:
            self._file_cache.insert(0, new_content)
            self._file_cache = self._file_cache[:self.max_items]
            self._cache_updated = True

    def write_to_file(self):
        with self._lock:
            if self._cache_updated:
                try:
                    with open(self.file_path, "w", encoding="utf-8") as file:
                        file.writelines(self._file_cache)
                    self._file_timestamp = os.path.getmtime(self.file_path)
                    self._cache_updated = False
                    self._fail = 0
                except Exception as e:
                    self.class_logger.error(f"Failed to write to file {self.file_path}: {e}")
                    self._fail += 1
                    if self._fail >= self.max_fail:
                        file_path, file_extension = os.path.splitext(self._original_file_path)
                        self.file_path = f"{file_path}-failed-at-{time.time()}.{file_extension}"
                        self._fail = 0

    def _read_from_file_and_update_cache(self):
        with open(self.file_path, "r", encoding="utf-8") as file:
            self._file_cache = file.readlines()
        self._file_cache = self._file_cache[:self.max_items]
        self._file_timestamp = os.path.getmtime(self.file_path)
        self._cache_updated = False
        return self._file_cache

    def is_write_needed(self) -> bool:
        with self._lock:
            return self._cache_updated
