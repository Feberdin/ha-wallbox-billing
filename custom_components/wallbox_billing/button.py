"""Button platform for Wallbox Billing."""
from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, ENTITY_SEND_INVOICE, SERVICE_SEND_INVOICE

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button entities."""
    async_add_entities([WallboxSendInvoiceButton(hass, entry)], update_before_add=False)


class WallboxSendInvoiceButton(ButtonEntity):
    """Button to manually trigger invoice generation and sending."""

    _attr_has_entity_name = True
    _attr_name = "Rechnung erstellen & senden"
    _attr_icon = "mdi:file-send"
    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self._hass = hass
        self._entry = entry

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_{ENTITY_SEND_INVOICE}"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "Wallbox Abrechnung",
            "manufacturer": "ESPHome / Eltako",
            "model": "DSZ15D",
        }

    async def async_press(self) -> None:
        """Called when the button is pressed."""
        _LOGGER.info("Manuelle Wallbox-Abrechnung ausgelöst")
        await self._hass.services.async_call(
            DOMAIN,
            SERVICE_SEND_INVOICE,
            {},
            blocking=False,
        )
