"""Coordinator for AMB Bellinzona: fetches at most once a day and persists the schedule."""

from __future__ import annotations

from datetime import date, datetime, timedelta
import logging
import random
from typing import Any

from amb_bellinzona import AMBBellinzona, AMBBellinzonaError, Tariff, TariffSchedule, TariffSlot

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN, FETCH_WINDOW_LENGTH, FETCH_WINDOW_START, RETRY_INTERVAL, STORAGE_VERSION

_LOGGER = logging.getLogger(__name__)

type AMBBellinzonaConfigEntry = ConfigEntry[AMBBellinzonaCoordinator]


def _window_start(day: date) -> datetime:
    return dt_util.start_of_local_day(day) + FETCH_WINDOW_START


def has_tomorrow(schedule: TariffSchedule, now: datetime) -> bool:
    """Return True when the schedule covers all of tomorrow (local days, DST-safe)."""
    day_after = dt_util.as_local(now).date() + timedelta(days=2)
    return schedule.end is not None and schedule.end >= dt_util.start_of_local_day(day_after)


def fetch_due(schedule: TariffSchedule | None, now: datetime) -> bool:
    """Return True when the API has (or may have) data we need."""
    if schedule is None or schedule.tariff_at(now) is None:
        return True
    return not has_tomorrow(schedule, now) and now >= _window_start(dt_util.as_local(now).date())


def next_fetch(schedule: TariffSchedule | None, now: datetime) -> datetime:
    """Return a random time in the next useful fetch window, or a short retry."""
    if schedule is None or schedule.tariff_at(now) is None:
        return now + RETRY_INTERVAL
    today = dt_util.as_local(now).date()
    if has_tomorrow(schedule, now):
        day = today + timedelta(days=1)
    elif now < _window_start(today):
        day = today
    else:
        return now + RETRY_INTERVAL
    # Spread installs over the window so they do not hit the API at the same second.
    return _window_start(day) + timedelta(seconds=random.uniform(0, FETCH_WINDOW_LENGTH.total_seconds()))


def _dump(schedule: TariffSchedule) -> list[dict[str, str]]:
    return [
        {"start": s.start.isoformat(), "end": s.end.isoformat(), "tariff": s.tariff.value}
        for s in schedule.slots
    ]


def _load(data: Any) -> TariffSchedule | None:
    try:
        return TariffSchedule(
            tuple(
                TariffSlot(datetime.fromisoformat(i["start"]), datetime.fromisoformat(i["end"]), Tariff(i["tariff"]))
                for i in data
            )
        )
    except (KeyError, TypeError, ValueError):
        _LOGGER.debug("Ignoring invalid stored tariff schedule")
        return None


class AMBBellinzonaCoordinator(DataUpdateCoordinator[TariffSchedule]):
    """Owns the fetch policy; entities read the schedule from `data`."""

    config_entry: AMBBellinzonaConfigEntry

    def __init__(self, hass: HomeAssistant, entry: AMBBellinzonaConfigEntry, client: AMBBellinzona) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=None,  # set after every update by next_fetch()
            always_update=False,
        )
        self.client = client
        self.store: Store[list[dict[str, str]]] = Store(hass, STORAGE_VERSION, DOMAIN)
        self._cached: TariffSchedule | None = None
        self._fetch_failing = False

    async def _async_setup(self) -> None:
        if (stored := await self.store.async_load()) is not None:
            self._cached = _load(stored)

    async def _async_update_data(self) -> TariffSchedule:
        now = dt_util.utcnow()
        schedule = self.data or self._cached
        if fetch_due(schedule, now):
            try:
                schedule = await self.client.async_get_schedule()
            except AMBBellinzonaError as err:
                self.update_interval = RETRY_INTERVAL
                if schedule is None or schedule.tariff_at(now) is None:
                    raise UpdateFailed(f"Error fetching tariff schedule: {err}") from err
                if not self._fetch_failing:
                    _LOGGER.warning("Fetching the tariff schedule failed, using the cached one: %s", err)
                    self._fetch_failing = True
                return schedule
            if self._fetch_failing:
                _LOGGER.info("Fetching the tariff schedule works again")
                self._fetch_failing = False
            await self.store.async_save(_dump(schedule))
        self.update_interval = next_fetch(schedule, now) - now
        return schedule

    @callback
    def async_quarter_hour(self, _now: datetime) -> None:
        """Re-evaluate entities at every slot boundary (no network)."""
        self.async_update_listeners()
