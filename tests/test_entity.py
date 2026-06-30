"""Test micro_entity.entity.Entity model."""

# pyright: reportArgumentType=false

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from micro_entity.entity import Entity


def test_wellformed_entity_constructs_and_exposes_fields():
    """A well-formed entity constructs and exposes its fields correctly."""
    now = datetime.now(tz=UTC)
    entity = Entity(
        id="test-001",
        created=now,
        updated=now,
        body="hello",
        attributes={"priority": 1},
    )
    assert entity.id == "test-001"
    assert entity.body == "hello"
    assert entity.attributes == {"priority": 1}
    assert entity.created == now
    assert entity.updated == now


def test_malformed_id_rejected():
    """A malformed id raises ValidationError."""
    with pytest.raises(ValidationError):
        Entity(id="bad id!", created=datetime.now(tz=UTC), updated=datetime.now(tz=UTC))


def test_valid_id_passes():
    """A valid id like ADR-0007 passes validation."""
    entity = Entity(
        id="ADR-0007",
        created=datetime.now(tz=UTC),
        updated=datetime.now(tz=UTC),
    )
    assert entity.id == "ADR-0007"


def test_empty_attribute_key_rejected():
    """An empty string key in attributes raises ValidationError."""
    with pytest.raises(ValidationError):
        Entity(
            id="test-002",
            created=datetime.now(tz=UTC),
            updated=datetime.now(tz=UTC),
            attributes={"": "val"},
        )


def test_body_defaults_to_none():
    """body defaults to None when omitted."""
    entity = Entity(
        id="test-003",
        created=datetime.now(tz=UTC),
        updated=datetime.now(tz=UTC),
    )
    assert entity.body is None


def test_string_body_accepted_verbatim_not_in_attributes():
    """A string body (including "") is accepted and does NOT appear in attributes."""
    entity = Entity(
        id="test-004",
        created=datetime.now(tz=UTC),
        updated=datetime.now(tz=UTC),
        body="",
    )
    assert entity.body == ""
    assert "body" not in entity.attributes


def test_nested_dict_attribute_rejected():
    """A nested dict attribute value raises ValidationError."""
    with pytest.raises(ValidationError):
        Entity(
            id="test-005",
            created=datetime.now(tz=UTC),
            updated=datetime.now(tz=UTC),
            attributes={"key": {"nested": True}},
        )


def test_naive_datetime_rejected():
    """A naive datetime (no tzinfo) raises ValidationError."""
    naive = datetime(2024, 1, 1)
    with pytest.raises(ValidationError):
        Entity(id="test-006", created=naive, updated=datetime.now(tz=UTC))
    with pytest.raises(ValidationError):
        Entity(id="test-006", created=datetime.now(tz=UTC), updated=naive)


def test_entity_is_frozen():
    """Assigning to a field on a frozen entity raises an error."""
    entity = Entity(
        id="test-007",
        created=datetime.now(tz=UTC),
        updated=datetime.now(tz=UTC),
    )
    # Pydantic frozen raises a ValueError or NotImplementedError on assignment
    with pytest.raises((ValueError, NotImplementedError)):
        entity.id = "new"


def test_valid_scalar_and_list_attributes_pass():
    """Valid scalar and list attributes pass."""
    entity = Entity(
        id="test-008",
        created=datetime.now(tz=UTC),
        updated=datetime.now(tz=UTC),
        attributes={"priority": 1, "tags": ["a", "b"]},
    )
    assert entity.attributes == {"priority": 1, "tags": ["a", "b"]}
