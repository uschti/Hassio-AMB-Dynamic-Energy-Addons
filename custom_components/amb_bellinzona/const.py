"""Constants for the AMB Bellinzona integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "amb_bellinzona"

# AMB publishes the next day's tariff by 12:00 local; fetch at a random minute in this window.
FETCH_WINDOW_START: Final = timedelta(hours=12, minutes=30)
FETCH_WINDOW_LENGTH: Final = timedelta(hours=1)
RETRY_INTERVAL: Final = timedelta(minutes=30)

STORAGE_VERSION: Final = 1
