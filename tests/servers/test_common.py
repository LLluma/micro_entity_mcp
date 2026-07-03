from dataclasses import FrozenInstanceError

import pytest

from servers._common import ProfileConfig


class TestProfileConfig:
    """Tests for the frozen ProfileConfig dataclass."""

    def test_construct_all_fields_defaults(self):
        """All fields present; missing callables default to None."""
        cfg = ProfileConfig(
            name="x",
            instructions="hi",
            status_values={"a", "b"},
        )
        assert cfg.name == "x"
        assert cfg.instructions == "hi"
        assert cfg.status_values == {"a", "b"}
        assert cfg.normalize is None
        assert cfg.normalize_id is None
        assert cfg.reserved_keys == frozenset({"created", "updated", "id"})

    def test_construct_with_callables(self):
        """normalize and normalize_id callables are stored as-is."""

        def noop(cm):
            return cm

        def normalize_id(_id):
            return _id

        cfg = ProfileConfig(
            name="y",
            instructions="lo",
            status_values={"c"},
            normalize=noop,
            normalize_id=normalize_id,
        )
        assert cfg.normalize is noop
        assert cfg.normalize_id is normalize_id

    def test_dataclass_is_frozen(self):
        """Frozen dataclass rejects mutation via __setattr__."""
        cfg = ProfileConfig(
            name="x",
            instructions="hi",
            status_values={"a"},
        )
        with pytest.raises(FrozenInstanceError):
            type(cfg).__setattr__(cfg, "name", "y")
