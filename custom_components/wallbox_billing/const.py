"""Constants for the Wallbox Billing integration."""

DOMAIN = "wallbox_billing"

# Config / Options keys
CONF_ENERGY_SENSOR = "energy_sensor"
CONF_PRICE_PER_KWH = "price_per_kwh"
CONF_RECIPIENT_EMAIL = "recipient_email"
CONF_OWNER_NAME = "owner_name"
CONF_METER_NUMBER = "meter_number"
CONF_INITIAL_READING = "initial_reading"
CONF_INITIAL_DATE = "initial_date"

CONF_SMTP_HOST = "smtp_host"
CONF_SMTP_PORT = "smtp_port"
CONF_SMTP_USERNAME = "smtp_username"
CONF_SMTP_PASSWORD = "smtp_password"
CONF_SMTP_FROM_EMAIL = "smtp_from_email"
CONF_SMTP_USE_TLS = "smtp_use_tls"
CONF_SMTP_USE_SSL = "smtp_use_ssl"

# Persistent storage
STORAGE_KEY = "wallbox_billing_store"
STORAGE_VERSION = 1

# Service
SERVICE_SEND_INVOICE = "send_invoice"

# Defaults
DEFAULT_PRICE_PER_KWH = 0.30
DEFAULT_SMTP_PORT = 587
DEFAULT_SMTP_USE_TLS = True
DEFAULT_SMTP_USE_SSL = False

# Entity unique-id suffixes
ENTITY_CONSUMPTION = "consumption_since_last_billing"
ENTITY_COST = "cost_since_last_billing"
ENTITY_LAST_BILLING_DATE = "last_billing_date"
ENTITY_LAST_BILLING_READING = "last_billing_reading"
ENTITY_SEND_INVOICE = "send_invoice"
ENTITY_TEST_INVOICE = "test_invoice"
ENTITY_SAMPLE_PDF = "sample_pdf"

# Daily stats options
CONF_INCLUDE_DAILY_STATS = "include_daily_stats"
CONF_DAILY_STATS_HOUR = "daily_stats_hour"
CONF_STATS_SENSOR = "stats_sensor"      # optionaler separater Sensor für Recorder-Statistiken
DEFAULT_INCLUDE_DAILY_STATS = True
DEFAULT_DAILY_STATS_HOUR = 0

# Additional services
SERVICE_SEND_TEST_INVOICE = "send_test_invoice"
SERVICE_SEND_SAMPLE_PDF = "send_sample_pdf"
