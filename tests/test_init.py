"""Tests for AMB Bellinzona setup, caching and refresh scheduling."""

from datetime import timedelta
import logging
from unittest.mock import MagicMock, patch

from amb_bellinzona import AMBBellinzonaConnectionError, TariffSchedule
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.amb_bellinzona.const import DOMAIN, RETRY_INTERVAL
from .conftest import NOW, make_schedule, setup_integration, stored_slots


def _store(hass_storage: dict, schedule: TariffSchedule) -> None:
    hass_storage[DOMAIN] = {"version": 1, "minor_version": 1, "key": DOMAIN, "data": stored_slots(schedule)}


@pytest.mark.freeze_time(NOW)
async def test_setup_fetches_and_stores(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry, hass_storage: dict
) -> None:
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_client.async_get_schedule.assert_awaited_once()
    assert len(hass_storage[DOMAIN]["data"]) > 0


@pytest.mark.freeze_time(NOW)
async def test_setup_uses_storage_without_fetching(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry, hass_storage: dict
) -> None:
    """Stored data covering today and tomorrow means no API call on restart."""
    today = dt_util.start_of_local_day()
    _store(hass_storage, make_schedule(today, today + timedelta(days=2)))
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_client.async_get_schedule.assert_not_awaited()


@pytest.mark.freeze_time("2026-11-14T13:00:00+00:00")  # 14:00 local, after the window
async def test_setup_fetches_when_stored_lacks_tomorrow_after_window(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry, hass_storage: dict, schedule: TariffSchedule
) -> None:
    _store(hass_storage, schedule)  # ends at local midnight: no tomorrow
    await setup_integration(hass, mock_config_entry)
    mock_client.async_get_schedule.assert_awaited_once()


@pytest.mark.freeze_time(NOW)
async def test_corrupt_storage_is_ignored(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry, hass_storage: dict
) -> None:
    hass_storage[DOMAIN] = {"version": 1, "minor_version": 1, "key": DOMAIN, "data": [{"bogus": 1}]}
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_client.async_get_schedule.assert_awaited_once()


@pytest.mark.freeze_time(NOW)
async def test_setup_retry_without_data(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    mock_client.async_get_schedule.side_effect = AMBBellinzonaConnectionError("down")
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_fetch_failure_uses_cache(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    hass_storage: dict,
    schedule: TariffSchedule,
    caplog: pytest.LogCaptureFixture,
    freezer: FrozenDateTimeFactory,
) -> None:
    """API down but the cache covers now: loaded, valid state, and only one warning across retries."""
    freezer.move_to("2026-11-14T13:00:00+00:00")  # 14:00 local
    _store(hass_storage, schedule)
    mock_client.async_get_schedule.side_effect = AMBBellinzonaConnectionError("down")
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get("sensor.amb_bellinzona_tariff").state == "high"
    calls = mock_client.async_get_schedule.await_count

    freezer.tick(RETRY_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_client.async_get_schedule.await_count > calls  # the retry really ran
    assert caplog.text.count("using the cached one") == 1
    assert hass.states.get("sensor.amb_bellinzona_tariff").state == "high"  # 14:30 local


async def test_retry_backoff(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    hass_storage: dict,
    schedule: TariffSchedule,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Failed requests retry after 1, 5 and 15 minutes, then every 30 minutes."""
    freezer.move_to("2026-11-14T13:00:00+00:00")  # 14:00 local, tomorrow missing
    _store(hass_storage, schedule)
    mock_client.async_get_schedule.side_effect = AMBBellinzonaConnectionError("down")
    await setup_integration(hass, mock_config_entry)
    for minutes in (1, 5, 15, 30, 30):
        freezer.tick(timedelta(minutes=minutes) - timedelta(seconds=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        calls = mock_client.async_get_schedule.await_count
        freezer.tick(timedelta(seconds=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert mock_client.async_get_schedule.await_count == calls + 1, minutes


async def test_scheduled_refresh_in_window(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """Set up at 10:00 local; the next fetch fires at 12:30 local (jitter patched to 0)."""
    freezer.move_to(NOW)
    with patch("custom_components.amb_bellinzona.coordinator.random.uniform", return_value=0):
        await setup_integration(hass, mock_config_entry)
        freezer.tick(timedelta(hours=2, minutes=30))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
    assert mock_client.async_get_schedule.await_count == 2


@pytest.mark.freeze_time(NOW)
async def test_unload_and_remove(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry, hass_storage: dict
) -> None:
    await setup_integration(hass, mock_config_entry)
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert DOMAIN not in hass_storage


async def test_unavailable_when_cache_gap_and_api_down(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    hass_storage: dict,
    schedule: TariffSchedule,
    caplog: pytest.LogCaptureFixture,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Warn once while the cache covers now, log recovery once, go unavailable on a real gap."""
    caplog.set_level(logging.INFO)
    freezer.move_to("2026-11-14T11:35:00+00:00")  # 12:35 local: window open, tomorrow missing
    _store(hass_storage, schedule)
    mock_client.async_get_schedule.side_effect = AMBBellinzonaConnectionError("down")
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get("sensor.amb_bellinzona_tariff").state == "high"
    assert caplog.text.count("using the cached one") == 1

    mock_client.async_get_schedule.side_effect = None  # API recovers on the next retry
    freezer.tick(RETRY_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert caplog.text.count("Fetching the tariff schedule works again") == 1

    mock_client.async_get_schedule.side_effect = AMBBellinzonaConnectionError("down")
    freezer.move_to("2026-11-14T23:30:00+00:00")  # 00:30 local the next day: past the schedule end
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.amb_bellinzona_tariff").state == "unavailable"
