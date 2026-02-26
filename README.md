# Wallbox Abrechnung – Home Assistant Integration

Eine Home Assistant Custom Integration zur automatischen Abrechnung von Ladekosten für Dienstfahrzeuge an privaten Wallboxen.

## Hardware

- **ESP32** (esp32dev) mit ESPHome
- **Eltako DSZ15D** Energiezähler
- Anschluss über **S0-Schnittstelle** an GPIO14

## Features

- Automatische Berechnung des Verbrauchs seit der letzten Abrechnung
- Berechnung der Kosten (Verbrauch × konfigurierbarer kWh-Preis)
- **PDF-Rechnung** mit: Name, Zählernummer, Zeitraum, Zählerstand (vorher/nachher), Verbrauch, Preis/kWh, Gesamtbetrag
- Versand der PDF per E-Mail (SMTP, inkl. TLS/SSL)
- **Manueller Button** zum sofortigen Erstellen und Versenden
- **Service** `wallbox_billing.send_invoice` für Automationen (z. B. monatlich)
- Sensoren: Verbrauch seit letzter Abrechnung, Kosten, Datum und Zählerstand der letzten Abrechnung

## Installation

### Via HACS (empfohlen)

1. HACS → Integrationen → ⋮ → Benutzerdefinierte Repositories
2. URL: `https://github.com/Feberdin/ha-wallbox-billing` | Kategorie: Integration
3. Integration installieren → Home Assistant neu starten

### Manuell

1. Ordner `custom_components/wallbox_billing/` in dein HA-Konfigurationsverzeichnis kopieren
2. Home Assistant neu starten

## Einrichtung

1. **Einstellungen → Integrationen → + Integration hinzufügen → "Wallbox Abrechnung"**
2. **Schritt 1 – Grundeinstellungen:**
   - Energiesensor: `sensor.esp32_wallbox_wallbox_zahlerstand`
   - Dein Name (wird auf der PDF angezeigt)
   - Zählernummer (z. B. `DSZ15D-001`)
   - Strompreis in €/kWh
   - Zählerstand bei der **letzten** Abrechnung (Startwert)
   - Datum der letzten Abrechnung
3. **Schritt 2 – E-Mail / SMTP:**
   - Empfänger-E-Mail (Arbeitgeber)
   - SMTP-Serverdaten (Beispiele unten)

## SMTP-Beispielkonfigurationen

| Anbieter | Host | Port | TLS | SSL |
|----------|------|------|-----|-----|
| Gmail | `smtp.gmail.com` | `587` | ✅ | ❌ |
| Gmail (SSL) | `smtp.gmail.com` | `465` | ❌ | ✅ |
| GMX | `mail.gmx.net` | `587` | ✅ | ❌ |
| Web.de | `smtp.web.de` | `587` | ✅ | ❌ |
| Outlook/Hotmail | `smtp-mail.outlook.com` | `587` | ✅ | ❌ |
| iCloud | `smtp.mail.me.com` | `587` | ✅ | ❌ |

> **Gmail-Hinweis:** Du benötigst ein [App-Passwort](https://myaccount.google.com/apppasswords) (kein normales Google-Passwort).

## Monatliche Automation (Beispiel)

```yaml
alias: "Wallbox Abrechnung monatlich"
description: "Sendet die Wallbox-Abrechnung am 1. jeden Monats um 08:00 Uhr"
trigger:
  - platform: time
    at: "08:00:00"
condition:
  - condition: template
    value_template: "{{ now().day == 1 }}"
action:
  - service: wallbox_billing.send_invoice
mode: single
```

## Manuelle Abrechnung (Button)

In Home Assistant erscheint das Gerät **"Wallbox Abrechnung"** mit einem Button **"Rechnung erstellen & senden"**. Ein Klick erstellt sofort die PDF und versendet sie.

> **Wichtig:** Nach jeder Abrechnung (Button oder Automation) wird der aktuelle Zählerstand als neuer Startwert gespeichert.

## Sensoren

| Sensor | Beschreibung |
|--------|-------------|
| `sensor.wallbox_abrechnung_verbrauch_seit_letzter_abrechnung` | kWh seit letzter Abrechnung |
| `sensor.wallbox_abrechnung_kosten_seit_letzter_abrechnung` | Kosten in EUR |
| `sensor.wallbox_abrechnung_letzte_abrechnung` | Datum der letzten Abrechnung |
| `sensor.wallbox_abrechnung_zahlerstand_letzte_abrechnung` | Zählerstand bei letzter Abrechnung |

## Einstellungen ändern

**Einstellungen → Integrationen → Wallbox Abrechnung → Konfigurieren**

Hier kannst du jederzeit Strompreis, E-Mail-Adresse, SMTP-Daten usw. anpassen.

## ESPHome-Firmware

Die ESPHome-Konfiguration für den ESP32 liegt unter [`esphome/wallbox.yaml`](esphome/wallbox.yaml).

**Manuellen Zählerstand setzen (bei Anbieterwechsel):**
In Home Assistant unter dem ESP32-Gerät → Zahl **"Wallbox Zählerstand setzen"** → neuen Wert eingeben.

---

*Erstellt für Home Assistant mit ESPHome + Eltako DSZ15D über S0-Schnittstelle.*
