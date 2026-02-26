"""Sensor platform for Wallbox Billing."""
from __future__ import annotations

import datetime
import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    CONF_ENERGY_SENSOR,
    CONF_PRICE_PER_KWH,
    DOMAIN,
    ENTITY_CONSUMPTION,
    ENTITY_COST,
    ENTITY_LAST_BILLING_DATE,
    ENTITY_LAST_BILLING_READING,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities."""
    domain_data = hass.data[DOMAIN][entry.entry_id]

    entities = [
        WallboxConsumptionSensor(hass, entry, domain_data),
        WallboxCostSensor(hass, entry, domain_data),
        WallboxLastBillingDateSensor(hass, entry, domain_data),
        WallboxLastBillingReadingSensor(hass, entry, domain_data),
    ]
    async_add_entities(entities, update_before_add=True)


class _WallboxBaseSensor(SensorEntity):
    """Base class for Wallbox Billing sensors."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        domain_data: dict,
    ) -> None:
        self._hass = hass
        self._entry = entry
        self._domain_data = domain_data

    @property
    def _cfg(self) -> dict:
        return self._domain_data["config"]

    @property
    def _stored(self) -> dict:
        return self._domain_data["stored"]

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "Wallbox Abrechnung",
            "manufacturer": "ESPHome / Eltako",
            "model": "DSZ15D",
        }

    async def async_added_to_hass(self) -> None:
        """Subscribe to updates."""
        sensor_id = self._cfg[CONF_ENERGY_SENSOR]
        self.async_on_remove(
            async_track_state_change_event(
                self._hass, [sensor_id], self._handle_sensor_update
            )
        )
        self.async_on_remove(
            self._hass.bus.async_listen(
                f"{DOMAIN}_invoice_sent", self._handle_invoice_sent
            )
        )

    @callback
    def _handle_sensor_update(self, event) -> None:
        self.async_write_ha_state()

    @callback
    def _handle_invoice_sent(self, event) -> None:
        if event.data.get("entry_id") == self._entry.entry_id:
            self.async_write_ha_state()

    def _current_reading(self) -> float | None:
        state = self._hass.states.get(self._cfg[CONF_ENERGY_SENSOR])
        if state is None or state.state in ("unknown", "unavailable"):
            return None
        try:
            return float(state.state)
        except ValueError:
            return None

    def _last_reading(self) -> float | None:
        val = self._stored.get("last_reading")
        if val is None:
            # Fall back to initial_reading from config
            val = self._cfg.get("initial_reading")
        return float(val) if val is not None else None


class WallboxConsumptionSensor(_WallboxBaseSensor):
    """Consumption since last billing in kWh."""

    _attr_name = "Verbrauch seit letzter Abrechnung"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_icon = "mdi:lightning-bolt"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_{ENTITY_CONSUMPTION}"

    @property
    def native_value(self) -> float | None:
        current = self._current_reading()
        last = self._last_reading()
        if current is None or last is None:
            return None
        return round(current - last, 3)


class WallboxCostSensor(_WallboxBaseSensor):
    """Estimated cost since last billing in EUR."""

    _attr_name = "Kosten seit letzter Abrechnung"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = "EUR"
    _attr_icon = "mdi:currency-eur"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_{ENTITY_COST}"

    @property
    def native_value(self) -> float | None:
        current = self._current_reading()
        last = self._last_reading()
        price = float(self._cfg.get(CONF_PRICE_PER_KWH, 0.30))
        if current is None or last is None:
            return None
        return round((current - last) * price, 2)


class WallboxLastBillingDateSensor(_WallboxBaseSensor):
    """Date of the last sent invoice."""

    _attr_name = "Letzte Abrechnung"
    _attr_device_class = SensorDeviceClass.DATE
    _attr_icon = "mdi:calendar-check"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_{ENTITY_LAST_BILLING_DATE}"

    @property
    def native_value(self) -> datetime.date | None:
        val = self._stored.get("last_date")
        if val is None:
            val = self._cfg.get("initial_date")
        if val is None:
            return None
        try:
            return datetime.date.fromisoformat(val)
        except ValueError:
            return None


class WallboxLastBillingReadingSensor(_WallboxBaseSensor):
    """Meter reading at the time of last billing."""

    _attr_name = "Zählerstand letzte Abrechnung"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_icon = "mdi:counter"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_{ENTITY_LAST_BILLING_READING}"

    @property
    def native_value(self) -> float | None:
        return self._last_reading()
