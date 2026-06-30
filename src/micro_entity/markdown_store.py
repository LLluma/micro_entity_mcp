"""Markdown-backed entity store bound to a directory."""

import os
import tempfile
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from micro_entity.validation import FormError, validate_id


class MarkdownStore:
    """A store that maps entity ids to ``.md`` files under a directory."""

    def __init__(
        self,
        directory: Path,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._directory = Path(directory).resolve()
        self._clock = clock
        self._directory.mkdir(parents=True, exist_ok=True)

    def _path_for(self, id: str) -> Path:
        """Resolve an entity id to a file path under the store directory.

        Validates the id so a traversal id can never escape the partition.

        Raises ``FormError`` if *id* is invalid.
        """
        validate_id(id)
        path = self._directory / f"{id}.md"
        # Ensure the resolved path stays inside the directory.
        try:
            path.relative_to(self._directory)
        except ValueError:
            raise FormError(f"id {id!r} resolves outside the store directory") from None
        return path

    def _atomic_write(self, path: Path, text: str) -> None:
        """Write *text* to *path* atomically via temp-file + ``os.replace``.

        The temp file is created in the same directory as *path* so that
        ``os.replace`` is an atomic rename on a single filesystem.
        """
        parent = path.parent
        parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=str(parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(text)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, str(path))
        except BaseException:
            os.unlink(tmp_path)
            raise
