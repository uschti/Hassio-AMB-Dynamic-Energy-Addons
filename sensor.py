"""Sensor platform for AMB Dynamic Energy integration."""
from __future__ import annotations

import logging
from datetime import timedelta
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

    sensors: list[SensorEntity] = [
        AMBCurrentPriceSensor(coordinator, config_entry),
        AMBCurrentDurationSensor(coordinator, config_entry),
        AMBPriceScheduleSensor(coordinator, config_entry),
    ]

    async_add_entities(sensors, update_before_add=True)


class AMBBaseSensor(CoordinatorEntity[AMBDataUpdateCoordinator], SensorEntity):
    """Base class for AMB Dynamic Energy sensors that rely on coordinator data."""

    def __init__(
            self,
            coordinator: AMBDataUpdateCoordinator,
            config_entry: ConfigEntry,
            sensor_type: str,
    ) -> None:
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._sensor_type = sensor_type
        self._attr_unique_id = f"{config_entry.entry_id}_{sensor_type}"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._config_entry.entry_id)},
            name="AMB Dynamic Energy",
            manufacturer=MANUFACTURER,
            model=MODEL,
            sw_version="1.0.0",
        )


class AMBCurrentPriceSensor(SensorEntity):
    """Current electricity price level computed in real-time with active polling."""

    def __init__(
            self,
            coordinator: AMBDataUpdateCoordinator,
            config_entry: ConfigEntry,
    ) -> None:
        self._coordinator = coordinator
        self._config_entry = config_entry
        self._attr_name = "Current Energy Price"
        self._attr_unique_id = f"{config_entry.entry_id}_{SENSOR_CURRENT_PRICE}"
        self._attr_icon = "mdi:flash"
        # Attiva polling per aggiornare ~ ogni 30s (default scan interval dei sensori)
        self._attr_should_poll = True

    @property
    def available(self) -> bool:
        # L’entità è disponibile quando l’ultimo refresh del coordinator è riuscito
        return self._coordinator.last_update_success

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._config_entry.entry_id)},
            name="AMB Dynamic Energy",
            manufacturer=MANUFACTURER,
            model=MODEL,
            sw_version="1.0.0",
        )

    async def async_update(self) -> None:
        # Nessuna chiamata I/O qui: il valore viene calcolato in base ai forecasts correnti in memoria
        return

    @property
    def native_value(self) -> str | None:
        """Return LOW/HIGH computed from the current time and today's forecast."""
        if not self._coordinator.data:
            return None
        price = self._calculate_current_price()
        _LOGGER.debug("AMBCurrentPriceSensor computed price: %s", price)
        return price.upper() if price else None

    def _calculate_current_price(self) -> str | None:
        """Calculate the current price by matching now against today's forecast ranges."""
        forecasts = self._coordinator.data.get("forecasts", [])
        now = dt_util.now()
        today_str = now.strftime("%Y-%m-%d")
        current_minutes = now.hour * 60 + now.minute

        for day in forecasts:
            if day.get("date") == today_str:
                for period in day.get("forecast", []):
                    rng = period.get("hour_range", "")
                    if " - " not in rng:
                        continue
                    start_str, end_str = rng.split(" - ")
                    start_m = self._time_to_minutes(start_str)
                    end_m = 24 * 60 if end_str == "23:59" else self._time_to_minutes(end_str)
                    if start_m <= current_minutes < end_m:
                        return period.get("price", "unknown")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose current range, next change and last update time."""
        if not self._coordinator.data:
            return {}

        attrs: dict[str, Any] = {"last_calculated": dt_util.now().isoformat()}

        # last_updated dal coordinator (quando i dati sono stati fetchati)
        attrs[ATTR_LAST_UPDATED] = self._coordinator.data.get("last_updated")

        # Range corrente
        current_info = self._get_current_period_info()
        if current_info:
            attrs[ATTR_CURRENT_RANGE] = f"{current_info['start']} - {current_info['end']}"

        # Prossimo cambio
        next_change = self._find_next_change()
        if next_change:
            attrs[ATTR_NEXT_CHANGE] = (
                f"{next_change['date']} {next_change['time']} ({next_change['price'].upper()})"
            )

        return attrs

    def _get_current_period_info(self) -> dict[str, Any] | None:
        forecasts = self._coordinator.data.get("forecasts", [])
        now = dt_util.now()
        today_str = now.strftime("%Y-%m-%d")
        current_minutes = now.hour * 60 + now.minute

        for day in forecasts:
            if day.get("date") == today_str:
                for period in day.get("forecast", []):
                    rng = period.get("hour_range", "")
                    if " - " not in rng:
                        continue
                    start_str, end_str = rng.split(" - ")
                    start_m = self._time_to_minutes(start_str)
                    end_m = 24 * 60 if end_str == "23:59" else self._time_to_minutes(end_str)
                    if start_m <= current_minutes < end_m:
                        return {"start": start_str, "end": end_str, "price": period.get("price")}
        return None

    def _find_next_change(self) -> dict[str, Any] | None:
        forecasts = self._coordinator.data.get("forecasts", [])
        now = dt_util.now()
        today_str = now.strftime("%Y-%m-%d")
        tomorrow_str = (now + timedelta(days=1)).strftime("%Y-%m-%d")
        current_minutes = now.hour * 60 + now.minute

        # Restanti intervalli di oggi
        for day in forecasts:
            if day.get("date") == today_str:
                for period in day.get("forecast", []):
                    rng = period.get("hour_range", "")
                    if " - " not in rng:
                        continue
                    start_str, _ = rng.split(" - ")
                    start_m = self._time_to_minutes(start_str)
                    if start_m > current_minutes:
                        return {"time": start_str, "price": period.get("price"), "date": today_str}

        # Primo intervallo di domani
        for day in forecasts:
            if day.get("date") == tomorrow_str:
                fc = day.get("forecast", [])
                if not fc:
                    break
                rng = fc[0].get("hour_range", "")
                if " - " in rng:
                    start_str, _ = rng.split(" - ")
                    return {"time": start_str, "price": fc[0].get("price"), "date": tomorrow_str}

        return None

    @staticmethod
    def _time_to_minutes(time_str: str) -> int:
        try:
            h, m = map(int, time_str.split(":"))
            return h * 60 + m
        except Exception:
            return 0


class AMBCurrentDurationSensor(SensorEntity):
    """Remaining time in current price period with active polling."""

    def __init__(
            self,
            coordinator: AMBDataUpdateCoordinator,
            config_entry: ConfigEntry,
    ) -> None:
        self._coordinator = coordinator
        self._config_entry = config_entry
        self._attr_name = "Current Price Period Remaining"
        self._attr_unique_id = f"{config_entry.entry_id}_{SENSOR_CURRENT_DURATION}"
        self._attr_native_unit_of_measurement = UnitOfTime.MINUTES
        self._attr_device_class = SensorDeviceClass.DURATION
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:timer"
        self._attr_should_poll = True  # polling ~ ogni 30s

    @property
    def available(self) -> bool:
        return self._coordinator.last_update_success

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._config_entry.entry_id)},
            name="AMB Dynamic Energy",
            manufacturer=MANUFACTURER,
            model=MODEL,
            sw_version="1.0.0",
        )

    async def async_update(self) -> None:
        return

    @property
    def native_value(self) -> int | None:
        if not self._coordinator.data:
            return None
        remaining = self._calculate_remaining_time()
        if remaining is not None:
            _LOGGER.debug("Remaining time calculated: %s minutes", remaining)
        return max(0, remaining) if remaining is not None else None

    def _calculate_remaining_time(self) -> int | None:
        if not self._coordinator.data:
            return None
        forecasts = self._coordinator.data.get("forecasts", [])
        now = dt_util.now()
        today_str = now.strftime("%Y-%m-%d")
        current_minutes = now.hour * 60 + now.minute

        for day in forecasts:
            if day.get("date") == today_str:
                for period in day.get("forecast", []):
                    rng = period.get("hour_range", "")
                    if " - " not in rng:
                        continue
                    start_str, end_str = rng.split(" - ")
                    start_m = self._time_to_minutes(start_str)
                    end_m = 24 * 60 if end_str == "23:59" else self._time_to_minutes(end_str)
                    if start_m <= current_minutes < end_m:
                        return end_m - current_minutes
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if not self._coordinator.data:
            return {}
        attrs: dict[str, Any] = {"last_calculated": dt_util.now().isoformat()}
        remaining = self.native_value
        if remaining is not None:
            if remaining >= 60:
                hours = remaining // 60
                minutes = remaining % 60
                attrs["remaining_formatted"] = f"{hours}h {minutes}m"
            else:
                attrs["remaining_formatted"] = f"{remaining}m"

            info = self._get_current_period_info()
            if info:
                attrs.update(
                    {
                        "current_period_start": info["start"],
                        "current_period_end": info["end"],
                        "current_period_price": info.get("price", "").upper(),
                    }
                )
        return attrs

    def _get_current_period_info(self) -> dict[str, Any] | None:
        if not self._coordinator.data:
            return None
        forecasts = self._coordinator.data.get("forecasts", [])
        now = dt_util.now()
        today_str = now.strftime("%Y-%m-%d")
        current_minutes = now.hour * 60 + now.minute

        for day in forecasts:
            if day.get("date") == today_str:
                for period in day.get("forecast", []):
                    rng = period.get("hour_range", "")
                    if " - " not in rng:
                        continue
                    start_str, end_str = rng.split(" - ")
                    start_m = self._time_to_minutes(start_str)
                    end_m = 24 * 60 if end_str == "23:59" else self._time_to_minutes(end_str)
                    if start_m <= current_minutes < end_m:
                        return {"start": start_str, "end": end_str, "price": period.get("price", "")}
        return None

    @staticmethod
    def _time_to_minutes(time_str: str) -> int:
        try:
            h, m = map(int, time_str.split(":"))
            return h * 60 + m
        except Exception:
            return 0


class AMBPriceScheduleSensor(AMBBaseSensor):
    """Sensor for complete price schedule and forecasts (for charts/UI)."""

    def __init__(
            self,
            coordinator: AMBDataUpdateCoordinator,
            config_entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator, config_entry, SENSOR_PRICE_SCHEDULE)
        self._attr_name = "Energy Price Schedule"
        self._attr_icon = "mdi:calendar-clock"

    @property
    def native_value(self) -> str | None:
        if not self.coordinator.data:
            return "No data"
        today_schedule = self.coordinator.data.get("today_schedule", [])
        tomorrow_schedule = self.coordinator.data.get("tomorrow_schedule", [])
        summary = f"Today: {len(today_schedule)} periods"
        if tomorrow_schedule:
            summary += f", Tomorrow: {len(tomorrow_schedule)} periods"
        return summary

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if not self.coordinator.data:
            return {}
        attrs = {
            ATTR_TODAY_SCHEDULE: self.coordinator.data.get("today_schedule", []),
            ATTR_TOMORROW_SCHEDULE: self.coordinator.data.get("tomorrow_schedule", []),
            ATTR_FORECASTS: self.coordinator.data.get("forecasts", []),
            ATTR_LAST_UPDATED: self.coordinator.data.get("last_updated"),
        }
        attrs["chart_data"] = self._generate_chart_data()
        return attrs

    def _generate_chart_data(self) -> list[dict[str, Any]]:
        if not self.coordinator.data:
            return []
        chart_data: list[dict[str, Any]] = []
        forecasts = self.coordinator.data.get("forecasts", [])
        for day in forecasts:
            date_str = day.get("date")
            for period in day.get("forecast", []):
                rng = period.get("hour_range", "")
                price = period.get("price", "unknown")
                if " - " not in rng:
                    continue
                start_str, end_str = rng.split(" - ")
                price_value = 1 if price == "high" else 0
                chart_data.append(
                    {
                        "date": date_str,
                        "start_time": start_str,
                        "end_time": end_str,
                        "price": price,
                        "price_value": price_value,
                        "timestamp": f"{date_str}T{start_str}:00",
                    }
                )
        return chart_data
