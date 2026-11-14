"""Constants for the AMB Bellinzona integration."""

from datetime import timedelta
from typing import Final
from zoneinfo import ZoneInfo

DOMAIN: Final = "amb_bellinzona"

# AMB's days and publication times are Swiss, whatever time zone Home Assistant uses.
AMB_TIME_ZONE: Final = ZoneInfo("Europe/Zurich")

# AMB publishes the next day's tariff by 12:00 Swiss time; fetch at a random minute in this window.
FETCH_WINDOW_START: Final = timedelta(hours=12, minutes=30)
FETCH_WINDOW_LENGTH: Final = timedelta(hours=1)
# Retry while AMB has not published the data we need yet.
RETRY_INTERVAL: Final = timedelta(minutes=30)
# Retry delays after failed requests; the last one repeats. Short first steps ride out local network blips.
RETRY_BACKOFF: Final = (timedelta(minutes=1), timedelta(minutes=5), timedelta(minutes=15), RETRY_INTERVAL)

STORAGE_VERSION: Final = 1
