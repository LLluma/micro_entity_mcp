"""Markdown-backed entity store bound to a directory."""

import os
import tempfile
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from micro_entity.codec import (
    entity_from_parts,
    entity_to_parts,
    parse_document,
    serialize_document,
)
from micro_entity.entity import Entity
from micro_entity.store import NotFoundError
from micro_entity.validation import FormError, Scalar, validate_attribute_value, validate_id


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

    def get(self, id: str) -> Entity:
        """Load one entity record by id.

        Opens the ``.md`` file for *id*, parses frontmatter + body via the
        codec, and returns the ``Entity``.  Raises ``NotFoundError`` if the
        file does not exist.

        Parse errors (malformed frontmatter, missing timestamps, etc.) are
        propagated unchanged — the store is strict on read.
        """
        path = self._path_for(id)
        if not path.is_file():
            raise NotFoundError(f"entity not found: {id}")
        text = path.read_text(encoding="utf-8")
        fm, body = parse_document(text)
        return entity_from_parts(id, fm, body)

    def create(
        self,
        id: str,
        *,
        attributes: dict[str, Scalar | list[Scalar]],
        body: str | None = None,
    ) -> Entity:
        """Persist a new entity record as a markdown file.

        Stamps both ``created`` and ``updated`` from the injected clock.
        Raises ``FileExistsError`` if the file already exists.

        Validation (id shape, attribute values) runs **before** any file is
        written, so a bad request leaves no partial file on disk.
        """
        # Form-validated id — raises FormError immediately.
        path = self._path_for(id)
        if path.is_file():
            raise FileExistsError(f"entity already exists: {id}")

        # Validate all attribute values before touching the filesystem.
        for val in attributes.values():
            validate_attribute_value(val)

        ts = self._clock()
        entity = Entity(
            id=id,
            created=ts,
            updated=ts,
            attributes=attributes,
            body=body,
        )

        fm, body_text = entity_to_parts(entity)
        document = serialize_document(fm, body_text)
        self._atomic_write(path, document)
        return entity
