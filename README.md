# ⚡ Deye Wallbox & Inverter Watcher Suite

[![Release](https://img.shields.io/badge/release-v1.2-blue.svg)](https://github.com/juergen874/wallbox-watcher/releases)
[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-green.svg)](https://www.python.org/)
[![Platform Termux/Linux](https://img.shields.io/badge/platform-Termux%20%7C%20Linux-orange.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Eine modulare Python-Suite zur Überwachung, Regelung und Fernsteuerung von:
- **Deye Smart EV Wallbox** (192.168.188.130 via Modbus TCP Port 8899, Slave 3 / Register 18 & Web-Telemetrie)
- **Deye SUN-12K-SG04LP3 Hybrid-Wechselrichter** (192.168.188.128 via Solarman V5 / Modbus TCP Port 8899, Slave 1)
- **Opel Corsa Electric** (SoC- & Ladeüberwachung über die offizielle Stellantis / Opel API)
- **Telegram Bot** mit interaktiven Inline-Buttons & Sonnenschein-Vorhersage für Zellertal

---

## 🚀 Hauptfunktionen

- ⚡ **Automatische Ladeerkennung:**  
  Erkennt in Echtzeit, sobald ein Fahrzeug an der Wallbox lädt (> 1.200 W), und sendet eine formatierte Push-Nachricht an Telegram.
- 🎯 **Dynamische Ladedauer-Berechnung (Ziel: 66% SoC):**  
  Berechnet anhand des aktuellen Fahrzeug-SoC und der Live-Ladeleistung die benötigte Energie (kWh), verbleibende Ladedauer und konkrete Ziel-Uhrzeit.
- 🔋 **Intelligente Heimspeicher-Überwachung:**  
  - **$\le$ 30% Speicher:** Automatische Empfehlung zum Pausieren des Ladevorgangs, um den Hausakku nicht tiefzuentladen.  
  - **$\ge$ 85% Speicher:** Automatische Empfehlung zum Starten des Ladens, um reichlich PV-Überschuss direkt ins Auto zu laden.
- 🌤️ **Sonnenschein-Vorhersage (Zellertal):**  
  Tägliche Abfrage der erwarteten Sonnenstunden der nächsten 3 Tage über die Open-Meteo-API.
- 🔘 **Direkte Hardware-Steuerung via Telegram:**  
  Echte Leistungsregelung der Wallbox über Modbus TCP (Port 8899, Slave 3, Register 18):
  - `[ ⏸️ Laden pausieren ]`: Setzt Ladelimit sofort auf `0 W` (stoppt Stromabgabe).
  - `[ ▶️ Laden starten ]`: Setzt Ladelimit auf `15.000 W` zurück (gibt Laden frei).
  - `[ 📊 Status aktualisieren ]`: Fragt Wallbox, Inverter, Fahrzeug und Wetter live ab.
- 🛡️ **Verbindungs- und API-Schutz:**  
  - Asynchrone Button-Quittierung (verhindert das Einfrieren der Telegram-App).
  - Automatischer Retry-Mechanismus und Socket-Bereinigung (`disconnect()`) für den Deye-Modbus-Port 8899.
  - 90-Sekunden In-Memory-Cache für Fahrzeugdaten zur Vermeidung von Opel-API-Drosselungen.

---

## 📦 Komponenten im Detail

### 1. `wallbox_watcher.py` (Hauptdienst)
Führt die 24/7-Überwachungsschleife und den Telegram-Long-Polling-Bot aus. Reagiert auf Button-Klicks, berechnet die Ladezeiten und schickt Push-Mitteilungen bei Ladebeginn/-ende oder Speicher-Schwellenwerten.

### 2. `corsa_status.py` (Opel Corsa Electric Integration)
- **Funktionsweise:** Fragt Akkustand (SoC %), Restreichweite, Kabel- und Ladestatus aller im MyOpel-Konto registrierten Fahrzeuge über die offizielle Stellantis Connected Car API ab.
- **Eigenständige Nutzung:**
  ```bash
  # Einmalige Statusabfrage beider Fahrzeuge:
  python3 corsa_status.py
  # Live-Überwachung im Terminal (alle 5 Minuten aktualisiert):
  python3 corsa_status.py --watch
  ```
- **Login & Authentifizierung:**
  Einmalig per `python3 corsa_status.py --login`. Unterstützt Tokens via `psa-token-helper.exe` oder PKCE-Webflow; Tokens werden automatisch per `refresh_token` im Hintergrund erneuert und lokal in `~/.corsa_tokens.json` gesichert.

### 3. `deye_wallbox.py` (Wallbox & Inverter Monitor)
- **Funktionsweise:** Verbindet Wallbox- und Wechselrichterdaten in einer gemeinsamen Konsolen-Übersicht.
  - **Wallbox (192.168.188.130):** Liest Ladeleistung pro Phase (L1, L2, L3), Gesamtleistung und aktives Ladelimit per HTTP-Status aus.
  - **Wechselrichter (192.168.188.128):** Fragt per Modbus TCP (Port 8899) PV-Erzeugung, Batteriespeicher-SoC und Netzbezug ab.
- **Eigenständige Nutzung:**
  ```bash
  # Einmaliger Status:
  python3 deye_wallbox.py
  # Live-Terminal-Monitor (alle 3 Sekunden aktualisiert):
  python3 deye_wallbox.py --watch 3
  # JSON-Export für Skripte oder Home Automation:
  python3 deye_wallbox.py --json
  ```

### 4. `deye-reader/` (Umfassender Deye SUN-12K Modbus Reader)
Enthält das vollwertige Telemetrie- und Webserver-Tool für den Deye-Hybrid-Wechselrichter:
- **`deye_reader.py`:** Liest über 50 Modbus-Register aus (Solar-Strings PV1/PV2, Batteriedaten, 3-Phasen-Netzmessungen, Hauslast, Temperaturen).
- **Web-Dashboard:** Integrierter lokaler HTTP-Server mit REST-API:
  ```bash
  python3 deye-reader/deye_reader.py --web 8080
  ```
- **`deye_reader_pocketpy.py`:** Extrem leichtgewichtige Version für MicroPython / PocketPy.

### 5. `start_watcher.sh`
Start- und Watchdog-Skript für Termux. Aktiviert `termux-wake-lock`, beendet alte Instanzen sauber und startet den Watcher als stabilen Hintergrund-Daemon.

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
chmod +x *.py *.sh deye-reader/*.py
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
- Dieses Repository enthält **keine privaten Tokens, Passwörter oder Chat-IDs**.
- Konfigurations- und Tokendateien (`.wallbox_telegram.json`, `.corsa_tokens.json`) sind in `.gitignore` eingetragen und verbleiben ausschließlich lokal auf Ihrem Gerät.

---

## 📄 Lizenz
MIT License - Frei verwendbar und anpassbar.
