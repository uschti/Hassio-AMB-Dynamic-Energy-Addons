"""Fixtures for AMB Bellinzona tests."""

from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timedelta
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from amb_bellinzona import Tariff, TariffSchedule, TariffSlot
from amb_bellinzona.models import parse_schedule
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant

from custom_components.amb_bellinzona.const import DOMAIN

FIXTURE = Path(__file__).parent / "fixtures" / "tariff_schedule_2026-11-14.json"
# Covers 2026-11-12 00:15 UTC .. 2026-11-15 00:00 Swiss; 10:00 Swiss on the 14th is HIGH (07:00-16:30).
NOW = "2026-11-14T09:00:00+00:00"


async def setup_integration(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Add the entry, set it up and wait until everything settled."""
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


def stored_slots(schedule: TariffSchedule) -> list[dict[str, str]]:
    """Return the schedule in the on-disk storage format (pinned here on purpose)."""
    return [
        {"start": s.start.isoformat(), "end": s.end.isoformat(), "tariff": s.tariff.value}
        for s in schedule.slots
    ]


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable loading custom_components in every test."""


@pytest.fixture(autouse=True)
async def zurich_time_zone(hass: HomeAssistant) -> None:
    """Run every test in AMB's time zone."""
    await hass.config.async_set_time_zone("Europe/Zurich")


def make_schedule(start: datetime, end: datetime, tariff: Tariff = Tariff.LOW) -> TariffSchedule:
    """Build a contiguous schedule of 15-minute slots in [start, end)."""
    slots = []
    while start < end:
        slots.append(TariffSlot(start, start + timedelta(minutes=15), tariff))
        start += timedelta(minutes=15)
    return TariffSchedule(tuple(slots))


@pytest.fixture
def schedule() -> TariffSchedule:
    """Real API payload of 2026-11-14 (today present, tomorrow not yet)."""
    return parse_schedule(json.loads(FIXTURE.read_text()))


@pytest.fixture
def mock_client(schedule: TariffSchedule) -> Generator[MagicMock]:
    """Patch the library client everywhere the integration creates it."""
    client = MagicMock()
    client.async_get_schedule = AsyncMock(return_value=schedule)
    with (
        patch("custom_components.amb_bellinzona.AMBBellinzona", return_value=client),
        patch("custom_components.amb_bellinzona.config_flow.AMBBellinzona", return_value=client),
    ):
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Config entry as created by the config flow."""
    return MockConfigEntry(domain=DOMAIN, title="AMB Bellinzona", data={})
