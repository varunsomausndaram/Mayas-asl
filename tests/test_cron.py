from datetime import datetime, timezone

from jarvis.scheduler.cron import CronTrigger, iter_next


def test_parse_and_match_minute():
    t = CronTrigger.parse("*/5 * * * *")
    d = datetime(2026, 4, 18, 9, 10, tzinfo=timezone.utc)
    assert t.matches(d)
    d2 = datetime(2026, 4, 18, 9, 11, tzinfo=timezone.utc)
    assert not t.matches(d2)


def test_next_after():
    t = CronTrigger.parse("0 9 * * *")
    n = t.next_after(datetime(2026, 4, 18, 8, 59, tzinfo=timezone.utc))
    assert n.hour == 9 and n.minute == 0


def test_weekday_and_day_or():
    t = CronTrigger.parse("0 0 15 * 1")  # 15th OR monday
    # April 18, 2026 is a Saturday; so only if day = 15 it matches.
    assert t.matches(datetime(2026, 4, 15, 0, 0, tzinfo=timezone.utc))
    # Monday April 20, 2026
    assert t.matches(datetime(2026, 4, 20, 0, 0, tzinfo=timezone.utc))


def test_iter_next():
    t = CronTrigger.parse("0 * * * *")  # every hour at 0 min
    start = datetime(2026, 4, 18, 9, 30, tzinfo=timezone.utc)
    values = list(iter_next(t, start, 3))
    assert [v.hour for v in values] == [10, 11, 12]


def test_invalid_expression():
    import pytest

    with pytest.raises(ValueError):
        CronTrigger.parse("bad")
    with pytest.raises(ValueError):
        CronTrigger.parse("0 0 0 0 0")  # day 0 invalid
