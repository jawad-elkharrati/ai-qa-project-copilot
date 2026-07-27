from __future__ import annotations

from datetime import UTC, date, datetime, time


def ensure_utc_datetime(value: datetime | str | None) -> datetime | None:
    """Return a timezone-aware UTC datetime.

    SQLite may return naive datetimes even for timezone-aware SQLAlchemy columns.
    The application convention is to interpret every naive value as UTC.
    """

    if value is None:
        return None
    parsed = value
    if isinstance(value, str):
        normalized = value.strip()
        if normalized.endswith(("Z", "z")):
            normalized = f"{normalized[:-1]}+00:00"
        parsed = datetime.fromisoformat(normalized)
    if not isinstance(parsed, datetime):
        raise TypeError(f"expected datetime, ISO string or None, got {type(value).__name__}")
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def require_utc_datetime(value: datetime | str) -> datetime:
    normalized = ensure_utc_datetime(value)
    if normalized is None:  # pragma: no cover - protected by the input type
        raise ValueError("datetime value is required")
    return normalized


def reference_day_end(value: date) -> datetime:
    """Return the inclusive UTC boundary used for date-based QA snapshots."""

    return datetime.combine(value, time.max, tzinfo=UTC)
