"""Offline PDF smoke test: synthetic readings and no private output files."""

import datetime as dt
import unittest

from custom_components.wallbox_billing.pdf_generator import generate_invoice_pdf


class PDFTests(unittest.TestCase):
    def test_missing_daily_reading_still_renders_valid_pdf(self):
        result = generate_invoice_pdf(
            "Test Owner",
            "TEST-1",
            "billing@example.invalid",
            dt.date(2026, 9, 1),
            dt.date(2026, 10, 1),
            100.0,
            105.0,
            0.34,
            daily_data=[(dt.date(2026, 9, 1), None), (dt.date(2026, 9, 2), 5.0)],
        )
        self.assertTrue(result.startswith(b"%PDF-"))
        self.assertIn(b"%%EOF", result)
        self.assertGreater(len(result), 1000)
