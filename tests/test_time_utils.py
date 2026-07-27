from datetime import UTC, datetime, timedelta, timezone

import sqlalchemy as sa

from app.time_utils import ensure_utc_datetime, reference_day_end, require_utc_datetime


def test_naive_datetime_is_interpreted_as_utc() -> None:
    value = datetime(2026, 7, 13, 9, 30)
    assert ensure_utc_datetime(value) == datetime(2026, 7, 13, 9, 30, tzinfo=UTC)


def test_aware_utc_datetime_is_stable() -> None:
    value = datetime(2026, 7, 13, 9, 30, tzinfo=UTC)
    assert ensure_utc_datetime(value) == value


def test_non_utc_offset_is_converted_and_can_cross_midnight() -> None:
    value = datetime(2026, 7, 14, 1, 30, tzinfo=timezone(timedelta(hours=3)))
    assert ensure_utc_datetime(value) == datetime(2026, 7, 13, 22, 30, tzinfo=UTC)


def test_iso_z_value_and_none_are_supported() -> None:
    assert ensure_utc_datetime("2026-07-13T09:30:00Z") == datetime(2026, 7, 13, 9, 30, tzinfo=UTC)
    assert ensure_utc_datetime(None) is None


def test_naive_and_aware_values_can_be_compared_after_normalization() -> None:
    naive = require_utc_datetime(datetime(2026, 7, 13, 8))
    aware = require_utc_datetime(datetime(2026, 7, 13, 9, tzinfo=UTC))
    assert naive < aware


def test_sqlite_naive_datetime_is_normalized() -> None:
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    metadata = sa.MetaData()
    events = sa.Table(
        "events",
        metadata,
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
    )
    metadata.create_all(engine)
    expected = datetime(2026, 7, 13, 9, 30, tzinfo=UTC)
    with engine.begin() as connection:
        connection.execute(events.insert().values(observed_at=expected))
        loaded = connection.scalar(sa.select(events.c.observed_at))
    assert loaded is not None and loaded.tzinfo is None
    assert ensure_utc_datetime(loaded) == expected


def test_reference_day_end_is_inclusive_utc_boundary() -> None:
    boundary = reference_day_end(datetime(2026, 7, 13).date())
    assert boundary.tzinfo is UTC
    assert boundary.date().isoformat() == "2026-07-13"
    assert boundary.hour == 23
