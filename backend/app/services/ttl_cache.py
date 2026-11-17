"""Process-local TTL cache for provider responses."""

from collections.abc import Callable
from copy import deepcopy
from threading import RLock
from time import monotonic
from typing import Generic, TypeVar

Key = TypeVar("Key")
Value = TypeVar("Value")


class TTLCache(Generic[Key, Value]):
    """Small thread-safe cache that returns copies so callers cannot mutate entries."""

    def __init__(self) -> None:
        self._entries: dict[Key, tuple[float, Value]] = {}
        self._lock = RLock()

    def get_or_set(
        self,
        key: Key,
        ttl_seconds: float,
        factory: Callable[[], Value],
        *,
        force_refresh: bool = False,
    ) -> Value:
        now = monotonic()
        with self._lock:
            entry = self._entries.get(key)
            if not force_refresh and entry and entry[0] > now:
                return deepcopy(entry[1])
            if entry:
                self._entries.pop(key, None)

        # Provider work happens outside the lock to avoid blocking unrelated keys.
        value = factory()
        with self._lock:
            self._entries[key] = (monotonic() + ttl_seconds, deepcopy(value))
        return deepcopy(value)

    def clear(self) -> None:
        """Clear entries; mainly useful for isolated tests and manual invalidation."""
        with self._lock:
            self._entries.clear()
