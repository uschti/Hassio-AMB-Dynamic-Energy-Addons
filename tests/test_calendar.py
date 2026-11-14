"""Tests for the AMB Bellinzona calendar."""

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.calendar import DOMAIN as CALENDAR_DOMAIN, SERVICE_GET_EVENTS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.amb_bellinzona.const import DOMAIN

from .conftest import NOW, setup_integration

ENTITY_ID = "calendar.amb_bellinzona_high_tariff"


async def _move(hass: HomeAssistant, freezer: FrozenDateTimeFactory, when: str) -> None:
    freezer.move_to(when)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def _events(hass: HomeAssistant, start: str, end: str, entity_id: str = ENTITY_ID) -> list[tuple[str, str, str]]:
    response = await hass.services.async_call(
        CALENDAR_DOMAIN,
        SERVICE_GET_EVENTS,
        {"entity_id": entity_id, "start_date_time": start, "end_date_time": end},
        blocking=True,
        return_response=True,
    )
    return [(e["start"], e["end"], e["summary"]) for e in response[entity_id]["events"]]


async def test_events_match_the_amb_app(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """Verified against the AMB app on 2026-11-14: high 07:00-16:30 and 20:00-23:00, low otherwise."""
    freezer.move_to(NOW)
    await setup_integration(hass, mock_config_entry)
    assert await _events(hass, "2026-11-14T00:00:00+01:00", "2026-11-15T00:00:00+01:00") == [
        ("2026-11-14T07:00:00+01:00", "2026-11-14T16:30:00+01:00", "High tariff"),
        ("2026-11-14T20:00:00+01:00", "2026-11-14T23:00:00+01:00", "High tariff"),
    ]
    assert await _events(
        hass, "2026-11-14T00:00:00+01:00", "2026-11-15T00:00:00+01:00", "calendar.amb_bellinzona_low_tariff"
    ) == [
        ("2026-11-13T23:00:00+01:00", "2026-11-14T07:00:00+01:00", "Low tariff"),
        ("2026-11-14T16:30:00+01:00", "2026-11-14T20:00:00+01:00", "Low tariff"),
        ("2026-11-14T23:00:00+01:00", "2026-11-15T00:00:00+01:00", "Low tariff"),  # the schedule ends at midnight
    ]
    # Ranges are half-open: touching a period at its edge does not include it.
    assert await _events(hass, "2026-11-14T00:00:00+01:00", "2026-11-14T07:00:00+01:00") == []
    assert await _events(hass, "2026-11-14T16:30:00+01:00", "2026-11-14T20:00:00+01:00") == []


async def test_state_follows_the_periods(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(NOW)  # 10:00 Swiss: inside 07:00-16:30
    await setup_integration(hass, mock_config_entry)
    state = hass.states.get(ENTITY_ID)
    assert state.state == "on"
    assert state.attributes["message"] == "High tariff"
    assert state.attributes["end_time"] == "2026-11-14 16:30:00"

    await _move(hass, freezer, "2026-11-14T15:30:00+00:00")  # 16:30 Swiss, the exact end: already the next period
    state = hass.states.get(ENTITY_ID)
    assert state.state == "off"
    assert state.attributes["start_time"] == "2026-11-14 20:00:00"

    await _move(hass, freezer, "2026-11-14T16:00:00+00:00")  # 17:00 Swiss: low, next period at 20:00
    state = hass.states.get(ENTITY_ID)
    assert state.state == "off"
    assert state.attributes["start_time"] == "2026-11-14 20:00:00"

    await _move(hass, freezer, "2026-11-14T22:30:00+00:00")  # 23:30 Swiss: nothing left in the cached schedule
    state = hass.states.get(ENTITY_ID)
    assert state.state == "off"
    assert "start_time" not in state.attributes


async def test_event_title_is_translated(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    await hass.config.async_update(language="it")
    freezer.move_to(NOW)
    await setup_integration(hass, mock_config_entry)
    entity_id = er.async_get(hass).async_get_entity_id("calendar", DOMAIN, f"{mock_config_entry.entry_id}_high_tariff")
    assert entity_id == "calendar.amb_bellinzona_tariffa_alta"  # HA names new entities in the system language
    assert hass.states.get(entity_id).attributes["message"] == "Tariffa alta"
