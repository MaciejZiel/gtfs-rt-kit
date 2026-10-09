"""Conversion of models to JSON-compatible structures."""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from datetime import date, datetime
from typing import Any

__all__ = ["to_jsonable"]


def to_jsonable(value: Any) -> Any:
    """Recursively convert dataclasses, datetimes and tuples into JSON-compatible values.

    Datetimes become ISO 8601 strings; dataclass properties are not included.
    """
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: to_jsonable(getattr(value, field.name))
            for field in dataclasses.fields(value)
        }
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [to_jsonable(item) for item in value]
    return value
