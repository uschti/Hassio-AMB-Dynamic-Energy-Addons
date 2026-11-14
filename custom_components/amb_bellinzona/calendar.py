"""Calendar of the AMB Bellinzona high-tariff periods."""

from __future__ import annotations

from datetime import UTC, datetime

from amb_bellinzona import Tariff

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import AMBBellinzonaConfigEntry
from .entity import AMBBellinzonaEntity

# Coordinator-driven: no parallel update limit needed.
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AMBBellinzonaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the calendar."""
    async_add_entities([AMBBellinzonaCalendar(entry.runtime_data, "high_tariff")])


class AMBBellinzonaCalendar(AMBBellinzonaEntity, CalendarEntity):
    """One event per high-tariff period of the cached schedule (today, and tomorrow once published)."""

    _attr_translation_key = "high_tariff"

    def _events(self, start: datetime, end: datetime) -> list[CalendarEvent]:
        return [
            CalendarEvent(
                start=dt_util.as_local(period.start), end=dt_util.as_local(period.end), summary=str(self.name)
            )
            for period in self.coordinator.data.periods()
            if period.tariff is Tariff.HIGH and period.end > start and period.start < end
        ]

    @property
    def event(self) -> CalendarEvent | None:
        """The current or next high-tariff period."""
        events = self._events(dt_util.utcnow(), datetime.max.replace(tzinfo=UTC))
        return events[0] if events else None

    async def async_get_events(self, hass: HomeAssistant, start_date: datetime, end_date: datetime) -> list[CalendarEvent]:
        """Return the high-tariff periods overlapping the requested range."""
        return self._events(start_date, end_date)
