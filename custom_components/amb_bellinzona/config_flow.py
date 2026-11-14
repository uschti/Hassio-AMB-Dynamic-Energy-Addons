"""Config flow for the AMB Bellinzona integration."""

from __future__ import annotations

import logging
from typing import Any

from amb_bellinzona import AMBBellinzona, AMBBellinzonaError

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class AMBBellinzonaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Single confirm step: the API is public, nothing to ask."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Confirm and test the connection."""
        errors: dict[str, str] = {}
        if user_input is not None:
            client = AMBBellinzona(async_get_clientsession(self.hass))
            try:
                await client.async_get_schedule()
            except AMBBellinzonaError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title="AMB Bellinzona", data={})
        return self.async_show_form(step_id="user", errors=errors)
