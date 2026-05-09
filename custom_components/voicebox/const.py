"""Constants for the Voicebox integration."""

from datetime import timedelta

DOMAIN = "voicebox"

CONF_HOST = "host"
CONF_PORT = "port"
CONF_API_KEY = "api_key"
CONF_USE_SSL = "use_ssl"
ATTR_ENTRY_ID = "entry_id"

DEFAULT_PORT = 8000
DEFAULT_TIMEOUT = 10
DEFAULT_STATUS = "unknown"
DEFAULT_USE_SSL = False
SAFE_OUTPUT_BASE_DIR = "/config/media/voicebox"

SERVICE_SYNTHESIZE = "synthesize"
ATTR_TEXT = "text"
ATTR_VOICE = "voice"
ATTR_OUTPUT_PATH = "output_path"

COORDINATOR_UPDATE_INTERVAL = timedelta(seconds=30)

PLATFORMS: list[str] = ["sensor", "switch", "tts"]
