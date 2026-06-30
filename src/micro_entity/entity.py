"""Pydantic v2 model for an entity."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from micro_entity.validation import Scalar, validate_attribute_value, validate_id


class Entity(BaseModel):
    """A frozen entity with id, timestamps, optional body, and attributes."""

    model_config = ConfigDict(frozen=True)

    id: str
    created: datetime
    updated: datetime
    body: str | None = None
    attributes: dict[str, Scalar | list[Scalar]] = {}

    @field_validator("id")
    @classmethod
    def validate_id_field(cls, v: str) -> str:
        validate_id(v)
        return v

    @field_validator("created", "updated")
    @classmethod
    def validate_datetime_tz(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return v

    @field_validator("attributes")
    @classmethod
    def validate_attributes(
        cls, v: dict[str, Scalar | list[Scalar]]
    ) -> dict[str, Scalar | list[Scalar]]:
        for key, val in v.items():
            if key == "":
                raise ValueError("attribute key must not be empty")
            validate_attribute_value(val)
        return v
