# Wallbox Abrechnung

[![Version](https://img.shields.io/badge/version-1.0.4-blue.svg)](https://github.com/Feberdin/ha-wallbox-billing/releases)
[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)
[![HA](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-brightgreen.svg)](https://www.home-assistant.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Eine Home Assistant Custom Integration zur automatischen Erstellung und dem Versand von monatlichen **Erstattungsanforderungen** für Ladekosten des Dienstfahrzeuges an der privaten Wallbox.

Die Integration erstellt ein professionelles **PDF-Dokument** mit allen relevanten Daten und versendet es direkt per E-Mail an den Arbeitgeber.

---

## Inhaltsverzeichnis

- [Features](#features)
- [Hardware](#hardware)
- [Installation](#installation)
- [Einrichtung](#einrichtung)
- [E-Mail-Konfiguration](#e-mail-konfiguration)
  - [Gmail App-Passwort erstellen](#gmail-app-passwort-erstellen)
  - [SMTP-Übersicht aller Anbieter](#smtp-übersicht-aller-anbieter)
- [Automationen](#automationen)
  - [Monatlicher automatischer Versand](#monatlicher-automatischer-versand)
  - [Benachrichtigung nach Versand](#benachrichtigung-nach-versand)
- [Button & manueller Versand](#button--manueller-versand)
- [Sensoren](#sensoren)
- [Einstellungen nachträglich ändern](#einstellungen-nachträglich-ändern)
- [ESPHome-Firmware](#esphome-firmware)

---

## Features

- **PDF-Rechnung** auf Knopfdruck oder per Automation mit:
  - Name, Zählernummer, Abrechnungszeitraum
  - Zählerstand zu Beginn und Ende des Zeitraums
  - Verbrauch in kWh
  - Strompreis je kWh
  - Gesamtbetrag in EUR
- Versand per **E-Mail** (SMTP) mit PDF als Anhang und HTML-Zusammenfassung im E-Mail-Text
- **Monatliche Automation** möglich (Service `wallbox_billing.send_invoice`)
- **Manueller Button** für sofortigen Versand
- **4 Sensoren** für aktuellen Verbrauch, Kosten, letztes Abrechnungsdatum und Zählerstand
- Alle Einstellungen jederzeit über die HA-Oberfläche änderbar
- Persistente Speicherung des letzten Zählerstandes über HA-Neustarts hinweg

---

## Hardware

Diese Integration wurde entwickelt für:

- **ESP32** (esp32dev) mit [ESPHome](https://esphome.io)
- **Eltako DSZ15D** Energiezähler
- Verbindung über **S0-Schnittstelle** an GPIO14 (1000 Impulse/kWh)

Die ESPHome-Konfiguration liegt unter [`esphome/wallbox.yaml`](esphome/wallbox.yaml).

---

## Installation

### Via HACS (empfohlen)

1. **HACS** → Integrationen → Menü (⋮) oben rechts → **Benutzerdefinierte Repositories**
2. URL eingeben: `https://github.com/Feberdin/ha-wallbox-billing`
3. Kategorie: **Integration** → Hinzufügen
4. Integration in der Liste suchen und **Herunterladen**
5. Home Assistant **neu starten**

### Manuell

1. Den Ordner `custom_components/wallbox_billing/` in dein HA-Konfigurationsverzeichnis kopieren (neben `configuration.yaml`)
2. Home Assistant **neu starten**

---

## Einrichtung

1. **Einstellungen → Integrationen → + Integration hinzufügen**
2. Nach **„Wallbox Abrechnung"** suchen und auswählen

### Schritt 1 – Grundeinstellungen

| Feld | Beschreibung | Beispiel |
|------|-------------|---------|
| Energiesensor | ESPHome-Sensor mit dem Zählerstand | `sensor.esp32_wallbox_wallbox_zahlerstand` |
| Dein Name | Wird auf der PDF als Absender angezeigt | `Max Mustermann` |
| Zählernummer | Seriennummer des Energiezählers | `DSZ15D-001` |
| Strompreis (€/kWh) | Aktueller Hausstrompreis | `0,3400` |
| Startwert (kWh) | Zählerstand der **letzten** Abrechnung | `4523,456` |
| Startdatum | Datum der letzten Abrechnung | `01.02.2026` |

### Schritt 2 – E-Mail / SMTP

| Feld | Beschreibung |
|------|-------------|
| Empfänger-E-Mail | E-Mail-Adresse des Arbeitgebers |
| SMTP-Host | Mailserver deines E-Mail-Anbieters |
| Port | Meist 587 (TLS) oder 465 (SSL) |
| Absender-E-Mail | Deine E-Mail-Adresse |
| Benutzername | Deine E-Mail-Adresse (oder leer lassen) |
| Passwort | Dein Passwort oder App-Passwort |
| TLS | Bei Port 587: **Ein** |
| SSL | Bei Port 465: **Ein** |

> Alle Einstellungen können jederzeit unter **Einstellungen → Integrationen → Wallbox Abrechnung → Konfigurieren** geändert werden.

---

## E-Mail-Konfiguration

### Gmail App-Passwort erstellen

Google lässt für externe Apps wie Home Assistant kein normales Google-Passwort zu. Stattdessen wird ein **App-Passwort** benötigt.

**Voraussetzung:** 2-Faktor-Authentifizierung muss bei Google aktiviert sein.

**Schritt-für-Schritt:**

1. Gehe zu [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
   *(du musst in deinem Google-Konto eingeloggt sein)*

2. Klicke auf **„App-Passwort erstellen"**

3. Gib einen beliebigen Namen ein, z. B. `Home Assistant Wallbox`

4. Klicke auf **„Erstellen"**

5. Du bekommst ein **16-stelliges Passwort** angezeigt (Format: `xxxx xxxx xxxx xxxx`)

6. Kopiere dieses Passwort und trage es in der Integration unter **Passwort** ein
   *(Leerzeichen werden beim Einfügen automatisch ignoriert)*

**Gmail SMTP-Einstellungen:**

| Feld | Wert |
|------|------|
| SMTP-Host | `smtp.gmail.com` |
| Port | `587` |
| TLS | **Ein** |
| SSL | **Aus** |
| Benutzername | deine vollständige Gmail-Adresse |
| Passwort | das 16-stellige App-Passwort |

> **Hinweis:** Das App-Passwort gilt nur für diese eine Anwendung und kann jederzeit unter [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) widerrufen werden.

---

### SMTP-Übersicht aller Anbieter

| Anbieter | Host | Port | TLS | SSL | Hinweis |
|----------|------|------|:---:|:---:|---------|
| **Gmail** | `smtp.gmail.com` | `587` | ✅ | ❌ | App-Passwort erforderlich |
| **Gmail (SSL)** | `smtp.gmail.com` | `465` | ❌ | ✅ | App-Passwort erforderlich |
| **GMX** | `mail.gmx.net` | `587` | ✅ | ❌ | Normales Passwort |
| **Web.de** | `smtp.web.de` | `587` | ✅ | ❌ | Normales Passwort |
| **T-Online** | `securesmtp.t-online.de` | `587` | ✅ | ❌ | Normales Passwort |
| **iCloud** | `smtp.mail.me.com` | `587` | ✅ | ❌ | App-Passwort erforderlich |
| **Outlook.com** | `smtp-mail.outlook.com` | `587` | ✅ | ❌ | Nur private Konten ohne 2FA |

> **Outlook / Microsoft 365:** Microsoft hat Basic-Authentifizierung für persönliche Microsoft 365-Konten seit September 2024 deaktiviert. Für private Outlook.com-Konten ohne 2FA kann es noch funktionieren. Empfehlung: Gmail oder GMX verwenden.

---

## Automationen

### Monatlicher automatischer Versand

Diese Automation sendet die Abrechnung automatisch am **1. jeden Monats um 08:00 Uhr**.

**Einrichten:** Einstellungen → Automationen → **+ Neu erstellen** → oben rechts **YAML bearbeiten** → folgenden Code einfügen:

```yaml
alias: "Wallbox Abrechnung – Monatlich senden"
description: "Erstellt und sendet am 1. jeden Monats die Wallbox-Abrechnung per E-Mail"
trigger:
  - platform: time
    at: "08:00:00"
condition:
  - condition: template
    value_template: "{{ now().day == 1 }}"
action:
  - service: wallbox_billing.send_invoice
    data: {}
mode: single
```

> **Tipp:** Die Uhrzeit (`08:00:00`) kann beliebig angepasst werden.

---

### Benachrichtigung nach Versand

Die Integration feuert nach jedem erfolgreichen Versand das Event `wallbox_billing_invoice_sent`. Diese Automation zeigt daraufhin eine Benachrichtigung an – egal ob der Versand durch die monatliche Automation oder durch manuellen Button-Klick ausgelöst wurde.

#### Variante A – Benachrichtigung in der HA-Oberfläche

```yaml
alias: "Wallbox Abrechnung – Benachrichtigung"
description: "Zeigt eine Meldung in Home Assistant an wenn die Abrechnung versendet wurde"
trigger:
  - platform: event
    event_type: wallbox_billing_invoice_sent
action:
  - service: notify.persistent_notification
    data:
      title: "Wallbox Abrechnung versendet"
      message: "Die monatliche Erstattungsanforderung wurde erfolgreich per E-Mail gesendet."
mode: single
```

#### Variante B – Push-Benachrichtigung auf das Smartphone

Voraussetzung: [Home Assistant Companion App](https://companion.home-assistant.io) auf dem Smartphone installiert.

```yaml
alias: "Wallbox Abrechnung – Push-Benachrichtigung"
description: "Sendet eine Push-Nachricht aufs Handy wenn die Abrechnung versendet wurde"
trigger:
  - platform: event
    event_type: wallbox_billing_invoice_sent
action:
  - service: notify.mobile_app_DEIN_GERÄTENAME
    data:
      title: "Wallbox Abrechnung versendet"
      message: "Die Erstattungsanforderung wurde erfolgreich per E-Mail gesendet."
mode: single
```

> Den genauen Gerätenamen findest du unter: **Einstellungen → Integrationen → Companion App → Benachrichtigungen**.
> Ersetze `DEIN_GERÄTENAME` durch den dort angezeigten Namen (z. B. `notify.mobile_app_iphone_von_max`).

---

## Button & manueller Versand

In Home Assistant erscheint nach der Einrichtung das Gerät **„Wallbox Abrechnung"** mit:

- **Button „Rechnung erstellen & senden"** – erstellt sofort die PDF und versendet sie
- 4 Sensoren mit aktuellen Abrechnungsdaten

> **Wichtig:** Nach jedem Versand (Button oder Automation) wird der aktuelle Zählerstand automatisch als neuer Startwert für den nächsten Abrechnungszeitraum gespeichert.

---

## Sensoren

| Sensor | Einheit | Beschreibung |
|--------|---------|-------------|
| `sensor.wallbox_abrechnung_verbrauch_seit_letzter_abrechnung` | kWh | Verbrauch seit letzter Abrechnung |
| `sensor.wallbox_abrechnung_kosten_seit_letzter_abrechnung` | EUR | Kosten seit letzter Abrechnung |
| `sensor.wallbox_abrechnung_letzte_abrechnung` | Datum | Datum der letzten Abrechnung |
| `sensor.wallbox_abrechnung_zahlerstand_letzte_abrechnung` | kWh | Zählerstand bei letzter Abrechnung |

---

## Einstellungen nachträglich ändern

Alle Einstellungen (Strompreis, Empfänger-E-Mail, SMTP-Daten, Name, Zählernummer) können jederzeit geändert werden:

**Einstellungen → Integrationen → Wallbox Abrechnung → Konfigurieren**

---

## ESPHome-Firmware

Die ESPHome-Konfiguration für den ESP32 liegt unter [`esphome/wallbox.yaml`](esphome/wallbox.yaml).

**Zählerstand manuell setzen** (z. B. nach Anbieterwechsel oder Gerätetausch):

In Home Assistant unter dem ESP32-Gerät → Zahl **„Wallbox Zählerstand setzen"** → gewünschten Wert eingeben.

---

*Entwickelt für Home Assistant mit ESPHome + Eltako DSZ15D über S0-Schnittstelle.*
