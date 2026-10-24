from __future__ import annotations

from datetime import UTC, datetime


def require_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be blank.")
    return normalized


def require_positive_int(value: int, field_name: str) -> int:
    if isinstance(value, bool) or value < 1:
        raise ValueError(f"{field_name} must be a positive integer.")
    return value


def require_non_negative_float(value: float, field_name: str) -> float:
    if isinstance(value, bool) or value < 0:
        raise ValueError(f"{field_name} must be zero or greater.")
    return float(value)


def require_score(value: float | None, field_name: str) -> float | None:
    if value is None:
        return None
    score = float(value)
    if not 0 <= score <= 10:
        raise ValueError(f"{field_name} must be between 0 and 10.")
    return score


def require_aware_datetime(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include a timezone.")
    return value.astimezone(UTC)


def utc_now() -> datetime:
    return datetime.now(UTC)
