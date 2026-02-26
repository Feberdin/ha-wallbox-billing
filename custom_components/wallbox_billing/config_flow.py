"""Config flow for Wallbox Billing."""
from __future__ import annotations

import datetime
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

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
    DEFAULT_PRICE_PER_KWH,
    DEFAULT_SMTP_PORT,
    DEFAULT_SMTP_USE_SSL,
    DEFAULT_SMTP_USE_TLS,
    DOMAIN,
)

_STEP1_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENERGY_SENSOR): selector.EntitySelector(
            selector.EntitySelectorConfig(
                domain="sensor",
                device_class=SensorDeviceClass.ENERGY,
            )
        ),
        vol.Required(CONF_OWNER_NAME): selector.TextSelector(),
        vol.Required(CONF_METER_NUMBER): selector.TextSelector(),
        vol.Required(CONF_PRICE_PER_KWH, default=DEFAULT_PRICE_PER_KWH): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0.0,
                max=10.0,
                step=0.0001,
                mode=selector.NumberSelectorMode.BOX,
                unit_of_measurement="€/kWh",
            )
        ),
        vol.Required(CONF_INITIAL_READING, default=0.0): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0.0,
                max=9999999.0,
                step=0.001,
                mode=selector.NumberSelectorMode.BOX,
                unit_of_measurement="kWh",
            )
        ),
        vol.Required(
            CONF_INITIAL_DATE,
            default=datetime.date.today().replace(day=1).isoformat(),
        ): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.DATE)
        ),
    }
)

_STEP2_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_RECIPIENT_EMAIL): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.EMAIL)
        ),
        vol.Required(CONF_SMTP_HOST): selector.TextSelector(),
        vol.Required(CONF_SMTP_PORT, default=DEFAULT_SMTP_PORT): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=1,
                max=65535,
                step=1,
                mode=selector.NumberSelectorMode.BOX,
            )
        ),
        vol.Required(CONF_SMTP_FROM_EMAIL): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.EMAIL)
        ),
        vol.Optional(CONF_SMTP_USERNAME, default=""): selector.TextSelector(),
        vol.Optional(CONF_SMTP_PASSWORD, default=""): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        ),
        vol.Required(CONF_SMTP_USE_TLS, default=DEFAULT_SMTP_USE_TLS): selector.BooleanSelector(),
        vol.Required(CONF_SMTP_USE_SSL, default=DEFAULT_SMTP_USE_SSL): selector.BooleanSelector(),
    }
)


class WallboxBillingConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Wallbox Billing."""

    VERSION = 1

    def __init__(self) -> None:
        self._step1_data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 1: sensor + owner + billing start."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._step1_data = user_input
            return await self.async_step_smtp()

        return self.async_show_form(
            step_id="user",
            data_schema=_STEP1_SCHEMA,
            errors=errors,
            description_placeholders={
                "hint": (
                    "Wähle den ESPHome-Sensor 'Wallbox Zählerstand' und trage den "
                    "Zählerstand der letzten Abrechnung als Startwert ein."
                )
            },
        )

    async def async_step_smtp(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 2: SMTP settings."""
        errors: dict[str, str] = {}

        if user_input is not None:
            all_data = {**self._step1_data, **user_input}
            # Store initial billing state in persistent store via __init__ after setup
            return self.async_create_entry(
                title=f"Wallbox Abrechnung – {self._step1_data[CONF_OWNER_NAME]}",
                data=all_data,
            )

        return self.async_show_form(
            step_id="smtp",
            data_schema=_STEP2_SCHEMA,
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> "WallboxBillingOptionsFlow":
        return WallboxBillingOptionsFlow()


class WallboxBillingOptionsFlow(config_entries.OptionsFlow):
    """Options flow to update settings after initial setup."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show options form."""
        cfg = {**self.config_entry.data, **self.config_entry.options}
        errors: dict[str, str] = {}

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_PRICE_PER_KWH, default=float(cfg.get(CONF_PRICE_PER_KWH, DEFAULT_PRICE_PER_KWH))
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0.0,
                        max=10.0,
                        step=0.0001,
                        mode=selector.NumberSelectorMode.BOX,
                        unit_of_measurement="€/kWh",
                    )
                ),
                vol.Required(
                    CONF_RECIPIENT_EMAIL, default=cfg.get(CONF_RECIPIENT_EMAIL, "")
                ): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.EMAIL)
                ),
                vol.Required(
                    CONF_OWNER_NAME, default=cfg.get(CONF_OWNER_NAME, "")
                ): selector.TextSelector(),
                vol.Required(
                    CONF_METER_NUMBER, default=cfg.get(CONF_METER_NUMBER, "")
                ): selector.TextSelector(),
                vol.Required(
                    CONF_SMTP_HOST, default=cfg.get(CONF_SMTP_HOST, "")
                ): selector.TextSelector(),
                vol.Required(
                    CONF_SMTP_PORT, default=int(cfg.get(CONF_SMTP_PORT, DEFAULT_SMTP_PORT))
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1, max=65535, step=1, mode=selector.NumberSelectorMode.BOX
                    )
                ),
                vol.Required(
                    CONF_SMTP_FROM_EMAIL, default=cfg.get(CONF_SMTP_FROM_EMAIL, "")
                ): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.EMAIL)
                ),
                vol.Optional(
                    CONF_SMTP_USERNAME, default=cfg.get(CONF_SMTP_USERNAME, "")
                ): selector.TextSelector(),
                vol.Optional(
                    CONF_SMTP_PASSWORD, default=cfg.get(CONF_SMTP_PASSWORD, "")
                ): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                ),
                vol.Required(
                    CONF_SMTP_USE_TLS,
                    default=cfg.get(CONF_SMTP_USE_TLS, DEFAULT_SMTP_USE_TLS),
                ): selector.BooleanSelector(),
                vol.Required(
                    CONF_SMTP_USE_SSL,
                    default=cfg.get(CONF_SMTP_USE_SSL, DEFAULT_SMTP_USE_SSL),
                ): selector.BooleanSelector(),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
        )
