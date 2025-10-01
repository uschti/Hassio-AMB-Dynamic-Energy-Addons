"""Config flow for AMB Dynamic Energy integration."""
from __future__ import annotations

import logging
from typing import Any
import voluptuous as vol
import aiohttp

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    DEFAULT_API_URL,
    DEFAULT_UPDATE_INTERVAL,
    CONF_API_URL,
    CONF_UPDATE_INTERVAL,
    DEFAULT_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_API_URL, default=DEFAULT_API_URL): cv.string,
        vol.Optional(
            CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL.total_seconds() / 3600
        ): vol.All(vol.Coerce(float), vol.Range(min=0.5, max=24)),
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    api_url = data[CONF_API_URL]

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT)) as session:
            async with session.get(api_url) as response:
                if response.status != 200:
                    raise CannotConnect(f"API returned status {response.status}")

                json_data = await response.json()

                # Validate expected structure
                if "current_price" not in json_data or "forecasts" not in json_data:
                    raise InvalidData("API response missing required fields")

                if json_data["current_price"] not in ["low", "high"]:
                    raise InvalidData("Invalid current_price value")

    except aiohttp.ClientError as err:
        _LOGGER.error("Error connecting to AMB API: %s", err)
        raise CannotConnect from err
    except Exception as err:
        _LOGGER.error("Unexpected error validating AMB API: %s", err)
        raise InvalidData from err

    return {"title": "AMB Dynamic Energy"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for AMB Dynamic Energy."""

    VERSION = 1

    async def async_step_user(
            self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)

                # Convert hours back to timedelta for storage
                user_input[CONF_UPDATE_INTERVAL] = int(user_input[CONF_UPDATE_INTERVAL] * 3600)

                return self.async_create_entry(title=info["title"], data=user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidData:
                errors["base"] = "invalid_data"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidData(HomeAssistantError):
    """Error to indicate there is invalid data."""
