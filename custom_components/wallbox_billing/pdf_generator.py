"""PDF invoice generator for Wallbox Billing.

fpdf2 is imported lazily inside generate_invoice_pdf() so that the integration
package can be loaded by Home Assistant even before fpdf2 is installed.
"""
from __future__ import annotations

import datetime


def _fmt_kwh(value: float) -> str:
    return f"{value:,.3f} kWh".replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_eur(value: float) -> str:
    # fpdf2's built-in fonts use latin-1; the € sign (U+20AC) is outside that
    # range, so we use "EUR" which is universally accepted on German invoices.
    return f"{value:,.2f} EUR".replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_price(value: float) -> str:
    return f"{value:.4f} EUR/kWh".replace(".", ",")


def _fmt_date(d: datetime.date) -> str:
    return d.strftime("%d.%m.%Y")


def _fmt_datetime(dt: datetime.datetime) -> str:
    return dt.strftime("%d.%m.%Y %H:%M Uhr")


def generate_invoice_pdf(
    owner_name: str,
    meter_number: str,
    recipient_email: str,
    period_from: datetime.date,
    period_to: datetime.date,
    reading_previous: float,
    reading_current: float,
    price_per_kwh: float,
    start_datetime: datetime.datetime | None = None,
    daily_data: list[tuple[datetime.date, float]] | None = None,
) -> bytes:
    """Generate a PDF invoice and return it as bytes.

    fpdf2 is imported here to avoid a top-level import error when the
    library is not yet installed (HA installs requirements on first boot).

    Parameters
    ----------
    start_datetime:
        Exakter Zeitstempel des letzten Abrechnungsstarts (wird auf Seite 1
        angezeigt). Falls None, wird nur das Datum verwendet.
    daily_data:
        Liste von (date, kwh) für jeden Kalendertag im Abrechnungszeitraum.
        Falls übergeben, wird eine zweite Seite mit Tagesübersicht erzeugt.
    """
    try:
        from fpdf import FPDF  # noqa: PLC0415
    except ImportError as exc:
        raise ImportError(
            "Das Paket 'fpdf2' ist nicht installiert. "
            "Bitte Home Assistant neu starten, damit die Anforderung installiert wird."
        ) from exc

    from io import BytesIO  # noqa: PLC0415

    consumption = reading_current - reading_previous
    total_cost = consumption * price_per_kwh
    today_str = _fmt_date(period_to)
    now_str = datetime.datetime.now().strftime("%d.%m.%Y %H:%M Uhr")

    class _InvoicePDF(FPDF):
        def header(self) -> None:
            self.set_font("Helvetica", "B", 22)
            self.set_text_color(30, 60, 120)
            self.cell(0, 12, "Erstattungsanforderung", ln=True, align="C")
            self.set_font("Helvetica", "", 13)
            self.set_text_color(60, 60, 60)
            self.cell(0, 8, "Ladekosten Dienstfahrzeug (Wallbox)", ln=True, align="C")
            self.ln(3)
            self.set_draw_color(30, 60, 120)
            self.set_line_width(0.8)
            self.line(10, self.get_y(), 200, self.get_y())
            self.ln(6)
            self.set_text_color(0, 0, 0)
            self.set_line_width(0.2)

        def footer(self) -> None:
            self.set_y(-14)
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(130, 130, 130)
            self.cell(
                0,
                10,
                f"Automatisch erstellt am {now_str} · Wallbox Abrechnung fuer Home Assistant",
                align="C",
            )

    pdf = _InvoicePDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    # ── Sender / Recipient block ─────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_fill_color(240, 243, 250)
    pdf.cell(95, 7, "Absender", ln=False, fill=True)
    pdf.cell(5, 7, "", ln=False)
    pdf.cell(90, 7, "Empfaenger (Arbeitgeber)", ln=True, fill=True)

    pdf.set_font("Helvetica", "", 11)
    pdf.cell(95, 7, owner_name, ln=False)
    pdf.cell(5, 7, "", ln=False)
    pdf.cell(90, 7, recipient_email, ln=True)

    pdf.ln(4)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(95, 6, f"Zahlernummer: {meter_number}", ln=False)
    pdf.cell(5, 6, "", ln=False)
    pdf.cell(90, 6, f"Datum: {today_str}", ln=True)
    pdf.set_text_color(0, 0, 0)

    pdf.ln(6)

    # ── Abrechnungszeitraum ──────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_fill_color(30, 60, 120)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 8, "  Abrechnungszeitraum", ln=True, fill=True)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 11)
    pdf.ln(2)

    col_w = 90
    pdf.cell(col_w, 7, "Von:", ln=False)
    pdf.cell(col_w, 7, _fmt_date(period_from), ln=True)
    pdf.cell(col_w, 7, "Bis:", ln=False)
    pdf.cell(col_w, 7, _fmt_date(period_to), ln=True)

    pdf.ln(6)

    # ── Zählerstandsnachweis ─────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_fill_color(30, 60, 120)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 8, "  Zaehlerstandsnachweis", ln=True, fill=True)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 11)
    pdf.ln(2)

    # Zeitstempel für Beginn
    if start_datetime is not None:
        begin_label = f"Zaehlerstand Beginn ({_fmt_datetime(start_datetime)})"
    else:
        begin_label = f"Zaehlerstand Beginn ({_fmt_date(period_from)})"

    end_label = f"Zaehlerstand Ende ({_fmt_datetime(datetime.datetime.now())})"

    # Table header
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_fill_color(220, 228, 245)
    pdf.cell(110, 7, "Position", ln=False, fill=True, border=1)
    pdf.cell(80, 7, "Wert", ln=True, fill=True, border=1, align="R")

    pdf.set_font("Helvetica", "", 11)
    rows = [
        (begin_label, _fmt_kwh(reading_previous)),
        (end_label, _fmt_kwh(reading_current)),
        ("Verbrauch", _fmt_kwh(consumption)),
        ("Preis je kWh", _fmt_price(price_per_kwh)),
    ]
    for i, (label, value) in enumerate(rows):
        fill_color = (248, 250, 255) if i % 2 == 0 else (255, 255, 255)
        pdf.set_fill_color(*fill_color)
        pdf.cell(110, 7, f"  {label}", ln=False, fill=True, border=1)
        pdf.cell(80, 7, value, ln=True, fill=True, border=1, align="R")

    # Total row
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_fill_color(30, 60, 120)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(110, 9, "  GESAMTBETRAG", ln=False, fill=True, border=1)
    pdf.cell(80, 9, _fmt_eur(total_cost), ln=True, fill=True, border=1, align="R")
    pdf.set_text_color(0, 0, 0)

    pdf.ln(8)

    # ── Zahlungsaufforderung ─────────────────────────────────────────────────
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(
        0,
        7,
        (
            f"Ich bitte um Erstattung des Betrages von {_fmt_eur(total_cost)} "
            f"fuer das Laden meines Dienstfahrzeuges an der privaten Wallbox "
            f"im Abrechnungszeitraum "
            f"{_fmt_date(period_from)} bis {_fmt_date(period_to)}."
        ),
    )

    pdf.ln(12)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 7, "Mit freundlichen Gruessen,", ln=True)
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, owner_name, ln=True)

    # ── Seite 2: Tagesübersicht ───────────────────────────────────────────────
    if daily_data is not None:
        _add_daily_page(pdf, daily_data, price_per_kwh, consumption, total_cost)

    buf = BytesIO()
    buf.write(pdf.output())
    return buf.getvalue()


def _add_daily_page(
    pdf,
    daily_data: list[tuple[datetime.date, float]],
    price_per_kwh: float,
    billed_consumption: float,
    billed_total: float,
) -> None:
    """Fügt Seite 2 mit der Tagesübersicht an das PDF an."""
    pdf.add_page()

    # ── Seitenüberschrift ────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_fill_color(30, 60, 120)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 10, "  Tagesuebersicht: Verbrauch und Kosten", ln=True, fill=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    # ── Tabellen-Header ──────────────────────────────────────────────────────
    col_date = 60
    col_kwh = 70
    col_eur = 60

    pdf.set_font("Helvetica", "B", 10)
    pdf.set_fill_color(220, 228, 245)
    pdf.cell(col_date, 7, "  Datum", ln=False, fill=True, border=1)
    pdf.cell(col_kwh, 7, "Verbrauch (kWh)", ln=False, fill=True, border=1, align="R")
    pdf.cell(col_eur, 7, "Kosten (EUR)", ln=True, fill=True, border=1, align="R")

    # ── Tageszeilen ──────────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "", 10)
    for i, (day, kwh) in enumerate(daily_data):
        cost = kwh * price_per_kwh
        fill_color = (248, 250, 255) if i % 2 == 0 else (255, 255, 255)
        pdf.set_fill_color(*fill_color)
        pdf.cell(col_date, 6, f"  {_fmt_date(day)}", ln=False, fill=True, border=1)
        pdf.cell(col_kwh, 6, _fmt_kwh(kwh), ln=False, fill=True, border=1, align="R")
        pdf.cell(col_eur, 6, _fmt_eur(cost), ln=True, fill=True, border=1, align="R")

    # ── Summenzeile ──────────────────────────────────────────────────────────
    daily_sum_kwh = sum(kwh for _, kwh in daily_data)
    daily_sum_eur = daily_sum_kwh * price_per_kwh

    pdf.set_font("Helvetica", "B", 10)
    pdf.set_fill_color(200, 215, 240)
    pdf.cell(col_date, 7, "  Summe Tageswerte", ln=False, fill=True, border=1)
    pdf.cell(col_kwh, 7, _fmt_kwh(daily_sum_kwh), ln=False, fill=True, border=1, align="R")
    pdf.cell(col_eur, 7, _fmt_eur(daily_sum_eur), ln=True, fill=True, border=1, align="R")

    pdf.ln(4)

    # ── Plausibilitätsprüfung ────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_fill_color(240, 243, 250)
    pdf.cell(col_date, 7, "  Rechnungsbetrag (S. 1)", ln=False, fill=True, border=1)
    pdf.cell(col_kwh, 7, _fmt_kwh(billed_consumption), ln=False, fill=True, border=1, align="R")
    pdf.cell(col_eur, 7, _fmt_eur(billed_total), ln=True, fill=True, border=1, align="R")

    diff_kwh = daily_sum_kwh - billed_consumption
    diff_eur = daily_sum_eur - billed_total
    abs_diff = abs(diff_kwh)

    if abs_diff > 0.05:
        # Differenz vorhanden – hervorheben
        pdf.set_fill_color(255, 235, 200)
        pdf.set_text_color(180, 60, 0)
    else:
        # Werte stimmen überein
        pdf.set_fill_color(220, 245, 220)
        pdf.set_text_color(0, 120, 0)

    sign = "+" if diff_kwh >= 0 else ""
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(col_date, 7, "  Differenz", ln=False, fill=True, border=1)
    pdf.cell(
        col_kwh, 7,
        f"{sign}{_fmt_kwh(diff_kwh)}",
        ln=False, fill=True, border=1, align="R",
    )
    pdf.cell(
        col_eur, 7,
        f"{sign}{_fmt_eur(diff_eur)}",
        ln=True, fill=True, border=1, align="R",
    )
    pdf.set_text_color(0, 0, 0)

    # ── Hinweistext ──────────────────────────────────────────────────────────
    pdf.ln(6)
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(100, 100, 100)
    hint = (
        "Hinweis: Die Tageswerte basieren auf den stündlichen Statistiken des "
        "Home Assistant Recorders. Die Ablesung erfolgt täglich zur konfigurierten "
        "Stunde (Standardwert: 00:00 Uhr). Differenzen zum Rechnungsbetrag entstehen "
        "durch unterschiedliche Ablese-Uhrzeiten beim Abrechnungsstart und -ende "
        "(z. B. wenn eine Abrechnung tagsüber ausgelöst wird). "
        "Fehlende Recorder-Daten werden als 0,000 kWh dargestellt."
    )
    pdf.multi_cell(col_date + col_kwh + col_eur, 5, hint)
    pdf.set_text_color(0, 0, 0)
