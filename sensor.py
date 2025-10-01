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


class AMBCurrentDurationSensor(SensorEntity):
    """Sensor for remaining time in current price period with active polling."""

    def __init__(
            self,
            coordinator: AMBDataUpdateCoordinator,
            config_entry: ConfigEntry,
    ) -> None:
        """Initialize the duration sensor."""
        self._coordinator = coordinator
        self._config_entry = config_entry
        self._attr_name = "Current Price Period Remaining"
        self._attr_unique_id = f"{config_entry.entry_id}_{SENSOR_CURRENT_DURATION}"
        self._attr_native_unit_of_measurement = UnitOfTime.MINUTES
        self._attr_device_class = SensorDeviceClass.DURATION
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:timer"

        # Enable active polling every 30 seconds
        self._attr_should_poll = True

    @property
    def available(self) -> bool:
        """Return if sensor is available."""
        return self._coordinator.last_update_success

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

    async def async_update(self) -> None:
        """Update the sensor - chiamata automaticamente da HA ogni 30 secondi."""
        # Forza aggiornamento ogni volta che viene chiamato
        pass

    @property
    def native_value(self) -> int | None:
        """Return remaining minutes in current price period."""
        if not self._coordinator.data:
            return None

        # Calcola il tempo rimanente in tempo reale ADESSO
        remaining = self._calculate_remaining_time()

        # Log per debug
        if remaining is not None:
            _LOGGER.debug(f"Remaining time calculated: {remaining} minutes")

        return max(0, remaining) if remaining is not None else None

    def _calculate_remaining_time(self) -> int | None:
        """Calculate remaining time in current period in real-time."""
        if not self._coordinator.data:
            return None

        forecasts = self._coordinator.data.get("forecasts", [])
        now = dt_util.now()
        today_str = now.strftime("%Y-%m-%d")
        current_minutes = now.hour * 60 + now.minute

        _LOGGER.debug(f"Calculating remaining time for {today_str} at {now.hour:02d}:{now.minute:02d}")

        # Trova il periodo corrente
        for day in forecasts:
            if day.get("date") == today_str:
                for period in day.get("forecast", []):
                    hour_range = period.get("hour_range", "")
                    if " - " in hour_range:
                        start_str, end_str = hour_range.split(" - ")
                        start_minutes = self._time_to_minutes(start_str)

                        if end_str == "23:59":
                            end_minutes = 24 * 60  # Fine giornata
                        else:
                            end_minutes = self._time_to_minutes(end_str)

                        # Controlla se siamo in questo periodo
                        if start_minutes <= current_minutes < end_minutes:
                            remaining = end_minutes - current_minutes
                            _LOGGER.debug(f"Found current period: {hour_range}, remaining: {remaining} min")
                            return remaining

        _LOGGER.debug("No current period found")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        if not self._coordinator.data:
            return {}

        attributes = {}
        remaining_minutes = self.native_value

        if remaining_minutes is not None:
            # Formato human readable
            if remaining_minutes >= 60:
                hours = remaining_minutes // 60
                minutes = remaining_minutes % 60
                attributes["remaining_formatted"] = f"{hours}h {minutes}m"
            else:
                attributes["remaining_formatted"] = f"{remaining_minutes}m"

            # Trova i dettagli del periodo corrente
            current_period_info = self._get_current_period_info()
            if current_period_info:
                attributes.update(current_period_info)

        # Timestamp ultimo calcolo
        attributes["last_calculated"] = dt_util.now().isoformat()

        return attributes

    def _get_current_period_info(self) -> dict[str, Any] | None:
        """Get current period information."""
        if not self._coordinator.data:
            return None

        forecasts = self._coordinator.data.get("forecasts", [])
        now = dt_util.now()
        today_str = now.strftime("%Y-%m-%d")
        current_minutes = now.hour * 60 + now.minute

        for day in forecasts:
            if day.get("date") == today_str:
                for period in day.get("forecast", []):
                    hour_range = period.get("hour_range", "")
                    if " - " in hour_range:
                        start_str, end_str = hour_range.split(" - ")
                        start_minutes = self._time_to_minutes(start_str)

                        if end_str == "23:59":
                            end_minutes = 24 * 60
                        else:
                            end_minutes = self._time_to_minutes(end_str)

                        if start_minutes <= current_minutes < end_minutes:
                            return {
                                "current_period_start": start_str,
                                "current_period_end": end_str,
                                "current_period_price": period.get("price", "").upper(),
                            }

        return None

    @staticmethod
    def _time_to_minutes(time_str: str) -> int:
        """Convert HH:MM to minutes since midnight."""
        try:
            hours, minutes = map(int, time_str.split(":"))
            return hours * 60 + minutes
        except (ValueError, AttributeError):
            return 0


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
