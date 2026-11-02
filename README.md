# ⚡ Deye Wallbox & Inverter Watcher (v1.0)

[![Release](https://img.shields.io/badge/release-v1.0-blue.svg)](https://github.com/juergen874/wallbox-watcher/releases)
[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-green.svg)](https://www.python.org/)
[![Platform Termux/Linux](https://img.shields.io/badge/platform-Termux%20%7C%20Linux-orange.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Ein leichtgewichtiger, autonomer Überwachungs- und Benachrichtigungsdienst für das Heimnetzwerk (z. B. auf einem Termux-Server oder Raspberry Pi):
- **Deye Smart EV Wallbox** (192.168.188.130)
- **Deye SUN-12K-SG04LP3 Hybrid-Wechselrichter** (192.168.188.128 via Solarman V5 / Modbus TCP Port 8899)
- **Opel Corsa Electric** (SoC- & Ladestatus über die offizielle Stellantis / Opel API)
- **Interaktiver Telegram Bot** mit Inline-Buttons und Wetterprognose (Zellertal)

---

## 🚀 Hauptfunktionen (v1.0)

- ⚡ **Automatische Ladeerkennung:**  
  Erkennt in Echtzeit, sobald ein Fahrzeug an der Wallbox lädt (> 1.200 W), und sendet eine formatierte Push-Nachricht an Telegram.
- 🎯 **Dynamische Ladedauer-Berechnung (Ziel: 66% SoC):**  
  Berechnet anhand des Fahrzeug-SoC und der aktuellen Ladeleistung die benötigte Energiemenge (kWh), Restdauer und die voraussichtliche Uhrzeit.
- 🔋 **Intelligente Speicher-Überwachung:**  
  - **$\le$ 30% Speicher:** Empfehlung zum Pausieren des Ladevorgangs, um den Heimspeicher nicht unnötig zu leeren.  
  - **$\ge$ 85% Speicher:** Empfehlung zum Starten des Ladens, um reichlich PV-Überschuss direkt ins Auto zu laden.
- 🌤️ **Sonnenschein-Vorhersage (Zellertal):**  
  Tägliche Abfrage der erwarteten Sonnenstunden der nächsten 3 Tage über die Open-Meteo-API.
- 🔘 **Interaktive Telegram-Buttons:**  
  Direkte Steuerung und Statusabfrage via Inline-Tastatur:
  ```text
  [ ▶️ Laden starten ]  [ ⏸️ Laden pausieren ]
  [ 📊 Status aktualisieren ]
  ```
- 🛡️ **Verbindungs- und API-Schutz:**  
  - Asynchrone Button-Quittierung (kein Hängen von Telegram).
  - Automatischer Retry-Mechanismus und Socket-Bereinigung (`disconnect()`) für den Deye-Modbus-Port 8899.
  - 90-Sekunden In-Memory-Cache für Fahrzeugdaten zur Vermeidung von Opel-API-Drosselungen.

---

## 📦 Komponenten & Dateien

| Datei | Beschreibung |
|---|---|
| `wallbox_watcher.py` | Hauptdienst (Telegram Long-Polling, Überwachungsschleife, Berechnungen) |
| `deye_wallbox.py` | Modul zum Auslesen der Wallbox-Telemetrie und Wechselrichterdaten |
| `corsa_status.py` | Opel Connect / PSA Cloud-Client für Fahrzeug-SoC und Ladestatus |
| `start_watcher.sh` | Start- und Watchdog-Skript für den 24/7-Betrieb unter Termux |

---

## 🛠️ Voraussetzungen & Installation

### 1. Abhängigkeiten installieren
```bash
pip install requests pysolarmanv5
```

### 2. Repository klonen
```bash
git clone https://github.com/juergen874/wallbox-watcher.git
cd wallbox-watcher
chmod +x *.py *.sh
```

### 3. Telegram-Bot einrichten
```bash
python3 wallbox_watcher.py --setup
```
*(Fragt interaktiv nach Bot-Token und Chat-/Gruppen-ID und sendet eine Bestätigung).*

### 4. Dienst starten
```bash
./start_watcher.sh
```

---

## 🔒 Sicherheitshinweise
- Dieses Repository enthält **keine privaten Tokens oder Passwörter**.
- Konfigurations- und Tokendateien (`.wallbox_telegram.json`, `.corsa_tokens.json`) sind in `.gitignore` eingetragen und verbleiben ausschließlich lokal auf Ihrem Gerät.

---

## 📄 Lizenz
MIT License - Frei verwendbar und anpassbar.
