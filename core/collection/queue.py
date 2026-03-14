import threading
from typing import Generic, TypeVar, Any, Optional, Iterator
from weakref import WeakValueDictionary, WeakSet

T = TypeVar('T')


class NamedQueue(Generic[T]):
    def __init__(self, name: str) -> None:
        self.name: str = name
        self.queue: list[T] = []
        self._new_item: list[T] = []
        self._lock: threading.RLock = threading.RLock()
        self._dependents = WeakSet()

    @property
    def dependents(self):
        with self._lock:
            return list(self._dependents)

    def add_dependent(self, observer: Any) -> None:
        with self._lock:
            self._dependents.add(observer)

    def remove_dependent(self, observer: Any) -> None:
        with self._lock:
            self._dependents.discard(observer)

    def enqueue(self, item: T) -> None:
        with self._lock:
            self._new_item.append(item)

    def dequeue(self) -> Optional[T]:
        with self._lock:
            if not self.queue:
                return None
            return self.queue.pop(0)

    def is_empty(self) -> bool:
        with self._lock:
            return len(self.queue) == 0

    def checked(self, item: T):
        with self._lock:
            self.queue.append(item)

    def loop_new_items(self) -> Iterator[T]:
        with self._lock:
            for item in self._new_item:
                yield item
            self._new_item.clear()

    def __iter__(self) -> Iterator[T]:
        with self._lock:
            return iter(self.queue.copy())

    def __len__(self) -> int:
        with self._lock:
            return len(self.queue)


class QueueManager(Generic[T]):
    def __init__(self) -> None:
        self.queues: WeakValueDictionary[str, NamedQueue[T]] = WeakValueDictionary()
        self.lock: threading.RLock = threading.RLock()

    def create_queue(self, name: str, *, return_existing: bool = True) -> NamedQueue[T]:
        with self.lock:
            if name in self.queues:
                if return_existing:
                    return self.queues[name]
                else:
                    raise ValueError(f"Queue name '{name}' already exists.")
            queue = NamedQueue[T](name)
            self.queues[name] = queue
            return queue

    def get_queue(self, name: str) -> Optional[NamedQueue[T]]:
        with self.lock:
            return self.queues.get(name)
