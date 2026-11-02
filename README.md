# ⚡ Deye Wallbox & Inverter Watcher

Automatischer Überwachungs- und Benachrichtigungsdienst für:
- **Deye Smart EV Wallbox** (192.168.188.130)
- **Deye SUN-12K-SG04LP3 Hybrid-Wechselrichter** (192.168.188.128 via Modbus TCP Port 8899)
- **Opel Corsa Electric** (Batteriestatus via Stellantis / Opel API)
- **Telegram Bot** mit interaktiven Inline-Buttons & Sonnenschein-Vorhersage (Zellertal)

---

## 🚀 Funktionen

- ⚡ **Automatische Ladeerkennung:** Sobald ein Fahrzeug an der Wallbox lädt (> 1.200 W), schickt der Bot eine Benachrichtigung.
- 🎯 **Ladedauer-Berechnung:** Berechnet dynamisch die verbleibende Zeit und Uhrzeit bis **66% SoC** des Corsa-e.
- 🔋 **Heimspeicher-Überwachung:**
  - Meldung bei $\le$ 30% Speicherstand (*Laden pausieren, um Heimspeicher zu schonen*).
  - Meldung bei $\ge$ 85% Speicherstand (*Laden starten, PV-Überschuss nutzen*).
- 🌤️ **Wetter-Integration:** Liefert täglich die erwarteten Sonnenstunden für Zellertal (via Open-Meteo).
- 🔘 **Telegram-Buttons:** `[ ▶️ Laden starten ]`, `[ ⏸️ Laden pausieren ]`, `[ 📊 Status aktualisieren ]`.

---

## 📦 Dateien

- `wallbox_watcher.py`: Hauptdienst mit Telegram Long-Polling und Überwachungsschleife.
- `deye_wallbox.py`: Modbus- & HTTP-Telemetrie-Modul für die Deye Wallbox & Wechselrichter.
- `corsa_status.py`: Abfrageskript für den Opel Corsa Electric SoC.
- `start_watcher.sh`: Startskript für den dauerhaften Betrieb unter Termux.

---

## 🔒 Datenschutz & Sicherheit
Dieses Repository enthält **keine privaten API-Tokens oder Anmeldedaten**.
Konfigurationsdateien (`.wallbox_telegram.json`, `.corsa_tokens.json`) werden über `.gitignore` ausgeschlossen und verbleiben ausschließlich lokal auf dem Gerät.
