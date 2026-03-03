"""Button platform for Wallbox Billing."""
from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    ENTITY_SAMPLE_PDF,
    ENTITY_SEND_INVOICE,
    ENTITY_TEST_INVOICE,
    SERVICE_SEND_INVOICE,
    SERVICE_SEND_SAMPLE_PDF,
    SERVICE_SEND_TEST_INVOICE,
)

_LOGGER = logging.getLogger(__name__)

_DEVICE_INFO = {
    "name": "Wallbox Abrechnung",
    "manufacturer": "ESPHome / Eltako",
    "model": "DSZ15D",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button entities."""
    async_add_entities(
        [
            WallboxSendInvoiceButton(hass, entry),
            WallboxTestInvoiceButton(hass, entry),
            WallboxSamplePDFButton(hass, entry),
        ],
        update_before_add=False,
    )


class _WallboxBaseButton(ButtonEntity):
    """Base class for Wallbox Billing buttons."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self._hass = hass
        self._entry = entry

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            **_DEVICE_INFO,
        }


class WallboxSendInvoiceButton(_WallboxBaseButton):
    """Button to manually trigger invoice generation and sending."""

    _attr_name = "Rechnung erstellen & senden"
    _attr_icon = "mdi:file-send"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_{ENTITY_SEND_INVOICE}"

    async def async_press(self) -> None:
        _LOGGER.info("Manuelle Wallbox-Abrechnung ausgelöst")
        await self._hass.services.async_call(
            DOMAIN, SERVICE_SEND_INVOICE, {}, blocking=False
        )


class WallboxTestInvoiceButton(_WallboxBaseButton):
    """Button to send a test invoice without changing any stored state."""

    _attr_name = "Test-Rechnung senden"
    _attr_icon = "mdi:file-send-outline"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_{ENTITY_TEST_INVOICE}"

    async def async_press(self) -> None:
        _LOGGER.info("Test-Rechnung ausgelöst (kein State-Update)")
        await self._hass.services.async_call(
            DOMAIN, SERVICE_SEND_TEST_INVOICE, {}, blocking=False
        )


class WallboxSamplePDFButton(_WallboxBaseButton):
    """Button to send a sample PDF with dummy data."""

    _attr_name = "Beispiel-PDF senden"
    _attr_icon = "mdi:file-pdf-box"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_{ENTITY_SAMPLE_PDF}"

    async def async_press(self) -> None:
        _LOGGER.info("Beispiel-PDF-Versand ausgelöst")
        await self._hass.services.async_call(
            DOMAIN, SERVICE_SEND_SAMPLE_PDF, {}, blocking=False
        )
