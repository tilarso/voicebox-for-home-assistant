# Handoff: Home Assistant Voicebox Integration

This handoff reflects the current implementation in `custom_components/voicebox`.

## Current integration behavior

- Config flow validates host safety, normalizes user input (`host`, `port`, optional `api_key`, `use_ssl`), probes `GET /api/status`, and creates one config entry per Voicebox server.
- Base URL uses `http://` by default and switches to `https://` when `use_ssl: true`.
- Per config entry, integration exposes:
  - status sensor (`/api/status` driven)
  - enabled switch (`/api/enable` and `/api/disable`)
- Service `voicebox.synthesize` supports:
  - required `text`
  - optional `voice`
  - optional `output_path` restricted to `/config/media/voicebox`
  - optional `entry_id` (required when multiple Voicebox entries are configured)

## Resolved in this round (R4)

- Removed unreachable `::` prefix blocklist branch in `config_flow._validate_host` (IPv6 literals are already rejected by the existing colon/bracket checks).
- Removed redundant re-normalization/type coercion inside `_async_validate_input`; it now consumes already-normalized values from `async_step_user`.
- Simplified `api_client._extract_response_body` non-JSON path to return response text directly (no secondary JSON parse attempt for non-JSON content-type responses).
- Added/updated tests for non-JSON response handling and for config-flow behavior alignment.

## Validation

Run from repository root:

`PYTHONPATH=. /opt/hermes/.venv/bin/python -m pytest -q`

Expected result after R4 changes: pass (all tests green).
