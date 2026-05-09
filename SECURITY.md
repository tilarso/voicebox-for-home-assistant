# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| latest  | :white_check_mark: |

Only the latest release on the `main` branch receives security updates. If you are running an older version, please upgrade before reporting.

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

To report a vulnerability privately, use one of the following channels:

1. **GitHub Security Advisories (preferred):** Navigate to [Security → Advisories](../../security/advisories) on this repository and click **"Report a vulnerability"**. This creates a private thread visible only to maintainers.
2. **Email:** Send details to the repository owner via the email address listed on their GitHub profile.

### What to include

- A clear description of the vulnerability and its potential impact.
- Steps to reproduce, including configuration details and versions.
- Any proof-of-concept code or logs (sanitize credentials before sharing).

### What to expect

- **Acknowledgement** within **72 hours** of your report.
- **Initial assessment** (confirmed / needs-more-info / not-applicable) within **7 days**.
- **Fix or mitigation** for confirmed vulnerabilities within **30 days**, depending on severity and complexity.
- A coordinated disclosure timeline agreed upon with the reporter before any public announcement.

If you do not receive an acknowledgement within 72 hours, please follow up — the report may not have been received.

## Scope

The following are **in scope** for this security policy:

- The Home Assistant custom integration code under `custom_components/voicebox/`.
- Configuration flows, API client logic, and service handlers.
- Any credentials, tokens, or secrets handled by the integration.
- Dependencies declared in `manifest.json`.

The following are **out of scope**:

- The upstream Voicebox server software itself — report those issues to the [Voicebox project](https://github.com/jamiepine/voicebox).
- Home Assistant core vulnerabilities — report those to [Home Assistant Security](https://www.home-assistant.io/security/).
- Issues in third-party HACS infrastructure.
- Denial-of-service attacks against a user's local network.

## Coordinated Disclosure

We follow coordinated disclosure practices:

1. The reporter and maintainers agree on a disclosure timeline (typically 90 days from confirmed report).
2. A fix is developed and tested privately.
3. A new release is published with the fix, and a security advisory is created on GitHub.
4. The reporter is credited in the advisory (unless they prefer to remain anonymous).

We ask that reporters refrain from publicly disclosing vulnerability details until a fix is available and the agreed timeline has elapsed.

## Security Design Principles

This integration is designed with the following security considerations:

- **HTTPS by default.** All communication with the Voicebox API uses HTTPS. Plain HTTP is explicitly blocked to prevent API key exposure in transit.
- **No credential logging.** API keys and tokens are never written to logs or diagnostic output.
- **Input validation.** User-supplied paths and parameters are validated to prevent path traversal and injection attacks.
- **Least privilege.** The integration requests only the Home Assistant permissions it needs to function.

## Thank You

We appreciate the security research community's efforts in responsibly disclosing vulnerabilities. Your work helps keep this project and its users safe.
