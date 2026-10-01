"""Wallbox Billing: validated invoices and auditable baseline corrections.

Inputs are HA sensor readings and explicit service fields. Corrections persist
before refreshing entities and never send mail. Debug via wallbox_billing logs;
do not log configuration dictionaries, which contain SMTP credentials.
"""

from __future__ import annotations

import asyncio
import datetime
import logging
import math
import random
import smtplib
import re
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    CONF_DAILY_STATS_HOUR,
    CONF_ENERGY_SENSOR,
    CONF_INCLUDE_DAILY_STATS,
    CONF_STATS_SENSOR,
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
    DEFAULT_DAILY_STATS_HOUR,
    DEFAULT_INCLUDE_DAILY_STATS,
    DOMAIN,
    SERVICE_SEND_INVOICE,
    SERVICE_SEND_SAMPLE_PDF,
    SERVICE_SEND_TEST_INVOICE,
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
        "lock": asyncio.Lock(),
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    async def _handle_send_invoice(call: ServiceCall) -> None:
        await _async_send_invoice(hass, entry, call)

    async def _handle_send_test_invoice(call: ServiceCall) -> None:
        await _async_send_invoice(hass, entry, call, test_mode=True)

    async def _handle_send_sample_pdf(call: ServiceCall) -> None:
        await _async_send_sample_pdf(hass, entry, call)

    async def _handle_correct_last_reading(call: ServiceCall) -> None:
        await _async_correct_last_reading(hass, call)

    async_register_admin_service(
        hass,
        DOMAIN,
        "correct_last_reading",
        _handle_correct_last_reading,
        schema=_CORRECTION_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN, SERVICE_SEND_INVOICE, _handle_send_invoice, schema=_SERVICE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_TEST_INVOICE,
        _handle_send_test_invoice,
        schema=_SERVICE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SEND_SAMPLE_PDF, _handle_send_sample_pdf, schema=vol.Schema({})
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


async def _async_fetch_daily_stats(
    hass: HomeAssistant,
    sensor_id: str,
    start_date: datetime.date,
    end_date: datetime.date,
    hour: int = 0,  # reserviert für Kompatibilität, wird bei period="day" nicht genutzt
) -> list[tuple[datetime.date, float | None]]:
    """Tagesverbrauch aus HA Recorder-Statistiken (Tagesauflösung).

    Nutzt period="day" für maximale Kompatibilität mit HA 2023+.
    In HA 2023.3+ gibt statistics_during_period 'start' als float (Unix-Timestamp)
    zurück – kein datetime-Objekt. Beide Formate werden korrekt behandelt.

    Gibt für jeden Kalendertag von start_date bis end_date ein (date, kwh)-Tupel zurück.
    Fehlende oder rückläufige Summen sind unbekannt (None), nicht Nullverbrauch.
    """
    try:
        from homeassistant.components.recorder import get_instance  # noqa: PLC0415
        from homeassistant.components.recorder.statistics import (  # noqa: PLC0415
            statistics_during_period,
        )
    except ImportError:
        _LOGGER.warning("Recorder nicht verfügbar – Tagesübersicht übersprungen")
        return []

    local_tz = dt_util.get_time_zone(hass.config.time_zone)

    # Einen Tag vor start_date benötigen wir, um die Differenz für start_date zu berechnen
    query_start = datetime.datetime.combine(
        start_date - datetime.timedelta(days=1),
        datetime.time(0, 0),
        tzinfo=local_tz,
    )
    query_end = datetime.datetime.combine(
        end_date + datetime.timedelta(days=1),
        datetime.time(0, 0),
        tzinfo=local_tz,
    )

    try:
        recorder = get_instance(hass)
        stats = await recorder.async_add_executor_job(
            statistics_during_period,
            hass,
            query_start,
            query_end,
            {sensor_id},
            "day",
            None,  # keine Einheitenumrechnung – Sensor liefert bereits kWh
            {"sum"},
        )
    except Exception as exc:  # noqa: BLE001
        _LOGGER.warning("Recorder-Abfrage fehlgeschlagen: %s", exc)
        return []

    if not stats or sensor_id not in stats:
        _LOGGER.debug("Keine Statistiken für Sensor %s gefunden", sensor_id)
        return []

    # Dict: lokales Datum → kumulativer Summenwert
    # HA 2023.3+: entry["start"] ist float (Unix-Timestamp)
    # ältere HA:  entry["start"] ist datetime-Objekt
    sum_by_date: dict[datetime.date, float] = {}
    for entry in stats[sensor_id]:
        # Attributzugriff funktioniert sowohl für dict als auch für TypedDict/dataclass
        ts_raw = (
            entry.get("start")
            if isinstance(entry, dict)
            else getattr(entry, "start", None)
        )
        val = (
            entry.get("sum") if isinstance(entry, dict) else getattr(entry, "sum", None)
        )

        if ts_raw is None or val is None:
            continue

        # Timestamp in lokales Datum konvertieren (HA 2023+: float, ältere: datetime)
        if isinstance(ts_raw, (int, float)):
            dt_local = datetime.datetime.fromtimestamp(float(ts_raw), tz=local_tz)
        elif isinstance(ts_raw, datetime.datetime):
            tz = ts_raw.tzinfo or datetime.timezone.utc
            dt_local = ts_raw.replace(tzinfo=tz).astimezone(local_tz)
        else:
            continue

        sum_by_date[dt_local.date()] = float(val)

    _LOGGER.debug(
        "Recorder Tagessummen für %s: %d Einträge (%s bis %s)",
        sensor_id,
        len(sum_by_date),
        min(sum_by_date, default="–"),
        max(sum_by_date, default="–"),
    )

    # Tagesverbrauch = Differenz aufeinanderfolgender Tagessummen
    result: list[tuple[datetime.date, float | None]] = []
    prev_date = start_date - datetime.timedelta(days=1)
    current = start_date
    while current <= end_date:
        sum_prev = sum_by_date.get(prev_date)
        sum_curr = sum_by_date.get(current)

        if (
            sum_prev is not None
            and sum_curr is not None
            and math.isfinite(sum_prev)
            and math.isfinite(sum_curr)
            and sum_curr >= sum_prev
        ):
            consumption = sum_curr - sum_prev
        else:
            _LOGGER.debug(
                "Keine Recorder-Daten für %s (prev=%s, curr=%s)",
                current,
                sum_prev,
                sum_curr,
            )
            consumption = None

        result.append((current, consumption))
        prev_date = current
        current += datetime.timedelta(days=1)

    return result


async def _async_send_invoice(
    hass: HomeAssistant,
    entry: ConfigEntry,
    call: ServiceCall,
    *,
    test_mode: bool = False,
) -> None:
    """Serialize sending and correction so neither overwrites a newer baseline."""
    async with hass.data[DOMAIN][entry.entry_id]["lock"]:
        await _async_send_invoice_locked(hass, entry, call, test_mode=test_mode)


async def _async_send_invoice_locked(
    hass: HomeAssistant,
    entry: ConfigEntry,
    call: ServiceCall,
    *,
    test_mode: bool = False,
) -> None:
    """Generate PDF invoice and send via SMTP.

    Im test_mode werden KEINE gespeicherten Werte (last_reading, last_datetime etc.)
    verändert und kein Event gefeuert.
    """
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

    # Letzten Abrechnungsstand aus Speicher laden
    last_reading = stored.get("last_reading")
    last_date_str = stored.get("last_date")
    last_datetime_str = stored.get("last_datetime")

    try:
        today, now = _invoice_dates_from_service_call(call)
    except ValueError as exc:
        _LOGGER.error("%s", exc)
        return

    if last_reading is None:
        # Erste Abrechnung: Startwerte aus Konfiguration
        last_reading = float(cfg.get(CONF_INITIAL_READING, 0.0))
        initial_date_str = cfg.get(CONF_INITIAL_DATE)
        last_date = (
            datetime.date.fromisoformat(initial_date_str)
            if initial_date_str
            else today.replace(day=1)
        )
        start_datetime = datetime.datetime.combine(last_date, datetime.time(0, 0))
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
        if last_datetime_str:
            start_datetime = datetime.datetime.fromisoformat(last_datetime_str)
        else:
            start_datetime = datetime.datetime.combine(last_date, datetime.time(0, 0))

    owner_name = cfg[CONF_OWNER_NAME]
    meter_number = cfg[CONF_METER_NUMBER]
    recipients = _split_recipients(cfg[CONF_RECIPIENT_EMAIL])
    if not recipients:
        _LOGGER.error("Keine gültigen Empfänger-E-Mail-Adressen konfiguriert.")
        return
    price_per_kwh = float(cfg[CONF_PRICE_PER_KWH])

    # A live software counter is not proof of the physical meter reading.
    # Confirmation is mandatory for money claims, never inferred from the sensor.
    for value in (last_reading, current_reading, price_per_kwh):
        if not math.isfinite(float(value)) or float(value) < 0:
            raise ServiceValidationError(
                "Abrechnung: ungültiger Zählerstand oder Preis."
            )
    if current_reading < last_reading:
        raise ServiceValidationError(
            "Zählerstand liegt unter der letzten Abrechnung. Erst Ablesung und "
            "Abrechnungsstart prüfen; es wurde keine E-Mail gesendet."
        )
    if not test_mode:
        confirmed = call.data.get("confirmed_meter_reading")
        if confirmed is None:
            raise ServiceValidationError(
                "Physischer Zählerstand muss mit confirmed_meter_reading bestätigt "
                "werden. Am Zähler ablesen; es wurde keine E-Mail gesendet."
            )
        if (
            not math.isfinite(float(confirmed))
            or abs(float(confirmed) - current_reading) > 0.01
        ):
            raise ServiceValidationError(
                "Bestätigte Ablesung weicht vom Softwarezähler ab. Zähler erst "
                "abgleichen; es wurde keine E-Mail gesendet."
            )

    # Tagesstatistiken aus Recorder holen (wenn Option aktiv)
    # Optionaler separater Statistik-Sensor; Fallback auf Haupt-Energiesensor
    daily_data = None
    if cfg.get(CONF_INCLUDE_DAILY_STATS, DEFAULT_INCLUDE_DAILY_STATS):
        stats_sensor_id = cfg.get(CONF_STATS_SENSOR) or sensor_id
        stats_hour = int(cfg.get(CONF_DAILY_STATS_HOUR, DEFAULT_DAILY_STATS_HOUR))
        daily_data = await _async_fetch_daily_stats(
            hass, stats_sensor_id, last_date, today, stats_hour
        )

    # Lazy import (fpdf2 wird erst beim ersten Start installiert)
    from .pdf_generator import generate_invoice_pdf  # noqa: PLC0415

    pdf_bytes = await hass.async_add_executor_job(
        generate_invoice_pdf,
        owner_name,
        meter_number,
        recipients[0],
        last_date,
        today,
        last_reading,
        current_reading,
        price_per_kwh,
        start_datetime,
        daily_data,
    )

    period_label = last_date.strftime("%Y-%m")
    filename = f"Wallbox_Abrechnung_{period_label}.pdf"

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
    test_prefix = "TEST: " if test_mode else ""
    subject = (
        f"{test_prefix}Wallbox Ladekosten {last_date.strftime('%B %Y')} – "
        f"{total_cost:.2f} €"
    )
    body = (
        f"<p>Guten Tag,</p>"
        f"{('<p><strong style="color:#cc0000">[TEST-E-Mail – keine Werte wurden gespeichert]</strong></p>' if test_mode else '')}"
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
            _send_email_sync,
            smtp_cfg,
            recipients,
            subject,
            body,
            pdf_bytes,
            filename,
        )
    except Exception as exc:  # noqa: BLE001
        _LOGGER.error("E-Mail-Versand fehlgeschlagen: %s", exc)
        return

    if test_mode:
        _LOGGER.info(
            "Test-Abrechnung gesendet (keine Werte geändert): %.3f kWh, %.2f €",
            consumption,
            total_cost,
        )
        return

    # Persistenten Zustand nur bei echter Abrechnung speichern
    stored["last_reading"] = current_reading
    stored["last_date"] = today.isoformat()
    stored["last_datetime"] = now.isoformat()
    data["stored"] = stored
    await data["store"].async_save(stored)

    hass.bus.async_fire(f"{DOMAIN}_invoice_sent", {"entry_id": entry.entry_id})
    _LOGGER.info(
        "Wallbox-Abrechnung erfolgreich gesendet: %.3f kWh, %.2f €",
        consumption,
        total_cost,
    )


async def _async_send_sample_pdf(
    hass: HomeAssistant,
    entry: ConfigEntry,
    call: ServiceCall,
) -> None:
    """Generiert eine Beispiel-PDF mit Dummy-Daten und sendet sie per E-Mail."""
    data = hass.data[DOMAIN][entry.entry_id]
    cfg = data["config"]

    today = datetime.date.today()
    period_from = today.replace(day=1)
    price_per_kwh = float(cfg[CONF_PRICE_PER_KWH])

    # Dummy-Werte
    owner_name = "Max Mustermann (Beispiel)"
    meter_number = "WB-BEISPIEL-001"
    reading_prev = 1000.0
    reading_curr = 1234.567
    start_datetime = datetime.datetime.combine(period_from, datetime.time(8, 0))

    # Dummy-Tagesdaten: Verbrauch gleichmäßig auf die Tage verteilt, leicht variiert
    num_days = (today - period_from).days + 1
    total_consumption = reading_curr - reading_prev
    base_per_day = total_consumption / max(num_days, 1)
    rng = random.Random(42)
    raw = [
        max(0.0, base_per_day + rng.uniform(-base_per_day * 0.4, base_per_day * 0.4))
        for _ in range(num_days)
    ]
    # Normieren damit die Summe passt
    raw_sum = sum(raw) or 1.0
    daily_data = [
        (
            period_from + datetime.timedelta(days=i),
            round(v / raw_sum * total_consumption, 3),
        )
        for i, v in enumerate(raw)
    ]

    recipients = _split_recipients(cfg[CONF_RECIPIENT_EMAIL])
    if not recipients:
        _LOGGER.error("Keine gültigen Empfänger-E-Mail-Adressen konfiguriert.")
        return

    from .pdf_generator import generate_invoice_pdf  # noqa: PLC0415

    pdf_bytes = await hass.async_add_executor_job(
        generate_invoice_pdf,
        owner_name,
        meter_number,
        recipients[0],
        period_from,
        today,
        reading_prev,
        reading_curr,
        price_per_kwh,
        start_datetime,
        daily_data,
    )

    filename = f"Wallbox_Beispiel_{today.strftime('%Y-%m')}.pdf"
    smtp_cfg = {
        "host": cfg[CONF_SMTP_HOST],
        "port": int(cfg[CONF_SMTP_PORT]),
        "username": cfg.get(CONF_SMTP_USERNAME, ""),
        "password": cfg.get(CONF_SMTP_PASSWORD, ""),
        "from_email": cfg[CONF_SMTP_FROM_EMAIL],
        "use_tls": cfg.get(CONF_SMTP_USE_TLS, True),
        "use_ssl": cfg.get(CONF_SMTP_USE_SSL, False),
    }
    consumption = reading_curr - reading_prev
    total_cost = consumption * price_per_kwh
    subject = f"Wallbox Abrechnung – Beispiel-PDF ({today.strftime('%B %Y')})"
    body = (
        f"<p>Guten Tag,</p>"
        f"<p><strong>[BEISPIEL-PDF – enthält keine echten Werte]</strong></p>"
        f"<p>Anbei finden Sie eine Beispiel-Abrechnung zur Ansicht der PDF-Vorlage.</p>"
        f"<table style='border-collapse:collapse;font-family:sans-serif'>"
        f"<tr><td style='padding:4px 12px'>Zeitraum:</td>"
        f"<td style='padding:4px 12px'>{period_from.strftime('%d.%m.%Y')} – {today.strftime('%d.%m.%Y')}</td></tr>"
        f"<tr><td style='padding:4px 12px'>Verbrauch (Beispiel):</td>"
        f"<td style='padding:4px 12px'>{consumption:.3f} kWh</td></tr>"
        f"<tr><td style='padding:4px 12px'><strong>Betrag (Beispiel):</strong></td>"
        f"<td style='padding:4px 12px'><strong>{total_cost:.2f} €</strong></td></tr>"
        f"</table>"
        f"<p>Mit freundlichen Grüßen,<br/>{owner_name}</p>"
    )

    try:
        await hass.async_add_executor_job(
            _send_email_sync,
            smtp_cfg,
            recipients,
            subject,
            body,
            pdf_bytes,
            filename,
        )
    except Exception as exc:  # noqa: BLE001
        _LOGGER.error("Beispiel-PDF-Versand fehlgeschlagen: %s", exc)
        return

    _LOGGER.info("Beispiel-PDF erfolgreich gesendet an %s", ", ".join(recipients))


def _split_recipients(value: str) -> list[str]:
    """Split recipient emails by comma or semicolon and normalize entries."""
    return [email.strip() for email in re.split(r"[;,]", value) if email.strip()]


_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Optional("invoice_date"): str,
        vol.Optional("confirmed_meter_reading"): vol.All(
            vol.Coerce(float), vol.Range(min=0)
        ),
    },
    extra=vol.ALLOW_EXTRA,
)

_CORRECTION_SCHEMA = vol.Schema(
    {
        vol.Required("entry_id"): str,
        vol.Required("expected_last_reading"): vol.Coerce(float),
        vol.Required("expected_last_datetime"): str,
        vol.Required("corrected_reading"): vol.All(vol.Coerce(float), vol.Range(min=0)),
        vol.Required("reason"): vol.All(str, vol.Length(min=10, max=300)),
    }
)


async def _async_correct_last_reading(hass: HomeAssistant, call: ServiceCall) -> None:
    """Correct one persisted baseline using compare-and-set; no SMTP side effects.

    Example: stored 100, expected 100, corrected 99 keeps the existing billing
    date and records the 100 -> 99 correction. A newer stored reading refuses it.
    The public service is admin-only and shares the invoice's per-entry lock.
    """
    entry_id = call.data["entry_id"]
    data = hass.data.get(DOMAIN, {}).get(entry_id)
    if data is None:
        raise ServiceValidationError("Wallbox-Eintrag nicht geladen. entry_id prüfen.")
    async with data["lock"]:
        stored = data["stored"]
        previous = stored.get("last_reading")
        corrected = call.data["corrected_reading"]
        expected = call.data["expected_last_reading"]
        state = hass.states.get(data["config"][CONF_ENERGY_SENSOR])
        try:
            current = float(state.state) if state else math.nan
            valid = all(
                math.isfinite(float(v)) and float(v) >= 0
                for v in (previous, corrected, expected, current)
            )
        except (TypeError, ValueError):
            valid = False
        if not valid:
            raise ServiceValidationError(
                "Ablesungen fehlen oder sind ungültig. Sensor prüfen."
            )
        if (
            abs(previous - expected) > 0.000001
            or stored.get("last_datetime") != call.data["expected_last_datetime"]
        ):
            raise ServiceValidationError(
                "Abrechnungsstart wurde inzwischen geändert. Neu prüfen."
            )
        if corrected > current + 0.001:
            raise ServiceValidationError(
                "Abrechnungsstart darf nicht über dem aktuellen Zähler liegen."
            )

        updated = dict(stored)
        updated["last_reading"] = corrected
        updated["corrections"] = [
            *stored.get("corrections", []),
            {
                "at": dt_util.utcnow().isoformat(),
                "previous_reading": previous,
                "corrected_reading": corrected,
                "billing_datetime": stored["last_datetime"],
                "reason": call.data["reason"],
            },
        ]
        # Disk first: a failed save must leave in-memory entities unchanged.
        await data["store"].async_save(updated)
        data["stored"] = updated
        hass.bus.async_fire(f"{DOMAIN}_reading_corrected", {"entry_id": entry_id})
        _LOGGER.info(
            "Wallbox-Abrechnungsstart korrigiert; Datum unverändert, kein Versand"
        )


def _invoice_dates_from_service_call(
    call: ServiceCall,
) -> tuple[datetime.date, datetime.datetime]:
    """
    Resolve invoice date and timestamp for service execution.

    - invoice_date (optional): ISO date string YYYY-MM-DD.
    """
    requested_date = call.data.get("invoice_date")
    if not requested_date:
        return datetime.date.today(), datetime.datetime.now()

    if not isinstance(requested_date, str):
        raise ValueError(
            "Ungültiger Typ für invoice_date: Erwartet wird ein ISO-Datum 'YYYY-MM-DD'."
        )

    value = requested_date.strip()
    if not value:
        return datetime.date.today(), datetime.datetime.now()

    try:
        invoice_date = datetime.date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(
            f"Ungültiges invoice_date '{value}'. Format muss YYYY-MM-DD sein."
        ) from exc

    return invoice_date, datetime.datetime.combine(invoice_date, datetime.time(0, 0))


def _send_email_sync(
    smtp_cfg: dict,
    to_emails: list[str],
    subject: str,
    body_html: str,
    pdf_bytes: bytes,
    filename: str,
) -> None:
    """Blocking SMTP send – runs in executor."""
    msg = MIMEMultipart("mixed")
    msg["From"] = smtp_cfg["from_email"]
    msg["To"] = ", ".join(to_emails)
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

    server.send_message(msg, from_addr=smtp_cfg["from_email"], to_addrs=to_emails)
    server.quit()
