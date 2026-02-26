"""Wallbox Billing – Home Assistant custom integration."""
from __future__ import annotations

import datetime
import logging
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.storage import Store

from .const import (
    CONF_ENERGY_SENSOR,
    CONF_INITIAL_DATE,
    CONF_INITIAL_READING,
    CONF_METER_NUMBER,
    CONF_OWNER_NAME,
    CONF_PRICE_PER_KWH,
    CONF_RECIPIENT_EMAIL,
    CONF_SMTP_FROM_EMAIL,
    CONF_SMTP_HOST,
    CONF_SMTP_PASSWORD,
    CONF_SMTP_PORT,
    CONF_SMTP_USE_SSL,
    CONF_SMTP_USE_TLS,
    CONF_SMTP_USERNAME,
    DOMAIN,
    SERVICE_SEND_INVOICE,
    STORAGE_KEY,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "button"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Wallbox Billing from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}_{entry.entry_id}")
    stored = await store.async_load() or {}

    hass.data[DOMAIN][entry.entry_id] = {
        "config": {**entry.data, **entry.options},
        "store": store,
        "stored": stored,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    async def _handle_send_invoice(call: ServiceCall) -> None:
        await _async_send_invoice(hass, entry, call)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_INVOICE,
        _handle_send_invoice,
        schema=vol.Schema({}),
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    hass.data[DOMAIN][entry.entry_id]["config"] = {**entry.data, **entry.options}
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_send_invoice(
    hass: HomeAssistant, entry: ConfigEntry, call: ServiceCall
) -> None:
    """Generate PDF invoice and send via SMTP."""
    data = hass.data[DOMAIN][entry.entry_id]
    cfg = data["config"]
    stored = data["stored"]

    sensor_id = cfg[CONF_ENERGY_SENSOR]
    state = hass.states.get(sensor_id)
    if state is None or state.state in ("unknown", "unavailable"):
        _LOGGER.error("Sensor %s nicht verfügbar – Abrechnung abgebrochen", sensor_id)
        return

    try:
        current_reading = float(state.state)
    except ValueError:
        _LOGGER.error("Ungültiger Sensorwert: %s", state.state)
        return

    # Load last billing data from persistent storage
    last_reading = stored.get("last_reading")
    last_date_str = stored.get("last_date")

    today = datetime.date.today()

    if last_reading is None:
        # First invoice: use the initial values entered during setup
        last_reading = float(cfg.get(CONF_INITIAL_READING, 0.0))
        initial_date_str = cfg.get(CONF_INITIAL_DATE)
        last_date = (
            datetime.date.fromisoformat(initial_date_str)
            if initial_date_str
            else today.replace(day=1)
        )
        _LOGGER.info(
            "Erste Abrechnung – verwende Startwert aus Konfiguration: %.3f kWh ab %s",
            last_reading,
            last_date,
        )
    else:
        last_date = (
            datetime.date.fromisoformat(last_date_str)
            if last_date_str
            else today.replace(day=1)
        )

    owner_name = cfg[CONF_OWNER_NAME]
    meter_number = cfg[CONF_METER_NUMBER]
    recipient_email = cfg[CONF_RECIPIENT_EMAIL]
    price_per_kwh = float(cfg[CONF_PRICE_PER_KWH])

    # Lazy import so the package loads even if fpdf2 isn't installed yet
    from .pdf_generator import generate_invoice_pdf  # noqa: PLC0415

    # Generate PDF in executor (fpdf2 is sync)
    pdf_bytes = await hass.async_add_executor_job(
        generate_invoice_pdf,
        owner_name,
        meter_number,
        recipient_email,
        last_date,
        today,
        last_reading,
        current_reading,
        price_per_kwh,
    )

    period_label = f"{last_date.strftime('%Y-%m')}"
    filename = f"Wallbox_Abrechnung_{period_label}.pdf"

    # Send email in executor
    smtp_cfg = {
        "host": cfg[CONF_SMTP_HOST],
        "port": int(cfg[CONF_SMTP_PORT]),
        "username": cfg.get(CONF_SMTP_USERNAME, ""),
        "password": cfg.get(CONF_SMTP_PASSWORD, ""),
        "from_email": cfg[CONF_SMTP_FROM_EMAIL],
        "use_tls": cfg.get(CONF_SMTP_USE_TLS, True),
        "use_ssl": cfg.get(CONF_SMTP_USE_SSL, False),
    }

    consumption = current_reading - last_reading
    total_cost = consumption * price_per_kwh
    subject = (
        f"Wallbox Ladekosten {last_date.strftime('%B %Y')} – "
        f"{total_cost:.2f} €"
    )
    body = (
        f"<p>Guten Tag,</p>"
        f"<p>anbei finden Sie die Erstattungsanforderung für die Ladekosten "
        f"des Dienstfahrzeuges an der privaten Wallbox.</p>"
        f"<table style='border-collapse:collapse;font-family:sans-serif'>"
        f"<tr><td style='padding:4px 12px'>Zeitraum:</td>"
        f"<td style='padding:4px 12px'>{last_date.strftime('%d.%m.%Y')} – "
        f"{today.strftime('%d.%m.%Y')}</td></tr>"
        f"<tr><td style='padding:4px 12px'>Verbrauch:</td>"
        f"<td style='padding:4px 12px'>{consumption:.3f} kWh</td></tr>"
        f"<tr><td style='padding:4px 12px'>Preis/kWh:</td>"
        f"<td style='padding:4px 12px'>{price_per_kwh:.4f} €</td></tr>"
        f"<tr><td style='padding:4px 12px'><strong>Gesamtbetrag:</strong></td>"
        f"<td style='padding:4px 12px'><strong>{total_cost:.2f} €</strong></td></tr>"
        f"</table>"
        f"<p>Die Abrechnung ist als PDF-Anhang beigefügt.</p>"
        f"<p>Mit freundlichen Grüßen,<br/>{owner_name}</p>"
    )

    try:
        await hass.async_add_executor_job(
            _send_email_sync, smtp_cfg, recipient_email, subject, body, pdf_bytes, filename
        )
    except Exception as exc:  # noqa: BLE001
        _LOGGER.error("E-Mail-Versand fehlgeschlagen: %s", exc)
        return

    # Persist new billing state
    stored["last_reading"] = current_reading
    stored["last_date"] = today.isoformat()
    data["stored"] = stored
    await data["store"].async_save(stored)

    # Signal sensors to update
    hass.bus.async_fire(f"{DOMAIN}_invoice_sent", {"entry_id": entry.entry_id})
    _LOGGER.info(
        "Wallbox-Abrechnung erfolgreich gesendet: %.3f kWh, %.2f €",
        consumption,
        total_cost,
    )


def _send_email_sync(
    smtp_cfg: dict,
    to_email: str,
    subject: str,
    body_html: str,
    pdf_bytes: bytes,
    filename: str,
) -> None:
    """Blocking SMTP send – runs in executor."""
    msg = MIMEMultipart("mixed")
    msg["From"] = smtp_cfg["from_email"]
    msg["To"] = to_email
    msg["Subject"] = subject

    msg.attach(MIMEText(body_html, "html", "utf-8"))

    attachment = MIMEApplication(pdf_bytes, _subtype="pdf")
    attachment.add_header("Content-Disposition", "attachment", filename=filename)
    msg.attach(attachment)

    if smtp_cfg["use_ssl"]:
        server = smtplib.SMTP_SSL(smtp_cfg["host"], smtp_cfg["port"], timeout=30)
    else:
        server = smtplib.SMTP(smtp_cfg["host"], smtp_cfg["port"], timeout=30)
        if smtp_cfg["use_tls"]:
            server.starttls()

    if smtp_cfg["username"]:
        server.login(smtp_cfg["username"], smtp_cfg["password"])

    server.send_message(msg)
    server.quit()
