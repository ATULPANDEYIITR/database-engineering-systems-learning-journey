from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from enum import Enum
from threading import RLock
from typing import Callable


class BufferError(Exception):
    """Base exception for buffer management failures."""


class BufferFullError(BufferError):
    """Raised when every frame is pinned and no frame can be evicted."""


class PageNotFoundError(BufferError):
    """Raised when a requested page does not exist."""


class FrameState(Enum):
    FREE = "free"
    CLEAN = "clean"
    DIRTY = "dirty"


@dataclass
class BufferFrame:
    page_id: int
    data: bytes
    pin_count: int = 0
    dirty: bool = False
    access_count: int = 1
    generation: int = 0

    @property
    def state(self) -> FrameState:
        return FrameState.DIRTY if self.dirty else FrameState.CLEAN


@dataclass
class BufferStatistics:
    requests: int = 0
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    writes: int = 0
    failed_evictions: int = 0

    @property
    def hit_ratio(self) -> float:
        return self.hits / self.requests if self.requests else 0.0

    @property
    def miss_ratio(self) -> float:
        return self.misses / self.requests if self.requests else 0.0


class BufferPool:
    """
    Fixed-capacity buffer pool using LRU replacement.

    OrderedDict maintains pages from least recently used
    to most recently used.

    Page loading and writing are delegated to storage callbacks.
    """

    def __init__(
        self,
        capacity: int,
        page_size: int = 4096,
        loader: Callable[[int], bytes] | None = None,
        writer: Callable[[int, bytes], None] | None = None,
    ):
        if capacity <= 0:
            raise ValueError("Buffer capacity must be positive.")

        if page_size <= 0:
            raise ValueError("Page size must be positive.")

        self.capacity = capacity
        self.page_size = page_size
        self.loader = loader or self._default_loader
        self.writer = writer or self._default_writer

        self.frames: OrderedDict[int, BufferFrame] = OrderedDict()
        self.statistics = BufferStatistics()
        self.lock = RLock()
        self.generation = 0

    @staticmethod
    def _default_loader(page_id: int) -> bytes:
        return f"PAGE:{page_id}".encode().ljust(4096, b"\0")

    @staticmethod
    def _default_writer(page_id: int, data: bytes) -> None:
        print(f"Storage write: page={page_id}, bytes={len(data)}")

    def _validate_page(self, page_id: int) -> None:
        if not isinstance(page_id, int) or isinstance(page_id, bool):
            raise TypeError("Page ID must be an integer.")

        if page_id < 0:
            raise ValueError("Page ID cannot be negative.")

    def _load_page(self, page_id: int) -> bytes:
        data = self.loader(page_id)

        if not isinstance(data, bytes):
            raise TypeError("Page loader must return bytes.")

        if len(data) != self.page_size:
            raise ValueError(
                f"Invalid page size: expected {self.page_size}, "
                f"received {len(data)}."
            )

        return data

    def _flush_frame(self, frame: BufferFrame) -> None:
        if frame.dirty:
            self.writer(frame.page_id, frame.data)
            frame.dirty = False
            self.statistics.writes += 1

    def _evict(self) -> None:
        for page_id, frame in list(self.frames.items()):
            if frame.pin_count == 0:
                # Write dirty pages before removing them.
                self._flush_frame(frame)
                del self.frames[page_id]
                self.statistics.evictions += 1
                return

        self.statistics.failed_evictions += 1
        raise BufferFullError(
            "All buffer frames are pinned. Unpin a page before loading another."
        )

    def fetch(self, page_id: int) -> BufferFrame:
        self._validate_page(page_id)

        with self.lock:
            self.statistics.requests += 1

            if page_id in self.frames:
                self.statistics.hits += 1
                frame = self.frames[page_id]
                frame.access_count += 1
                self.frames.move_to_end(page_id)
                return frame

            self.statistics.misses += 1

            # Load before evicting to avoid losing a frame if storage fails.
            data = self._load_page(page_id)

            if len(self.frames) >= self.capacity:
                self._evict()

            self.generation += 1

            frame = BufferFrame(
                page_id=page_id,
                data=data,
                generation=self.generation,
            )

            self.frames[page_id] = frame
            return frame

    def pin(self, page_id: int) -> BufferFrame:
        with self.lock:
            frame = self.fetch(page_id)
            frame.pin_count += 1
            return frame

    def unpin(self, page_id: int, dirty: bool = False) -> None:
        self._validate_page(page_id)

        with self.lock:
            frame = self.frames.get(page_id)

            if frame is None:
                raise PageNotFoundError(f"Page {page_id} is not cached.")

            if frame.pin_count <= 0:
                raise BufferError(f"Page {page_id} is not pinned.")

            frame.pin_count -= 1
            frame.dirty = frame.dirty or dirty

    def read(self, page_id: int) -> bytes:
        with self.lock:
            return bytes(self.fetch(page_id).data)

    def write(self, page_id: int, offset: int, payload: bytes) -> None:
        if not isinstance(payload, bytes):
            raise TypeError("Payload must be bytes.")

        if not isinstance(offset, int) or isinstance(offset, bool):
            raise TypeError("Offset must be an integer.")

        if offset < 0 or offset + len(payload) > self.page_size:
            raise ValueError("Write exceeds page boundaries.")

        with self.lock:
            frame = self.pin(page_id)

            try:
                modified = bytearray(frame.data)
                modified[offset:offset + len(payload)] = payload
                frame.data = bytes(modified)
                frame.dirty = True
            finally:
                self.unpin(page_id, dirty=True)

    def flush_page(self, page_id: int) -> None:
        with self.lock:
            frame = self.frames.get(page_id)

            if frame is None:
                raise PageNotFoundError(f"Page {page_id} is not cached.")

            if frame.pin_count:
                raise BufferError("Cannot flush a pinned page.")

            self._flush_frame(frame)

    def flush_all(self) -> None:
        with self.lock:
            for frame in self.frames.values():
                if frame.pin_count:
                    raise BufferError(
                        f"Cannot flush all pages: page {frame.page_id} is pinned."
                    )

            for frame in self.frames.values():
                self._flush_frame(frame)

    def invalidate(self, page_id: int, discard_dirty: bool = False) -> None:
        with self.lock:
            frame = self.frames.get(page_id)

            if frame is None:
                return

            if frame.pin_count:
                raise BufferError("Cannot invalidate a pinned page.")

            if frame.dirty and not discard_dirty:
                self._flush_frame(frame)

            del self.frames[page_id]

    def snapshot(self) -> dict:
        with self.lock:
            return {
                "capacity": self.capacity,
                "used_frames": len(self.frames),
                "free_frames": self.capacity - len(self.frames),
                "pages": [
                    {
                        "page_id": frame.page_id,
                        "state": frame.state.value,
                        "pin_count": frame.pin_count,
                        "access_count": frame.access_count,
                    }
                    for frame in self.frames.values()
                ],
                "statistics": {
                    "requests": self.statistics.requests,
                    "hits": self.statistics.hits,
                    "misses": self.statistics.misses,
                    "hit_ratio": round(self.statistics.hit_ratio, 4),
                    "miss_ratio": round(self.statistics.miss_ratio, 4),
                    "evictions": self.statistics.evictions,
                    "writes": self.statistics.writes,
                    "failed_evictions": self.statistics.failed_evictions,
                },
            }


def demonstrate_buffer_management() -> None:
    storage: dict[int, bytes] = {}
    page_size = 64

    def loader(page_id: int) -> bytes:
        if page_id not in storage:
            storage[page_id] = (
                f"Initial content of page {page_id}".encode()
                .ljust(page_size, b"\0")
            )
        return storage[page_id]

    def writer(page_id: int, data: bytes) -> None:
        storage[page_id] = data
        print(f"Persisted page {page_id}")

    pool = BufferPool(
        capacity=3,
        page_size=page_size,
        loader=loader,
        writer=writer,
    )

    print("\n1. Initial page requests")

    pool.fetch(1)
    pool.fetch(2)
    pool.fetch(3)

    # Page 1 is now the least recently used page.
    pool.fetch(1)

    print("\n2. Buffer hit and miss")

    pool.fetch(2)
    pool.fetch(4)

    print("\n3. Modify a cached page")

    pool.write(4, 0, b"UPDATED DATABASE RECORD")

    print("\n4. Demonstrate pinning")

    pinned = pool.pin(2)

    try:
        pool.fetch(5)
        pool.fetch(6)
    except BufferFullError as error:
        print("Expected buffer pressure:", error)
    finally:
        pool.unpin(2)

    print("\n5. Flush dirty pages")

    pool.flush_all()

    print("\n6. Buffer pool snapshot")

    import json
    print(json.dumps(pool.snapshot(), indent=4))

    print("\n7. Edge-case validation")

    try:
        pool.unpin(2)
    except BufferError as error:
        print("Expected error:", error)

    try:
        pool.fetch(-1)
    except ValueError as error:
        print("Expected error:", error)

    print("\n8. Storage verification")

    assert storage[4].startswith(b"UPDATED DATABASE RECORD")
    assert pool.statistics.hits > 0
    assert pool.statistics.misses > 0

    print("All buffer management assertions passed.")


if __name__ == "__main__":
    demonstrate_buffer_management()
