# Sichere Abrechnung und Korrekturen

## Vor dem Versand

`wallbox_billing.send_invoice` verlangt jetzt `confirmed_meter_reading`.
Dieser Wert muss direkt vom physischen Zähler abgelesen werden. Nicht einfach
den Sensorwert einsetzen, sonst wird die Prüfung wirkungslos. Mehr als 0,01 kWh
Abweichung, negative Verbräuche und nicht endliche Werte stoppen den Versand.
Bestehende Monatsautomationen und der Versandknopf senden ohne diesen Parameter
keine Rechnung mehr. Erst Ablesung prüfen, dann bewusst den Dienst ausführen.
Test- und Beispielversand bleiben E-Mails, sind also keine Vorschau ohne Versand.

Kalendertagswerte sind nur Zusatzinformationen, nicht die Erstattungsforderung.
Datenlücken und rückläufige Summen werden als unbekannt dargestellt. Kalibrierungen
können die Statistik verfälschen und müssen separat geprüft werden.

## Bereits gespeicherten Abrechnungsstart korrigieren

Unter Entwicklerwerkzeuge > Aktionen `wallbox_billing.correct_last_reading` wählen.
Der Dienst ist nur für Administratoren vorgesehen und sendet keine E-Mail.

1. Softwarezähler, physischen Zähler und den letzten eingereichten Beleg abgleichen.
2. Altwert und Attribut `billing_datetime` des Sensors „Zählerstand letzte
   Abrechnung“ notieren. Nur diese Daten sichern, keine SMTP-Konfiguration.
3. Den passenden `entry_id`, `expected_last_reading`, `expected_last_datetime`,
   `corrected_reading` und einen kurzen Belegverweis als `reason` angeben.
4. Der Dienst verweigert veraltete Altwerte und einen Start oberhalb des aktuellen
   Zählers. Er speichert vor dem Aktualisieren der Sensoren und protokolliert die
   Änderung dauerhaft im vorhandenen Store. Das Abrechnungsdatum bleibt erhalten.
5. Zählerstand und Verbrauch seit letzter Abrechnung anschließend prüfen.

Dieser Dienst verändert weder ESPHome noch Recorder und ist kein allgemeiner
Kalibrierungsdienst. Vor einer Hardwarekorrektur immer auch deren Wirkung auf die
Recorder-Summen prüfen. Niemals `.storage` oder die Datenbank von Hand überschreiben.
Eine Rücknahme erfolgt über denselben Dienst mit erneut geprüftem Istwert.

## Installieren und testen

Python 3.14 und `uv` werden vorausgesetzt. Alle Tests verwenden synthetische Daten;
SMTP, PDF-Ausgabe, Recorder-Abfrage und Persistenz werden an den Grenzen ersetzt.

```sh
uv venv --python 3.14 .venv
uv pip install --python .venv/bin/python -r requirements-test.txt
.venv/bin/python -m unittest discover -s tests -p test_billing_corrections.py -v
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/ruff check custom_components/wallbox_billing tests
.venv/bin/python -m compileall -q custom_components/wallbox_billing tests
docker run --rm -v "$PWD:/github/workspace" ghcr.io/home-assistant/hassfest
```

## Diagnose und Grenzen

Home Assistant > Einstellungen > System > Protokolle, Filter `wallbox_billing`.
INFO zeigt erfolgreiche Korrekturen; Validierungsfehler erscheinen direkt beim
Dienstaufruf. Für die Statistikabfrage kann vorübergehend über `logger.set_level`
`custom_components.wallbox_billing: debug` aktiviert werden. Keine Zugangsdaten
oder komplette Konfigurationen als Diagnoseausgabe teilen.

Die Bestätigung ersetzt keine physische Ablesung. Sie kann einen falsch
abgetippten, zum ebenfalls falsch gesetzten Softwarezähler passenden Wert nicht
erkennen. Bei Abweichungen Foto/Ziffern unabhängig prüfen. Ein Pulseingang kann
nicht nachträglich entscheiden, ob verlorene oder zusätzliche Impulse echt waren.
