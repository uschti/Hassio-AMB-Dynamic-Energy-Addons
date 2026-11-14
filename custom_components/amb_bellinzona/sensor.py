"""Sensors for the AMB Bellinzona dynamic tariff."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from amb_bellinzona import Tariff, TariffSchedule

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import AMBBellinzonaConfigEntry, AMBBellinzonaCoordinator
from .entity import AMBBellinzonaEntity

# Coordinator-driven: no parallel update limit needed.
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class AMBBellinzonaSensorEntityDescription(SensorEntityDescription):
    """Sensor description with a value computed from the schedule at a given time."""

    value_fn: Callable[[TariffSchedule, datetime], str | datetime | None]


def _next_change(schedule: TariffSchedule, now: datetime) -> datetime | None:
    change = schedule.next_change(now)
    return change.start if change else None


SENSORS: tuple[AMBBellinzonaSensorEntityDescription, ...] = (
    AMBBellinzonaSensorEntityDescription(
        key="tariff",
        translation_key="tariff",
        device_class=SensorDeviceClass.ENUM,
        options=[tariff.value for tariff in Tariff],
        value_fn=lambda schedule, now: schedule.tariff_at(now),
    ),
    AMBBellinzonaSensorEntityDescription(
        key="next_change",
        translation_key="next_change",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_next_change,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AMBBellinzonaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors."""
    async_add_entities(AMBBellinzonaSensor(entry.runtime_data, description) for description in SENSORS)


class AMBBellinzonaSensor(AMBBellinzonaEntity, SensorEntity):
    """A sensor derived from the tariff schedule and the current time."""

    entity_description: AMBBellinzonaSensorEntityDescription

    def __init__(self, coordinator: AMBBellinzonaCoordinator, description: AMBBellinzonaSensorEntityDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> str | datetime | None:
        """Compute the value for the current instant."""
        return self.entity_description.value_fn(self.coordinator.data, dt_util.utcnow())
