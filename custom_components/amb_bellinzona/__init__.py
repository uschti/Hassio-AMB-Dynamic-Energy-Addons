"""The AMB Bellinzona integration."""

from __future__ import annotations

from amb_bellinzona import AMBBellinzona

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.storage import Store

from .const import DOMAIN, STORAGE_VERSION
from .coordinator import AMBBellinzonaConfigEntry, AMBBellinzonaCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: AMBBellinzonaConfigEntry) -> bool:
    """Set up AMB Bellinzona from a config entry."""
    coordinator = AMBBellinzonaCoordinator(hass, entry, AMBBellinzona(async_get_clientsession(hass)))
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    entry.async_on_unload(
        async_track_time_change(hass, coordinator.async_quarter_hour, minute=(0, 15, 30, 45), second=0)
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AMBBellinzonaConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: AMBBellinzonaConfigEntry) -> None:
    """Delete the cached schedule when the integration is removed."""
    await Store(hass, STORAGE_VERSION, DOMAIN).async_remove()
