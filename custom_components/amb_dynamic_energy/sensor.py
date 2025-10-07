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
# UnitOfTime is kept for minutes display
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from custom_components.amb_dynamic_energy.const import (
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
from custom_components.amb_dynamic_energy.coordinator import AMBDataUpdateCoordinator

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
            name="AMB Dynamic Energy Rate",
            manufacturer=MANUFACTURER,
            model=MODEL,
            sw_version="1.1.0",
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
        self._attr_should_poll = True  # update ~ every 30s

    @property
    def available(self) -> bool:
        return self._coordinator.last_update_success

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._config_entry.entry_id)},
            name="AMB Dynamic Energy Rate",
            manufacturer=MANUFACTURER,
            model=MODEL,
            sw_version="1.1.0",
        )

    async def async_update(self) -> None:
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
        attrs[ATTR_LAST_UPDATED] = self._coordinator.data.get("last_updated")

        current_info = self._get_current_period_info()
        if current_info:
            attrs[ATTR_CURRENT_RANGE] = f"{current_info['start']} - {current_info['end']}"

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
    """Remaining time in current price period, merging contiguous same-price slots across midnight."""

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
        self._attr_should_poll = True  # update ~ every 30s

    @property
    def available(self) -> bool:
        return self._coordinator.last_update_success

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._config_entry.entry_id)},
            name="AMB Dynamic Energy Rate",
            manufacturer=MANUFACTURER,
            model=MODEL,
            sw_version="1.1.0",
        )

    async def async_update(self) -> None:
        return

    @property
    def native_value(self) -> int | None:
        """Return remaining minutes in the merged current block (today + contiguous tomorrow if same price)."""
        if not self._coordinator.data:
            return None
        remaining = self._calculate_merged_remaining()
        if remaining is not None:
            _LOGGER.debug("Merged remaining time: %s minutes", remaining)
        return max(0, remaining) if remaining is not None else None

    def _calculate_merged_remaining(self) -> int | None:
        """Find current period today, then merge with following contiguous same-price slots today and tomorrow."""
        forecasts = self._coordinator.data.get("forecasts", [])
        now = dt_util.now()
        today_str = now.strftime("%Y-%m-%d")
        tomorrow_str = (now + timedelta(days=1)).strftime("%Y-%m-%d")
        current_minutes = now.hour * 60 + now.minute

        # Build today schedule
        today_sched = self._build_schedule_for_date(forecasts, today_str)
        if not today_sched:
            return None

        # Find current slot in today schedule
        idx = None
        for i, slot in enumerate(today_sched):
            if slot["start_m"] <= current_minutes < slot["end_m"]:
                idx = i
                break
        if idx is None:
            return None

        current_price = today_sched[idx]["price"]
        merged_end = today_sched[idx]["end_m"]

        # Merge with following slots today if contiguous and same price
        i = idx + 1
        while i < len(today_sched):
            nxt = today_sched[i]
            if nxt["start_m"] == merged_end and nxt["price"] == current_price:
                merged_end = nxt["end_m"]
                i += 1
            else:
                break

        # If merged_end reaches end of day and tomorrow is available, merge with tomorrow's contiguous head
        if merged_end >= 24 * 60:
            tomorrow_sched = self._build_schedule_for_date(forecasts, tomorrow_str)
            if tomorrow_sched:
                j = 0
                # Start of tomorrow must be contiguous (00:00) and same price
                while j < len(tomorrow_sched):
                    slot = tomorrow_sched[j]
                    if j == 0 and slot["start_m"] == 0 and slot["price"] == current_price:
                        # Extend beyond midnight: add minutes from tomorrow
                        merged_end = 24 * 60 + slot["end_m"]
                        j += 1
                        # Chain more contiguous same-price slots tomorrow if needed
                        while j < len(tomorrow_sched):
                            next_slot = tomorrow_sched[j]
                            prev_end = merged_end - 24 * 60  # end within tomorrow day-space
                            if next_slot["start_m"] == prev_end and next_slot["price"] == current_price:
                                merged_end = 24 * 60 + next_slot["end_m"]
                                j += 1
                            else:
                                break
                        break
                    else:
                        break

        # Remaining is merged_end - now
        return merged_end - current_minutes

    def _build_schedule_for_date(self, forecasts: list, date_str: str) -> list[dict[str, Any]]:
        """Return normalized schedule list: [{start_m, end_m, price}] for given date."""
        for day in forecasts:
            if day.get("date") == date_str:
                result: list[dict[str, Any]] = []
                for period in day.get("forecast", []):
                    rng = period.get("hour_range", "")
                    if " - " not in rng:
                        continue
                    start_str, end_str = rng.split(" - ")
                    start_m = self._time_to_minutes(start_str)
                    end_m = 24 * 60 if end_str == "23:59" else self._time_to_minutes(end_str)
                    result.append({"start_m": start_m, "end_m": end_m, "price": period.get("price", "unknown")})
                # Ensure sorted and contiguous logic works
                result.sort(key=lambda x: x["start_m"])
                return result
        return []

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Attributes include formatted remaining and merged-until timestamp for debug."""
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

        # Also expose current merged end human-friendly for troubleshooting
        merged_end_info = self._current_merged_end_info()
        if merged_end_info:
            attrs.update(merged_end_info)

        return attrs

    def _current_merged_end_info(self) -> dict[str, Any] | None:
        """Return details about the merged end window for visibility."""
        forecasts = self._coordinator.data.get("forecasts", [])
        now = dt_util.now()
        today_str = now.strftime("%Y-%m-%d")
        tomorrow_str = (now + timedelta(days=1)).strftime("%Y-%m-%d")
        current_minutes = now.hour * 60 + now.minute

        today_sched = self._build_schedule_for_date(forecasts, today_str)
        if not today_sched:
            return None

        # Find current slot
        idx = None
        for i, slot in enumerate(today_sched):
            if slot["start_m"] <= current_minutes < slot["end_m"]:
                idx = i
                break
        if idx is None:
            return None

        current_price = today_sched[idx]["price"]
        merged_end_m = today_sched[idx]["end_m"]

        # Merge within today
        i = idx + 1
        while i < len(today_sched):
            nxt = today_sched[i]
            if nxt["start_m"] == merged_end_m and nxt["price"] == current_price:
                merged_end_m = nxt["end_m"]
                i += 1
            else:
                break

        merged_date = today_str
        # Merge into tomorrow head if contiguous
        if merged_end_m >= 24 * 60:
            tomorrow_sched = self._build_schedule_for_date(forecasts, tomorrow_str)
            if tomorrow_sched and tomorrow_sched[0]["start_m"] == 0 and tomorrow_sched[0]["price"] == current_price:
                merged_end_m = 24 * 60 + tomorrow_sched[0]["end_m"]
                j = 1
                while j < len(tomorrow_sched):
                    prev_end = merged_end_m - 24 * 60
                    nxt = tomorrow_sched[j]
                    if nxt["start_m"] == prev_end and nxt["price"] == current_price:
                        merged_end_m = 24 * 60 + nxt["end_m"]
                        j += 1
                    else:
                        break
                merged_date = tomorrow_str

        # Build HH:MM end for attributes
        end_total_m = merged_end_m
        if end_total_m < 24 * 60:
            end_h = end_total_m // 60
            end_min = end_total_m % 60
            end_label = f"{today_str} {end_h:02d}:{end_min:02d}"
        else:
            within_tomorrow = end_total_m - 24 * 60
            end_h = within_tomorrow // 60
            end_min = within_tomorrow % 60
            end_label = f"{tomorrow_str} {end_h:02d}:{end_min:02d}"

        return {
            "merged_until": end_label,
            "merged_price": current_price.upper(),
        }

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
