# Architecture: HA Voicebox Integration Contract

## Domain Model

### Core Concepts

- **Voicebox Instance** — A running Voicebox Docker container exposing a TTS HTTP API. One instance = one HA config entry = one HA device.
- **TTS Request** — Text + optional voice/speaker/style parameters → audio bytes.
- **Voice** — A named TTS voice model available on the Voicebox instance.

### Domain Objects

```
VoiceboxInstance
  ├── base_url: str          # e.g. "http://192.168.1.50:5000"
  ├── api_key: str | None    # Bearer token (optional, depends on instance config)
  ├── default_voice: str     # default voice ID for TTS calls
  ├── default_speaker_id: str | None
  ├── default_style: str | None
  └── timeout: int           # request timeout in seconds (default: 10)

TTSRequest
  ├── text: str              # non-empty, max ~10000 chars (enforced client-side)
  ├── voice: str             # voice identifier
  ├── speaker_id: str | None
  ├── style: str | None
  └── output_format: str     # "wav" (default) or "mp3"

TTSResponse
  ├── audio_data: bytes      # raw audio payload
  ├── content_type: str      # "audio/wav" or "audio/mpeg"
  └── duration_ms: int | None
```

---

## Config Entries and Options

### Config Flow (initial setup)

| Step | Field | Type | Required | Validation |
|------|-------|------|----------|------------|
| user | `base_url` | str | yes | URL format, must include scheme + host |
| user | `api_key` | str | no | If provided, tested via probe call |

**Probe:** `GET {base_url}/api/status` (or equivalent health endpoint). Must return 2xx.

**Unique key:** `base_url` — prevents duplicate entries for same instance.

### Options Flow (post-setup)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `default_voice` | str | `"default"` | Voice ID for TTS when not specified per-call |
| `default_speaker_id` | str | `""` | Speaker ID (empty = not sent) |
| `default_style` | str | `""` | Style modifier (empty = not sent) |
| `output_format` | str | `"wav"` | `"wav"` or `"mp3"` |
| `timeout` | int | `10` | HTTP timeout in seconds |

Options changes trigger coordinator reload (no restart required).

---

## API Client Boundaries

### `VoiceboxApiClient`

Single class owning all HTTP communication. Injected with `aiohttp.ClientSession` (HA-managed session preferred).

**Public interface:**

```python
class VoiceboxApiClient:
    def __init__(self, base_url: str, api_key: str | None, session: aiohttp.ClientSession, timeout: int = 10): ...

    async def async_get_status(self) -> dict:
        """GET /api/status → {"status": "running", ...}. Used by config flow probe and coordinator polling."""

    async def async_synthesize(self, text: str, voice: str, speaker_id: str | None = None, style: str | None = None, output_format: str = "wav") -> tuple[bytes, str]:
        """POST /api/tts → (audio_bytes, content_type). Raises on any non-2xx."""

    async def async_list_voices(self) -> list[dict]:
        """GET /api/voices → [{id, name, ...}, ...]. Optional; graceful fallback if endpoint missing."""
```

**Request contract (synthesize):**

```
POST {base_url}/api/tts
Content-Type: application/json
Authorization: Bearer {api_key}  (header omitted if api_key is None)

{
  "text": "Hello world",
  "voice": "en-default",
  "speaker_id": "spk_01",     // omitted if null
  "style": "cheerful",         // omitted if null
  "output_format": "wav"       // "wav" or "mp3"
}

→ 200 OK
Content-Type: audio/wav (or audio/mpeg)
Body: <raw audio bytes>
```

**Error mapping:**

| HTTP Status | Exception Class | Retryable |
|-------------|----------------|-----------|
| 401/403 | `VoiceboxAuthError` | No |
| 400/422 | `VoiceboxValidationError` | No |
| 429 | `VoiceboxRateLimitError` | Yes (backoff) |
| 500-599 | `VoiceboxServerError` | Yes (1 retry) |
| Timeout | `VoiceboxConnectionError` | Yes (1 retry) |
| Connection refused/reset | `VoiceboxConnectionError` | Yes (1 retry) |

All exceptions inherit from `VoiceboxError(HomeAssistantError)`.

**Retry policy:** Max 1 retry for transient errors only. Exponential backoff (1s base). Auth/validation errors never retry.

---

## Coordinator Pattern

### `VoiceboxCoordinator(DataUpdateCoordinator)`

Standard HA `DataUpdateCoordinator` pattern.

```python
class VoiceboxCoordinator(DataUpdateCoordinator[VoiceboxStatus]):
    update_interval = timedelta(seconds=30)

    async def _async_update_data(self) -> VoiceboxStatus:
        """Poll /api/status. On failure, raise UpdateFailed (entities go unavailable)."""
```

**Data shape:**

```python
@dataclass
class VoiceboxStatus:
    status: str          # "running", "stopped", "error"
    version: str | None  # Voicebox version if reported
    voices: list[str]    # available voice IDs (cached, refreshed on reload)
```

**Lifecycle:**
- Created in `async_setup_entry` → stored in `entry.runtime_data`
- First refresh awaited before entity platform setup
- Torn down in `async_unload_entry`

---

## Module Map

```
custom_components/voicebox/
├── __init__.py          # async_setup_entry, async_unload_entry, PLATFORMS
├── const.py             # DOMAIN, CONF_*, DEFAULT_*, PLATFORMS list
├── config_flow.py       # ConfigFlow + OptionsFlow
├── client.py            # VoiceboxApiClient
├── coordinator.py       # VoiceboxCoordinator
├── tts.py               # VoiceboxTTSEntity (TTS platform)
├── exceptions.py        # VoiceboxError hierarchy
├── diagnostics.py       # async_get_config_entry_diagnostics (redacted)
├── manifest.json        # integration metadata
├── strings.json         # UI strings (config/options flow)
└── translations/
    └── en.json          # English translations
```

---

## Compatibility Constraints

| Constraint | Value |
|------------|-------|
| HA minimum version | 2024.1.0 (TTS entity platform API stable) |
| Python | ≥ 3.12 |
| HACS compatible | Yes (standard custom_components layout) |
| IoT class | `local_polling` |
| Dependencies | None beyond HA core (aiohttp provided by HA) |
| Config entry version | 1 |
| Single config entry | No — multiple instances supported (keyed on base_url) |

---

## Acceptance Criteria

### Architecture

- [ ] Single `VoiceboxApiClient` class owns all HTTP; no raw aiohttp calls elsewhere
- [ ] All API exceptions are typed and inherit `VoiceboxError`
- [ ] Coordinator polls status at 30s interval; entities go unavailable on failure
- [ ] Config flow validates connectivity before creating entry
- [ ] Options flow allows changing defaults without re-adding integration
- [ ] No secrets (api_key, auth headers) appear in logs or diagnostics

### Implementation Quality

- [ ] manifest.json passes hassfest validation
- [ ] All modules type-annotated (mypy clean)
- [ ] Ruff lint clean
- [ ] Test coverage ≥ 80% overall, ≥ 90% on client/config_flow/tts/diagnostics
- [ ] Contract tests verify request/response schema against this document

### Functional

- [ ] Config flow: add → probe → success/error with clear messages
- [ ] TTS service call returns playable audio bytes
- [ ] Options changes take effect without restart
- [ ] Duplicate base_url entry rejected
- [ ] Diagnostics endpoint returns redacted debug info
