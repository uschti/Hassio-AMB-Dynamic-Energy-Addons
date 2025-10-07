"""Config flow without user input for AMB Dynamic Energy integration."""

from __future__ import annotations

from typing import Any

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import (
    DOMAIN,
    DEFAULT_API_URL,
    DEFAULT_UPDATE_INTERVAL,
    CONF_API_URL,
    CONF_UPDATE_INTERVAL,
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow that creates an entry with default fixed config, no UI."""

    VERSION = 1

    async def async_step_user(
            self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Create entry using default config without requesting data from user."""
        # Do not ask user for input, simply create configuration entry with defaults
        return self.async_create_entry(
            title="AMB Dynamic Energy",
            data={
                CONF_API_URL: DEFAULT_API_URL,
                CONF_UPDATE_INTERVAL: int(DEFAULT_UPDATE_INTERVAL.total_seconds()),
            },
        )

    async def async_step_import(
            self, import_data: dict[str, Any]
    ) -> FlowResult:
        """Support import from configuration.yaml or other import methods."""
        # Redirect import to user step, maintains compatibility
        return await self.async_step_user()

    @staticmethod
    def async_get_options_flow(config_entry):
        """Return the options flow handler to allow changing API URL and interval after setup."""
        from .config_flow import OptionsFlowHandler

        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Config flow options handler for AMB Dynamic Energy."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
            self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        default_api_url = self.config_entry.options.get(
            CONF_API_URL, self.config_entry.data.get(CONF_API_URL, DEFAULT_API_URL)
        )
        default_update_interval = self.config_entry.options.get(
            CONF_UPDATE_INTERVAL,
            self.config_entry.data.get(CONF_UPDATE_INTERVAL, int(DEFAULT_UPDATE_INTERVAL.total_seconds())),
        )
        schema = {
            vol.Optional(
                CONF_API_URL, default=default_api_url
            ): str,
            vol.Optional(
                CONF_UPDATE_INTERVAL, default=default_update_interval / 3600
            ): float,
        }

        import voluptuous as vol

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema),
        )
