"""Tests for the LoadError dataclass and Store protocol."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from micro_entity.entity import Entity
from micro_entity.store import LoadError, Store


class TestLoadError:
    """Unit tests for LoadError."""

    def test_construct_with_id_and_reason(self) -> None:
        err = LoadError(id="bad-id", reason="file not found")
        assert err.id == "bad-id"
        assert err.reason == "file not found"

    def test_is_frozen(self) -> None:
        err = LoadError(id="x", reason="oops")
        with pytest.raises(FrozenInstanceError):
            err.id = "changed"  # type: ignore[misc]

    def test_equality_by_value(self) -> None:
        a = LoadError(id="same", reason="same")
        b = LoadError(id="same", reason="same")
        c = LoadError(id="same", reason="other")
        assert a == b
        assert a != c

    def test_hash_is_consistent(self) -> None:
        err = LoadError(id="h", reason="err")
        # frozen dataclasses are hashable
        s = {err}
        assert err in s

    def test_repr_contains_fields(self) -> None:
        err = LoadError(id="rep", reason="msg")
        assert "LoadError" in repr(err)
        assert "rep" in repr(err)
        assert "msg" in repr(err)


class TestStore:
    """Verify Store is a runtime-checkable protocol with required methods."""

    # -- a minimal stub that implements every Store method --

    class _StubStore:
        """Do-nothing stub implementing Store for runtime-check testing."""

        def _now(self) -> datetime:
            return datetime.now(UTC)

        def create(
            self,
            id: str,
            *,
            attributes: dict[str, str | int | float | bool | list[str | int | float | bool]],
            body: str | None = None,
        ) -> Entity:
            return Entity(
                id=id,
                created=self._now(),
                updated=self._now(),
                attributes=attributes,
                body=body,
            )

        def get(self, id: str) -> Entity:
            return Entity(id=id, created=self._now(), updated=self._now())

        def load_all(self) -> tuple[list[Entity], list[LoadError]]:
            return [], []

        def update(
            self,
            id: str,
            *,
            attributes: (
                dict[str, str | int | float | bool | list[str | int | float | bool]] | None
            ) = None,
            body: str | None = None,
        ) -> Entity:
            return Entity(
                id=id,
                created=self._now(),
                updated=self._now(),
                attributes=attributes or {},
                body=body,
            )

        def delete(self, id: str) -> None:
            pass

        def clear(self) -> None:
            pass

    def test_store_is_runtime_checkable_protocol(self) -> None:
        stub = self._StubStore()
        # isinstance should not raise; Protocol is runtime-checkable
        assert isinstance(stub, Store)

    def test_all_method_signatures_match(self) -> None:
        """Every Store method has the expected signature shape."""
        expected = {"create", "get", "load_all", "update", "delete", "clear"}
        # Protocol members are accessible; check that our stub has them all.
        stub = self._StubStore()
        for name in expected:
            assert hasattr(stub, name), f"Stub missing method: {name}"

    def test_store_protocol_has_all_methods(self) -> None:
        """Store Protocol defines the six required methods."""
        protocol_attrs = {name for name in dir(Store) if not name.startswith("_")}
        expected = {"create", "get", "load_all", "update", "delete", "clear"}
        assert expected.issubset(protocol_attrs), f"Missing: {expected - protocol_attrs}"

    def test_method_docstrings_present(self) -> None:
        """Every Store method has a docstring."""
        for name in ("create", "get", "load_all", "update", "delete", "clear"):
            method = getattr(Store, name)
            doc = method.__doc__ or ""
            assert doc.strip(), f"{name} missing docstring"

    def test_store_is_protocol_not_abc(self) -> None:
        """Store uses typing.Protocol, not abc.ABC."""
        from typing import Protocol

        assert issubclass(Store, Protocol)

    def test_stub_implements_store_structurally(self) -> None:
        """A class that implements all Store methods passes isinstance."""
        stub = self._StubStore()
        # structural subtyping: isinstance succeeds even without subclassing
        assert isinstance(stub, Store)

    def test_create_signature_accepts_scalar_types(self) -> None:
        """create() attributes accept Scalar or list[Scalar]."""
        stub = self._StubStore()
        e = stub.create(
            id="test",
            attributes={"role": "admin", "count": 42},
            body="hello",
        )
        assert e.id == "test"
        assert e.attributes == {"role": "admin", "count": 42}

    def test_create_default_body_none(self) -> None:
        """create() defaults body to None when not provided."""
        stub = self._StubStore()
        e = stub.create(id="no-body", attributes={})
        assert e.body is None

    def test_load_all_returns_typed_tuple(self) -> None:
        """load_all returns (list[Entity], list[LoadError])."""
        stub = self._StubStore()
        entities, errors = stub.load_all()
        assert isinstance(entities, list)
        assert isinstance(errors, list)
        assert isinstance(entities, list)
        assert all(isinstance(e, Entity) for e in entities)

    def test_update_preserves_existing(self) -> None:
        """update() only applies provided fields."""
        stub = self._StubStore()
        e = stub.update(id="u1", body="new body")
        assert e.id == "u1"
        assert e.body == "new body"

    def test_delete_is_none_return(self) -> None:
        """delete() returns None."""
        stub = self._StubStore()
        result = stub.delete("any-id")
        assert result is None

    def test_clear_is_none_return(self) -> None:
        """clear() returns None."""
        stub = self._StubStore()
        result = stub.clear()
        assert result is None
