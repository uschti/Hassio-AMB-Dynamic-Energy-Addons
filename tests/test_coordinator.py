"""Tests for the AMB Bellinzona fetch policy."""

from datetime import date, datetime, timedelta

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.amb_bellinzona.coordinator import fetch_due, has_tomorrow, next_fetch

from .conftest import make_schedule


def local(day: date, hour: int, minute: int = 0) -> datetime:
    """Return a local (Europe/Zurich) aware datetime."""
    return dt_util.start_of_local_day(day) + timedelta(hours=hour, minutes=minute)


TODAY = date(2026, 11, 14)
TOMORROW = date(2026, 11, 15)
DAY_AFTER = date(2026, 11, 16)


def today_only():
    return make_schedule(dt_util.start_of_local_day(TODAY), dt_util.start_of_local_day(TOMORROW))


def with_tomorrow():
    return make_schedule(dt_util.start_of_local_day(TODAY), dt_util.start_of_local_day(DAY_AFTER))


async def test_has_tomorrow(hass: HomeAssistant) -> None:
    now = local(TODAY, 14)
    assert not has_tomorrow(today_only(), now)
    assert has_tomorrow(with_tomorrow(), now)


async def test_has_tomorrow_dst_spring_forward(hass: HomeAssistant) -> None:
    """2027-03-28 has 23 h: tomorrow ends at local midnight, not +24 h."""
    day = date(2027, 3, 27)
    end = dt_util.start_of_local_day(date(2027, 3, 29))
    full = make_schedule(dt_util.start_of_local_day(day), end)
    short = make_schedule(dt_util.start_of_local_day(day), end - timedelta(minutes=15))
    assert has_tomorrow(full, local(day, 14))
    assert not has_tomorrow(short, local(day, 14))


async def test_fetch_due(hass: HomeAssistant) -> None:
    assert fetch_due(None, local(TODAY, 10))
    assert not fetch_due(today_only(), local(TODAY, 10))      # before the window, today is enough
    assert fetch_due(today_only(), local(TODAY, 12, 30))      # window open, tomorrow missing
    assert not fetch_due(with_tomorrow(), local(TODAY, 14))   # nothing new to get
    assert fetch_due(today_only(), local(TOMORROW, 1))        # cache no longer covers now


async def test_fetch_due_on_gap(hass: HomeAssistant) -> None:
    gap = make_schedule(dt_util.start_of_local_day(TODAY), local(TODAY, 9))
    assert fetch_due(gap, local(TODAY, 10))


async def test_next_fetch_with_tomorrow_is_in_tomorrows_window(hass: HomeAssistant) -> None:
    when = next_fetch(with_tomorrow(), local(TODAY, 14))
    assert local(TOMORROW, 12, 30) <= when < local(TOMORROW, 13, 30)


async def test_next_fetch_before_window_is_today(hass: HomeAssistant) -> None:
    when = next_fetch(today_only(), local(TODAY, 10))
    assert local(TODAY, 12, 30) <= when < local(TODAY, 13, 30)


async def test_next_fetch_retries_after_window_without_tomorrow(hass: HomeAssistant) -> None:
    now = local(TODAY, 14)
    assert next_fetch(today_only(), now) == now + timedelta(minutes=30)
    assert next_fetch(None, now) == now + timedelta(minutes=30)


async def test_next_fetch_retries_on_gap(hass: HomeAssistant) -> None:
    now = local(TODAY, 10)
    gap = make_schedule(dt_util.start_of_local_day(TODAY), local(TODAY, 9))
    assert next_fetch(gap, now) == now + timedelta(minutes=30)
