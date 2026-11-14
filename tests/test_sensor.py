"""Tests for the AMB Bellinzona sensors."""

from datetime import timedelta
from unittest.mock import MagicMock

from amb_bellinzona import TariffSchedule
from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from custom_components.amb_bellinzona.const import DOMAIN

from .conftest import NOW, make_schedule, setup_integration


async def test_sensors_and_quarter_hour_tick(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    schedule: TariffSchedule,
) -> None:
    """Verified against the AMB app on 2026-11-14: high 07:00-16:30, low 16:30-20:00."""
    # Cover tomorrow too, so the 12:30 refresh timer (jumped over below) has nothing to fetch.
    mock_client.async_get_schedule.return_value = TariffSchedule(
        schedule.slots + make_schedule(schedule.end, schedule.end + timedelta(days=1)).slots
    )
    freezer.move_to(NOW)  # 10:00 local
    await setup_integration(hass, mock_config_entry)

    tariff = hass.states.get("sensor.amb_bellinzona_tariff")
    assert tariff.state == "high"
    assert tariff.attributes["options"] == ["high", "low"]
    assert hass.states.get("sensor.amb_bellinzona_next_tariff_change").state == "2026-11-14T15:30:00+00:00"

    freezer.move_to("2026-11-14T15:30:00+00:00")  # 16:30 local
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.amb_bellinzona_tariff").state == "low"
    assert hass.states.get("sensor.amb_bellinzona_next_tariff_change").state == "2026-11-14T19:00:00+00:00"
    mock_client.async_get_schedule.assert_awaited_once()  # the tick never hits the network


async def test_device(hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry, freezer: FrozenDateTimeFactory) -> None:
    freezer.move_to(NOW)
    await setup_integration(hass, mock_config_entry)
    device = dr.async_get(hass).async_get_device_by_identifier((DOMAIN, mock_config_entry.entry_id), mock_config_entry.entry_id)
    assert device.manufacturer == "AMB"
    assert device.name == "AMB Bellinzona"
    assert device.entry_type is dr.DeviceEntryType.SERVICE
