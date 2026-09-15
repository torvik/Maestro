"""Cross-platform interprocess lock for memory index writes.

Uses msvcrt.locking on Windows, fcntl.flock on Unix.
No external dependencies -- stdlib only (Python 3.9+).
No I/O at module level.
"""

import os
import time
from pathlib import Path


class MemoryLock:
    """Interprocess file lock for exclusive SQLite writes.

    Usage::

        with MemoryLock(lock_path):
            # write to SQLite
    """

    def __init__(self, lock_path=None):
        self._lock_path = Path(lock_path) if lock_path else None
        self._fd = None
        self._acquired = False

    def acquire(self, timeout_seconds: float = 10.0) -> bool:
        """Try to acquire exclusive lock.

        Returns True if acquired, False if timeout.
        Does not raise on timeout.
        """
        if self._lock_path is None:
            raise ValueError("lock_path is not set")

        # Ensure parent dir exists
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)

        deadline = time.monotonic() + timeout_seconds

        if os.name == "nt":
            return self._acquire_windows(deadline)
        else:
            return self._acquire_unix(deadline)

    def _acquire_windows(self, deadline: float) -> bool:
        import msvcrt

        # Open or create the lock file
        while True:
            try:
                if self._fd is None:
                    self._fd = os.open(
                        str(self._lock_path),
                        os.O_RDWR | os.O_CREAT,
                    )
                msvcrt.locking(self._fd, msvcrt.LK_NBLCK, 1)
                self._acquired = True
                return True
            except (OSError, IOError):
                if time.monotonic() >= deadline:
                    return False
                time.sleep(0.05)

    def _acquire_unix(self, deadline: float) -> bool:
        import fcntl

        if self._fd is None:
            self._fd = os.open(
                str(self._lock_path),
                os.O_RDWR | os.O_CREAT,
            )

        while True:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                self._acquired = True
                return True
            except (OSError, IOError):
                if time.monotonic() >= deadline:
                    return False
                time.sleep(0.05)

    def release(self) -> None:
        """Release the lock. Idempotent."""
        if not self._acquired or self._fd is None:
            return

        if os.name == "nt":
            import msvcrt
            try:
                msvcrt.locking(self._fd, msvcrt.LK_UNLCK, 1)
            except (OSError, IOError):
                pass
        else:
            import fcntl
            try:
                fcntl.flock(self._fd, fcntl.LOCK_UN)
            except (OSError, IOError):
                pass

        try:
            os.close(self._fd)
        except (OSError, IOError):
            pass

        self._fd = None
        self._acquired = False

    def __enter__(self):
        from packages.core.memory.core import MemoryError
        if not self.acquire():
            raise MemoryError(
                f"Could not acquire memory lock at {self._lock_path} "
                f"within timeout. Another process may be writing."
            )
        return self

    def __exit__(self, *args):
        self.release()
