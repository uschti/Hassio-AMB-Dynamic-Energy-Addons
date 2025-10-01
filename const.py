"""Constants for the AMB Dynamic Energy integration."""
from datetime import timedelta
from typing import Final

DOMAIN: Final = "amb_dynamic_energy"

# API Configuration
DEFAULT_API_URL: Final = "https://amb-dynamic-current-api.uschti.ch/amb-data"
DEFAULT_TIMEOUT: Final = 15
DEFAULT_UPDATE_INTERVAL: Final = timedelta(hours=2)

# Retry Configuration
RETRY_ATTEMPTS: Final = 5
RETRY_INTERVAL: Final = timedelta(minutes=1)
EXTENDED_RETRY_ATTEMPTS: Final = 20
EXTENDED_RETRY_INTERVAL: Final = timedelta(minutes=10)

# Sensor Configuration
SENSOR_CURRENT_PRICE: Final = "current_price"
SENSOR_CURRENT_DURATION: Final = "current_duration"
SENSOR_PRICE_SCHEDULE: Final = "price_schedule"

# Device Information
MANUFACTURER: Final = "Andrea Pellegrini @uschti (https://github.com/uschti)"
MODEL: Final = "Dynamic Energy Pricing"

# Configuration Keys
CONF_API_URL: Final = "api_url"
CONF_UPDATE_INTERVAL: Final = "update_interval"

# Attributes
ATTR_CURRENT_PRICE: Final = "current_price"
ATTR_FORECASTS: Final = "forecasts"
ATTR_NEXT_CHANGE: Final = "next_change"
ATTR_CURRENT_RANGE: Final = "current_range"
ATTR_TODAY_SCHEDULE: Final = "today_schedule"
ATTR_TOMORROW_SCHEDULE: Final = "tomorrow_schedule"
ATTR_LAST_UPDATED: Final = "last_updated"
