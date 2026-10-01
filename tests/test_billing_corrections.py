"""Billing regression tests with synthetic readings and no network or email.

Run: python -m unittest discover -s tests -v
Only external boundaries (storage, Recorder, SMTP and PDF rendering) are faked.
"""

import asyncio
import datetime as dt
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from homeassistant.exceptions import ServiceValidationError

from custom_components import wallbox_billing as billing
from custom_components.wallbox_billing.sensor import WallboxLastBillingReadingSensor


class BillingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.entry = SimpleNamespace(entry_id="test-entry")
        self.stored = {
            "last_reading": 100.0,
            "last_date": "2026-09-01",
            "last_datetime": "2026-09-01T08:00:00+02:00",
        }
        self.cfg = {
            "energy_sensor": "sensor.test_meter",
            "owner_name": "Test Owner",
            "meter_number": "TEST-1",
            "recipient_email": "billing@example.invalid",
            "price_per_kwh": 0.34,
            "include_daily_stats": False,
            "smtp_host": "smtp.example.invalid",
            "smtp_port": 587,
            "smtp_from_email": "sender@example.invalid",
        }
        self.data = {
            "stored": self.stored,
            "config": self.cfg,
            "store": SimpleNamespace(async_save=AsyncMock()),
            "lock": asyncio.Lock(),
        }

        async def execute(fn, *args):
            return fn(*args)

        self.hass = SimpleNamespace(
            data={"wallbox_billing": {self.entry.entry_id: self.data}},
            states=SimpleNamespace(get=Mock(return_value=SimpleNamespace(state="105"))),
            bus=SimpleNamespace(async_fire=Mock()),
            config=SimpleNamespace(time_zone="Europe/Berlin"),
            async_add_executor_job=execute,
        )
        self.mail = self.enterContext(patch.object(billing, "_send_email_sync"))
        self.pdf = self.enterContext(
            patch(
                "custom_components.wallbox_billing.pdf_generator.generate_invoice_pdf",
                return_value=b"synthetic PDF boundary",
            )
        )

    async def send(self, **data):
        await billing._async_send_invoice(
            self.hass, self.entry, SimpleNamespace(data=data)
        )

    async def test_unconfirmed_meter_blocks_real_invoice_before_email(self):
        with self.assertRaisesRegex(ServiceValidationError, "bestätigt"):
            await self.send()
        self.mail.assert_not_called()
        self.data["store"].async_save.assert_not_awaited()

    async def test_negative_consumption_blocks_invoice(self):
        self.hass.states.get.return_value.state = "99"
        with self.assertRaises(ServiceValidationError):
            await self.send(confirmed_meter_reading=99)
        self.mail.assert_not_called()

    async def test_nonfinite_reading_blocks_invoice(self):
        self.hass.states.get.return_value.state = "nan"
        with self.assertRaises(ServiceValidationError):
            await self.send(confirmed_meter_reading=105)
        self.mail.assert_not_called()

    async def test_mismatched_confirmation_blocks_invoice(self):
        with self.assertRaises(ServiceValidationError):
            await self.send(confirmed_meter_reading=104)
        self.mail.assert_not_called()

    async def test_confirmed_invoice_preserves_normal_send(self):
        await self.send(confirmed_meter_reading=105)
        self.mail.assert_called_once()
        self.data["store"].async_save.assert_awaited_once()
        self.assertEqual(self.data["stored"]["last_reading"], 105)

    async def test_missing_recorder_day_is_unknown_not_zero(self):
        day = dt.date(2026, 9, 2)
        recorder = SimpleNamespace(
            async_add_executor_job=AsyncMock(
                return_value={
                    "sensor.test_meter": [
                        {
                            "start": dt.datetime(
                                2026, 9, 2, tzinfo=dt.timezone.utc
                            ).timestamp(),
                            "sum": 10,
                        }
                    ],
                }
            )
        )
        with patch(
            "homeassistant.components.recorder.get_instance", return_value=recorder
        ):
            rows = await billing._async_fetch_daily_stats(
                self.hass, "sensor.test_meter", day, day
            )
        self.assertEqual(rows, [(day, None)])

    def correction_call(self, **changes):
        fields = {
            "entry_id": self.entry.entry_id,
            "expected_last_reading": 100.0,
            "expected_last_datetime": self.stored["last_datetime"],
            "corrected_reading": 99.0,
            "reason": "Verified synthetic meter photo",
        }
        fields.update(changes)
        return SimpleNamespace(data=fields)

    async def correct(self, **changes):
        handler = getattr(billing, "_async_correct_last_reading", None)
        self.assertTrue(callable(handler), "A persistent correction service is missing")
        await handler(self.hass, self.correction_call(**changes))

    async def test_correction_persists_and_refreshes_without_email(self):
        await self.correct()
        self.assertEqual(self.data["stored"]["last_reading"], 99)
        self.assertEqual(
            self.data["stored"]["last_datetime"], self.stored["last_datetime"]
        )
        self.assertEqual(
            self.data["stored"]["corrections"][-1]["previous_reading"], 100
        )
        self.data["store"].async_save.assert_awaited_once()
        self.mail.assert_not_called()
        self.hass.bus.async_fire.assert_called_once_with(
            "wallbox_billing_reading_corrected", {"entry_id": "test-entry"}
        )

    async def test_stale_expected_reading_refuses_overwrite(self):
        with self.assertRaises(ServiceValidationError):
            await self.correct(expected_last_reading=98)
        self.data["store"].async_save.assert_not_awaited()

    async def test_future_baseline_refuses_overwrite(self):
        with self.assertRaises(ServiceValidationError):
            await self.correct(corrected_reading=106)
        self.data["store"].async_save.assert_not_awaited()

    async def test_storage_failure_keeps_old_state_and_no_event(self):
        self.data["store"].async_save.side_effect = OSError("synthetic storage failure")
        with self.assertRaises(OSError):
            await self.correct()
        self.assertEqual(self.data["stored"]["last_reading"], 100)
        self.hass.bus.async_fire.assert_not_called()

    def test_baseline_sensor_exposes_timestamp_without_configuration(self):
        sensor = WallboxLastBillingReadingSensor(self.hass, self.entry, self.data)
        self.assertEqual(
            sensor.extra_state_attributes,
            {
                "billing_datetime": "2026-09-01T08:00:00+02:00",
                "correction_count": 0,
            },
        )


if __name__ == "__main__":
    unittest.main()
