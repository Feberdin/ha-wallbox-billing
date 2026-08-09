# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.1.x   | ✅ current |
| < 1.1.0 | ❌ no longer maintained |

## Reporting a Vulnerability

**Please do not report security vulnerabilities via public GitHub issues.**

If you discover a security issue (e.g. sensitive data exposure, injection vulnerability), please report it privately:

1. Go to the [GitHub Security Advisories](https://github.com/Feberdin/ha-wallbox-billing/security/advisories/new) page
2. Click **"Report a vulnerability"**
3. Describe the issue, affected versions, and potential impact

You can expect an acknowledgement within 48 hours. We will work with you to understand and address the issue before any public disclosure.

## Security Notes

- SMTP credentials (password) are stored in Home Assistant's encrypted config entry storage
- ESPHome Wi-Fi, API encryption, OTA, and fallback access values belong in the ignored
  `esphome/secrets.yaml`; the repository contains only `!secret` references and a placeholder template
- Any ESPHome credentials previously committed to Git must be rotated on the device; rewriting Git
  history alone does not invalidate exposed credentials
- No data is sent to external services other than the configured SMTP server
- PDF invoices are generated locally and only sent to the configured email recipient
- No telemetry or analytics are collected
