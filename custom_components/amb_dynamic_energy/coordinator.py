"""DataUpdateCoordinator for AMB Dynamic Energy integration."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    DEFAULT_API_URL,
    DEFAULT_TIMEOUT,
    DEFAULT_UPDATE_INTERVAL,
    RETRY_ATTEMPTS,
    RETRY_INTERVAL,
    EXTENDED_RETRY_ATTEMPTS,
    EXTENDED_RETRY_INTERVAL,
    CONF_API_URL,
    CONF_UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class AMBDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching AMB data from API."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize."""
        self.config_entry = config_entry
        self.api_url = config_entry.data.get(CONF_API_URL, DEFAULT_API_URL)

        update_interval_seconds = config_entry.data.get(
            CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL.total_seconds()
        )
        update_interval = timedelta(seconds=update_interval_seconds)

        self._retry_count = 0
        self._extended_retry_count = 0

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        try:
            return await self._fetch_data_with_retry()
        except Exception as exception:
            raise UpdateFailed(exception) from exception

    async def _fetch_data_with_retry(self) -> dict[str, Any]:
        """Fetch data with retry logic."""
        for attempt in range(1, RETRY_ATTEMPTS + 1):
            try:
                data = await self._fetch_data()
                # Reset retry counts on success
                self._retry_count = 0
                self._extended_retry_count = 0
                return self._process_data(data)

            except aiohttp.ClientError as err:
                _LOGGER.warning(
                    "Attempt %d/%d failed to fetch AMB data: %s",
                    attempt, RETRY_ATTEMPTS, err
                )

                if attempt == RETRY_ATTEMPTS:
                    # Start extended retry cycle
                    return await self._extended_retry()

                await asyncio.sleep(RETRY_INTERVAL.total_seconds())

        raise UpdateFailed("Failed to fetch data after all retry attempts")

    async def _extended_retry(self) -> dict[str, Any]:
        """Extended retry with longer intervals."""
        _LOGGER.info("Starting extended retry cycle")

        for attempt in range(1, EXTENDED_RETRY_ATTEMPTS + 1):
            try:
                data = await self._fetch_data()
                self._extended_retry_count = 0
                return self._process_data(data)

            except aiohttp.ClientError as err:
                _LOGGER.warning(
                    "Extended attempt %d/%d failed: %s",
                    attempt, EXTENDED_RETRY_ATTEMPTS, err
                )

                if attempt == EXTENDED_RETRY_ATTEMPTS:
                    break

                await asyncio.sleep(EXTENDED_RETRY_INTERVAL.total_seconds())

        # If we have cached data, return it with warning
        if self.data:
            _LOGGER.warning("Using cached data due to API unavailability")
            return self.data

        raise UpdateFailed("API unavailable and no cached data available")

    async def _fetch_data(self) -> dict[str, Any]:
        """Fetch data from API."""
        timeout = aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(self.api_url) as response:
                response.raise_for_status()
                return await response.json()

    def _process_data(self, raw_data: dict[str, Any]) -> dict[str, Any]:
        """Process raw API data into structured format."""
        current_price = raw_data.get("current_price", "unknown")
        forecasts = raw_data.get("forecasts", [])

        now = dt_util.now()
        processed_data = {
            "current_price": current_price,
            "forecasts": forecasts,
            "last_updated": now.isoformat(),
        }

        # Find current and next price periods
        current_period = self._find_current_period(forecasts, now)
        if current_period:
            processed_data["current_period"] = current_period
            processed_data["next_change"] = self._find_next_change(forecasts, now)

        # Separate today and tomorrow forecasts
        today_str = now.strftime("%Y-%m-%d")
        tomorrow_str = (now + timedelta(days=1)).strftime("%Y-%m-%d")

        processed_data["today_schedule"] = self._get_day_schedule(forecasts, today_str)
        processed_data["tomorrow_schedule"] = self._get_day_schedule(forecasts, tomorrow_str)

        return processed_data

    def _find_current_period(self, forecasts: list, now: datetime) -> dict[str, Any] | None:
        """Find current price period."""
        today_str = now.strftime("%Y-%m-%d")
        current_minutes = now.hour * 60 + now.minute

        for day in forecasts:
            if day.get("date") == today_str:
                for period in day.get("forecast", []):
                    hour_range = period.get("hour_range", "")
                    if " - " in hour_range:
                        start_str, end_str = hour_range.split(" - ")
                        start_minutes = self._time_to_minutes(start_str)
                        end_minutes = self._time_to_minutes(end_str)

                        # Handle end of day case
                        if end_str == "23:59":
                            end_minutes = 24 * 60

                        if start_minutes <= current_minutes < end_minutes:
                            return {
                                "price": period.get("price"),
                                "start": start_str,
                                "end": end_str,
                                # Rimuovi remaining_minutes da qui - calcolato nel sensore
                            }
        return None


    def _find_next_change(self, forecasts: list, now: datetime) -> dict[str, Any] | None:
        """Find next price change."""
        today_str = now.strftime("%Y-%m-%d")
        tomorrow_str = (now + timedelta(days=1)).strftime("%Y-%m-%d")
        current_minutes = now.hour * 60 + now.minute

        # Check remaining periods today
        for day in forecasts:
            if day.get("date") == today_str:
                for period in day.get("forecast", []):
                    hour_range = period.get("hour_range", "")
                    if " - " in hour_range:
                        start_str, _ = hour_range.split(" - ")
                        start_minutes = self._time_to_minutes(start_str)

                        if start_minutes > current_minutes:
                            return {
                                "time": start_str,
                                "price": period.get("price"),
                                "date": today_str,
                            }

        # Check tomorrow's first period
        for day in forecasts:
            if day.get("date") == tomorrow_str:
                forecast = day.get("forecast", [])
                if forecast:
                    first_period = forecast[0]
                    hour_range = first_period.get("hour_range", "")
                    if " - " in hour_range:
                        start_str, _ = hour_range.split(" - ")
                        return {
                            "time": start_str,
                            "price": first_period.get("price"),
                            "date": tomorrow_str,
                        }

        return None

    def _get_day_schedule(self, forecasts: list, date_str: str) -> list[dict[str, Any]]:
        """Get schedule for specific day."""
        for day in forecasts:
            if day.get("date") == date_str:
                return day.get("forecast", [])
        return []

    @staticmethod
    def _time_to_minutes(time_str: str) -> int:
        """Convert HH:MM to minutes since midnight."""
        try:
            hours, minutes = map(int, time_str.split(":"))
            return hours * 60 + minutes
        except (ValueError, AttributeError):
            return 0
