"""Constants for the Voicebox integration."""

from datetime import timedelta

DOMAIN = "voicebox"

CONF_HOST = "host"
CONF_PORT = "port"
CONF_API_KEY = "api_key"

DEFAULT_PORT = 8000
DEFAULT_TIMEOUT = 10
DEFAULT_STATUS = "unknown"

COORDINATOR_UPDATE_INTERVAL = timedelta(seconds=30)

PLATFORMS: list[str] = ["sensor", "switch"]
