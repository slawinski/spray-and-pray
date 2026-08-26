"""OS-level concurrency lock for discovery runs.

Prevents scheduled discovery and manual discovery from executing
concurrently (which would double-spend LLM budget and race imports).
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

LOCK_PATH = Path(".discovery.lock")


class DiscoveryLockError(Exception):
    """Discovery is already in progress."""


class DiscoveryLock:
    """flock-based exclusive lock; falls back to no-op on non-POSIX."""

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path else LOCK_PATH
        self._file = None

    def acquire(self) -> bool:
        """Tries to take the lock. Returns True on success, False if held."""
        try:
            import fcntl
        except ImportError:  # non-POSIX: assume uncontended
            return True

        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._file = open(self.path, "w")
        try:
            fcntl.flock(self._file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self._file.close()
            self._file = None
            return False
        self._file.write(str(__import__("os").getpid()))
        self._file.flush()
        return True

    def release(self) -> None:
        if self._file is None:
            return
        try:
            import fcntl

            fcntl.flock(self._file.fileno(), fcntl.LOCK_UN)
        except Exception:  # pragma: no cover — best effort
            pass
        try:
            self._file.close()
        finally:
            self._file = None

    def __enter__(self) -> "DiscoveryLock":
        if not self.acquire():
            raise DiscoveryLockError("Discovery already in progress.")
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()
