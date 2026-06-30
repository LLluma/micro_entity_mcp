"""Abstract storage interface and error type for entities."""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from micro_entity.entity import Entity
from micro_entity.validation import Scalar


@dataclass(frozen=True)
class LoadError:
    """Error record encountered during store load operations."""

    id: str
    reason: str


@runtime_checkable
class Store(Protocol):
    """Abstract storage interface for entities.

    Profiles code against this seam so that any concrete backend
    (MarkdownStore, DatabaseStore, etc.) can be swapped without
    changing profile logic.
    """

    def create(
        self,
        id: str,
        *,
        attributes: dict[str, Scalar | list[Scalar]],
        body: str | None = None,
    ) -> Entity:
        """Create a new entity record.

        Returns the created Entity.

        Raises ``ValueError`` if *id* already exists.
        """
        ...

    def get(self, id: str) -> Entity:
        """Fetch one entity by its id.

        Returns the Entity.

        Raises ``ValueError`` if not found.
        """
        ...

    def load_all(self) -> tuple[list[Entity], list[LoadError]]:
        """Load all entities, quarantining load errors.

        Returns a ``(entities, errors)`` tuple. Records that failed
        to load appear in *errors* with their id and the reason.
        """
        ...

    def update(
        self,
        id: str,
        *,
        attributes: dict[str, Scalar | list[Scalar]] | None = None,
        body: str | None = None,
    ) -> Entity:
        """Patch an existing entity.

        Only the provided fields are applied; omitted fields are preserved.

        Returns the updated Entity.

        Raises ``ValueError`` if *id* does not exist.
        """
        ...

    def delete(self, id: str) -> None:
        """Remove an entity by its id.

        Raises ``ValueError`` if not found.
        """
        ...

    def clear(self) -> None:
        """Remove every entity in this store."""
        ...
