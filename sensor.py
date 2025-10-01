"""Sensor platform for AMB Dynamic Energy integration."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    MANUFACTURER,
    MODEL,
    SENSOR_CURRENT_PRICE,
    SENSOR_CURRENT_DURATION,
    SENSOR_PRICE_SCHEDULE,
    ATTR_CURRENT_PRICE,
    ATTR_FORECASTS,
    ATTR_NEXT_CHANGE,
    ATTR_CURRENT_RANGE,
    ATTR_TODAY_SCHEDULE,
    ATTR_TOMORROW_SCHEDULE,
    ATTR_LAST_UPDATED,
)
from .coordinator import AMBDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AMB Dynamic Energy sensors based on a config entry."""
    coordinator: AMBDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    sensors = [
        AMBCurrentPriceSensor(coordinator, config_entry),
        AMBCurrentDurationSensor(coordinator, config_entry),
        AMBPriceScheduleSensor(coordinator, config_entry),
    ]

    async_add_entities(sensors, update_before_add=True)


class AMBBaseSensor(CoordinatorEntity[AMBDataUpdateCoordinator], SensorEntity):
    """Base class for AMB Dynamic Energy sensors."""

    def __init__(
            self,
            coordinator: AMBDataUpdateCoordinator,
            config_entry: ConfigEntry,
            sensor_type: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._sensor_type = sensor_type
        self._attr_unique_id = f"{config_entry.entry_id}_{sensor_type}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._config_entry.entry_id)},
            name="AMB Dynamic Energy",
            manufacturer=MANUFACTURER,
            model=MODEL,
            sw_version="1.0.0",
        )


class AMBCurrentPriceSensor(AMBBaseSensor):
    """Sensor for current electricity price level."""

    def __init__(
            self,
            coordinator: AMBDataUpdateCoordinator,
            config_entry: ConfigEntry,
    ) -> None:
        """Initialize the current price sensor."""
        super().__init__(coordinator, config_entry, SENSOR_CURRENT_PRICE)
        self._attr_name = "Current Energy Price"
        self._attr_icon = "mdi:flash"

    @property
    def native_value(self) -> str | None:
        """Return the current price level."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get("current_price", "unknown").upper()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        if not self.coordinator.data:
            return {}

        attributes = {
            ATTR_LAST_UPDATED: self.coordinator.data.get("last_updated"),
        }

        current_period = self.coordinator.data.get("current_period")
        if current_period:
            attributes[ATTR_CURRENT_RANGE] = (
                f"{current_period['start']} - {current_period['end']}"
            )

        next_change = self.coordinator.data.get("next_change")
        if next_change:
            attributes[ATTR_NEXT_CHANGE] = (
                f"{next_change['date']} {next_change['time']} ({next_change['price'].upper()})"
            )

        return attributes


class AMBCurrentDurationSensor(AMBBaseSensor):
    """Sensor for remaining time in current price period."""

    def __init__(
            self,
            coordinator: AMBDataUpdateCoordinator,
            config_entry: ConfigEntry,
    ) -> None:
        """Initialize the duration sensor."""
        super().__init__(coordinator, config_entry, SENSOR_CURRENT_DURATION)
        self._attr_name = "Current Price Period Remaining"
        self._attr_native_unit_of_measurement = UnitOfTime.MINUTES
        self._attr_device_class = SensorDeviceClass.DURATION
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:timer"

    @property
    def native_value(self) -> int | None:
        """Return remaining minutes in current price period."""
        if not self.coordinator.data:
            return None

        current_period = self.coordinator.data.get("current_period")
        if not current_period:
            return None

        return current_period.get("remaining_minutes", 0)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        if not self.coordinator.data:
            return {}

        attributes = {}
        current_period = self.coordinator.data.get("current_period")

        if current_period:
            remaining_minutes = current_period.get("remaining_minutes", 0)

            # Convert to human readable format
            if remaining_minutes >= 60:
                hours = remaining_minutes // 60
                minutes = remaining_minutes % 60
                attributes["remaining_formatted"] = f"{hours}h {minutes}m"
            else:
                attributes["remaining_formatted"] = f"{remaining_minutes}m"

            attributes["current_period_start"] = current_period.get("start")
            attributes["current_period_end"] = current_period.get("end")
            attributes["current_period_price"] = current_period.get("price", "").upper()

        return attributes


class AMBPriceScheduleSensor(AMBBaseSensor):
    """Sensor for complete price schedule and forecasts."""

    def __init__(
            self,
            coordinator: AMBDataUpdateCoordinator,
            config_entry: ConfigEntry,
    ) -> None:
        """Initialize the schedule sensor."""
        super().__init__(coordinator, config_entry, SENSOR_PRICE_SCHEDULE)
        self._attr_name = "Energy Price Schedule"
        self._attr_icon = "mdi:calendar-clock"

    @property
    def native_value(self) -> str | None:
        """Return summary of schedule."""
        if not self.coordinator.data:
            return "No data"

        today_schedule = self.coordinator.data.get("today_schedule", [])
        tomorrow_schedule = self.coordinator.data.get("tomorrow_schedule", [])

        schedule_summary = f"Today: {len(today_schedule)} periods"
        if tomorrow_schedule:
            schedule_summary += f", Tomorrow: {len(tomorrow_schedule)} periods"

        return schedule_summary

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return complete schedule data for use in dashboard cards."""
        if not self.coordinator.data:
            return {}

        attributes = {
            ATTR_TODAY_SCHEDULE: self.coordinator.data.get("today_schedule", []),
            ATTR_TOMORROW_SCHEDULE: self.coordinator.data.get("tomorrow_schedule", []),
            ATTR_FORECASTS: self.coordinator.data.get("forecasts", []),
            ATTR_LAST_UPDATED: self.coordinator.data.get("last_updated"),
        }

        # Add chart data for graphing
        attributes["chart_data"] = self._generate_chart_data()

        return attributes

    def _generate_chart_data(self) -> list[dict[str, Any]]:
        """Generate data points for charts."""
        if not self.coordinator.data:
            return []

        chart_data = []
        forecasts = self.coordinator.data.get("forecasts", [])

        for day in forecasts:
            date_str = day.get("date")
            for period in day.get("forecast", []):
                hour_range = period.get("hour_range", "")
                price = period.get("price", "unknown")

                if " - " in hour_range:
                    start_str, end_str = hour_range.split(" - ")

                    # Convert to price values for charting (low=0, high=1)
                    price_value = 1 if price == "high" else 0

                    chart_data.append({
                        "date": date_str,
                        "start_time": start_str,
                        "end_time": end_str,
                        "price": price,
                        "price_value": price_value,
                        "timestamp": f"{date_str}T{start_str}:00"
                    })

        return chart_data
