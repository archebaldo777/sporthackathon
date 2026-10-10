"""Небольшой кэш в памяти процесса с TTL и вытеснением старых записей.

Используется для дорогих чтений (поиск по банку кандидатов, карта категорий, карточки кандидатов). Ключ всегда включает
версию данных (например, время последнего изменения профилей), поэтому изменения видны сразу, а TTL лишь ограничивает
память. У каждого воркера свой кэш — общий кэш (Redis) нужен только при горизонтальном масштабировании.
"""
from __future__ import annotations

import threading
import time
from collections import OrderedDict
from typing import Any, Callable


class TTLCache:
    def __init__(self, maxsize: int = 2048, ttl: float = 60.0):
        self.maxsize, self.ttl = maxsize, ttl
        self._data: OrderedDict[Any, tuple[float, Any]] = OrderedDict()
        self._lock = threading.Lock()
        self.hits = self.misses = 0

    def get_or_set(self, key, factory: Callable[[], Any]):
        now = time.monotonic()
        with self._lock:
            item = self._data.get(key)
            if item and item[0] > now:
                self._data.move_to_end(key)
                self.hits += 1
                return item[1]
        value = factory()
        with self._lock:
            self.misses += 1
            self._data[key] = (now + self.ttl, value)
            self._data.move_to_end(key)
            while len(self._data) > self.maxsize:
                self._data.popitem(last=False)
        return value

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
