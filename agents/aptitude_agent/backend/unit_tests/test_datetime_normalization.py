from datetime import datetime, timezone

from backend.app.models.base import as_utc, utcnow


def test_mysql_naive_datetime_is_normalized_before_comparison():
    naive=datetime(2026,8,20,12,0,0)
    assert as_utc(naive).tzinfo==timezone.utc
    assert as_utc(naive)<utcnow()


def test_aware_datetime_is_normalized_to_utc():
    value=datetime(2026,8,20,17,30,0,tzinfo=timezone.utc)
    assert as_utc(value)==value
