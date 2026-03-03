# Contributing to Wallbox Abrechnung

Thank you for your interest in contributing! This is a personal Home Assistant integration for wallbox billing, but contributions are welcome.

## Reporting Bugs

Please use the [Bug Report template](.github/ISSUE_TEMPLATE/bug_report.md) when opening an issue. Include:

- Home Assistant version
- Integration version (visible in HACS or `manifest.json`)
- ESPHome/hardware setup (if relevant)
- Steps to reproduce the issue
- Relevant log output (`Settings → System → Logs`, filter by `wallbox_billing`)

## Suggesting Features

Use the [Feature Request template](.github/ISSUE_TEMPLATE/feature_request.md). Please describe the use case clearly.

## Pull Requests

1. Fork the repository
2. Create a branch: `git checkout -b feature/my-feature` or `fix/my-bugfix`
3. Make your changes and test them in a real Home Assistant instance
4. Ensure Python syntax is valid: `python3 -m py_compile custom_components/wallbox_billing/*.py`
5. Open a Pull Request with a clear description of what was changed and why

### Code Style

- Follow existing code patterns
- Keep changes focused – one feature or fix per PR
- No unnecessary dependencies

## Development Setup

1. Clone the repo into your HA `custom_components` directory:
   ```
   custom_components/wallbox_billing/
   ```
2. Restart Home Assistant
3. Check logs for any errors

## Questions

Open a [GitHub Discussion](https://github.com/Feberdin/ha-wallbox-billing/issues) or issue for questions.
