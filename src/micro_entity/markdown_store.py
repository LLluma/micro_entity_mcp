"""Markdown-backed entity store bound to a directory."""

import os
import tempfile
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from micro_entity.codec import (
    CommentedMap,
    entity_from_parts,
    entity_to_parts,
    parse_document,
    serialize_document,
)
from micro_entity.entity import Entity
from micro_entity.store import UNSET, LoadError, NotFoundError, UnsetType
from micro_entity.validation import FormError, Scalar, validate_attribute_value, validate_id


class MarkdownStore:
    """A store that maps entity ids to ``.md`` files under a directory."""

    def __init__(
        self,
        directory: Path,
        *,
        segment: str | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        resolved = Path(directory).resolve()
        if segment:
            resolved = resolved / segment
        self._directory = resolved
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

    def exists(self, id: str) -> bool:
        return self._path_for(id).is_file()

    def path_for(self, id: str) -> Path:
        return self._path_for(id)

    def atomic_write(self, path: Path, text: str) -> None:
        self._atomic_write(path, text)

    def get(
        self,
        id: str,
        *,
        normalize: Callable[[CommentedMap], CommentedMap] | None = None,
    ) -> Entity:
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
        if normalize is not None:
            fm = normalize(fm)
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

    def update(
        self,
        id: str,
        *,
        attributes: dict[str, Scalar | list[Scalar]] | None = None,
        body: str | None | UnsetType = UNSET,
        normalize: Callable[[CommentedMap], CommentedMap] | None = None,
    ) -> Entity:
        """Patch an existing entity record.

        *attributes* values are validated **before** any I/O; a bad value
        leaves the file untouched.  The frontmatter ``CommentedMap`` is
        patched in-place so comments, key-order, and untouched keys survive.

        Body behaviour: omit ``body`` (or pass ``UNSET``) to keep the
        existing body verbatim; pass ``body=""``/``body="..."``/``body=None``
        to replace it.  ``body=None`` removes the body region entirely.

        Returns the updated ``Entity``.

        Raises ``NotFoundError`` if *id* does not exist.
        """
        path = self._path_for(id)
        if not path.is_file():
            raise NotFoundError(f"entity not found: {id}")

        text = path.read_text(encoding="utf-8")
        fm, existing_body = parse_document(text)
        if normalize is not None:
            fm = normalize(fm)

        # Validate ALL provided attribute values before touching the filesystem.
        if attributes is not None:
            for val in attributes.values():
                validate_attribute_value(val)
            # Patch the CommentedMap in-place (preserves comments, order, other keys).
            for k, v in attributes.items():
                fm[k] = v

        fm["updated"] = self._clock().isoformat()

        if body is UNSET:
            new_body = existing_body
        else:
            assert isinstance(body, (str, type(None)))
            new_body = body

        document = serialize_document(fm, new_body)
        self._atomic_write(path, document)
        return entity_from_parts(id, fm, new_body)

    def load_all(
        self,
        *,
        normalize: Callable[[CommentedMap], CommentedMap] | None = None,
    ) -> tuple[list[Entity], list[LoadError]]:
        """Load every ``.md`` record in the directory.

        Valid records become ``Entity`` instances, sorted by id.
        Malformed files yield a ``LoadError`` with their stem and the
        exception message.  Returns ``(entities, errors)`` — never
        raises.
        """
        entities: list[Entity] = []
        errors: list[LoadError] = []

        if not self._directory.is_dir():
            return (entities, errors)

        for path in sorted(self._directory.glob("*.md")):
            stem = path.stem
            try:
                entity = self.get(stem, normalize=normalize)
                entities.append(entity)
            except Exception as exc:
                errors.append(LoadError(id=stem, reason=str(exc)))

        entities.sort(key=lambda e: e.id)
        return (entities, errors)

    def delete(self, id: str) -> None:
        """Remove the ``.md`` file for *id*.

        Raises ``NotFoundError`` if the file does not exist.
        """
        path = self._path_for(id)
        if not path.is_file():
            raise NotFoundError(f"entity not found: {id}")
        path.unlink()

    def clear(self) -> None:
        """Remove every ``.md`` record file directly in the store directory.

        Leaves non-``.md`` files and subdirectories untouched.  No-op when
        the store is already empty.
        """
        if not self._directory.is_dir():
            return
        for path in self._directory.glob("*.md"):
            if path.is_file():
                path.unlink()
