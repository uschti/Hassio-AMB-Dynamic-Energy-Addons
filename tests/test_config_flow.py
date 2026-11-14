"""Tests for the AMB Bellinzona config flow."""

from unittest.mock import MagicMock

from amb_bellinzona import AMBBellinzonaConnectionError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.amb_bellinzona.const import DOMAIN


async def test_user_flow(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """The confirm step tests the API and creates the entry."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "AMB Bellinzona"
    assert result["data"] == {}
    await hass.async_block_till_done()
    assert mock_client.async_get_schedule.await_count == 2  # flow check + first setup (install day)


async def test_user_flow_cannot_connect_then_recovers(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """A library error shows cannot_connect; the user can retry."""
    mock_client.async_get_schedule.side_effect = AMBBellinzonaConnectionError("down")
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_client.async_get_schedule.side_effect = None
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_unknown_error(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """An unexpected exception shows unknown."""
    mock_client.async_get_schedule.side_effect = RuntimeError("boom")
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_single_instance(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """A second entry is refused (manifest single_config_entry)."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
