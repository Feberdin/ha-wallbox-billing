"""PDF invoice generator for Wallbox Billing.

fpdf2 is imported lazily inside generate_invoice_pdf() so that the integration
package can be loaded by Home Assistant even before fpdf2 is installed.
"""
from __future__ import annotations

import datetime


def _fmt_kwh(value: float) -> str:
    return f"{value:,.3f} kWh".replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_eur(value: float) -> str:
    return f"{value:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_price(value: float) -> str:
    return f"{value:.4f} €/kWh".replace(".", ",")


def generate_invoice_pdf(
    owner_name: str,
    meter_number: str,
    recipient_email: str,
    period_from: datetime.date,
    period_to: datetime.date,
    reading_previous: float,
    reading_current: float,
    price_per_kwh: float,
) -> bytes:
    """Generate a PDF invoice and return it as bytes.

    fpdf2 is imported here to avoid a top-level import error when the
    library is not yet installed (HA installs requirements on first boot).
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
    today_str = period_to.strftime("%d.%m.%Y")

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
                f"Automatisch erstellt am {today_str} · Wallbox Abrechnung für Home Assistant",
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
    pdf.cell(90, 7, "Empfänger (Arbeitgeber)", ln=True, fill=True)

    pdf.set_font("Helvetica", "", 11)
    pdf.cell(95, 7, owner_name, ln=False)
    pdf.cell(5, 7, "", ln=False)
    pdf.cell(90, 7, recipient_email, ln=True)

    pdf.ln(4)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(95, 6, f"Zählernummer: {meter_number}", ln=False)
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
    pdf.cell(col_w, 7, period_from.strftime("%d.%m.%Y"), ln=True)
    pdf.cell(col_w, 7, "Bis:", ln=False)
    pdf.cell(col_w, 7, period_to.strftime("%d.%m.%Y"), ln=True)

    pdf.ln(6)

    # ── Zählerstandsnachweis ─────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_fill_color(30, 60, 120)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 8, "  Zählerstandsnachweis", ln=True, fill=True)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 11)
    pdf.ln(2)

    # Table header
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_fill_color(220, 228, 245)
    pdf.cell(110, 7, "Position", ln=False, fill=True, border=1)
    pdf.cell(80, 7, "Wert", ln=True, fill=True, border=1, align="R")

    pdf.set_font("Helvetica", "", 11)
    rows = [
        ("Zählerstand (Beginn des Zeitraums)", _fmt_kwh(reading_previous)),
        ("Zählerstand (Ende des Zeitraums)", _fmt_kwh(reading_current)),
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
            f"für das Laden meines Dienstfahrzeuges an der privaten Wallbox "
            f"im Abrechnungszeitraum "
            f"{period_from.strftime('%d.%m.%Y')} bis {period_to.strftime('%d.%m.%Y')}."
        ),
    )

    pdf.ln(12)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 7, "Mit freundlichen Grüßen,", ln=True)
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, owner_name, ln=True)

    buf = BytesIO()
    buf.write(pdf.output())
    return buf.getvalue()
