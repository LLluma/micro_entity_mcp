"""Abstract storage interface and error type for entities."""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from micro_entity.entity import Entity
from micro_entity.validation import Scalar


class UnsetType:
    """Sentinel singleton indicating "no value supplied"."""

    _instance: "UnsetType | None" = None

    def __new__(cls) -> "UnsetType":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "UNSET"


UNSET = UnsetType()


class NotFoundError(Exception):
    """Raised when a store lookup finds no record for the requested id."""

    pass


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

        Raises ``FileExistsError`` if *id* already exists.
        """
        ...

    def get(self, id: str) -> Entity:
        """Fetch one entity by its id.

        Returns the Entity.

        Raises ``NotFoundError`` if *id* does not exist.
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
        body: str | None | UnsetType = UNSET,
    ) -> Entity:
        """Patch an existing entity.

        Only the provided fields are applied; omitted fields are preserved.

        Returns the updated Entity.

        Raises ``NotFoundError`` if *id* does not exist.
        """
        ...

    def delete(self, id: str) -> None:
        """Remove an entity by its id.

        Raises ``NotFoundError`` if *id* does not exist.
        """
        ...

    def clear(self) -> int:
        """Remove every entity in this store.

        Returns the number of records removed.
        """
        ...
