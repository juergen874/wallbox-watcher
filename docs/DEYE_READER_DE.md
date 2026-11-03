# 📖 Deye-Reader — Ausführliche Dokumentation (Deutsch)

`deye-reader` ist ein spezialisiertes Diagnose- und Monitoring-Werkzeug für **Deye Hybrid-Wechselrichter** (z. B. Deye SUN-12K-SG04LP3 / SG01HP3-Serie) über das **Solarman V5 Protokoll** und **Modbus TCP (Port 8899)**.

---

## 🎯 Zweck und Funktionsumfang

- **Echtzeit-Telemetrie:** Liest sekundengenau PV-Leistung (PV1, PV2, Gesamt), Netzbezug/Einspeisung, Hauslast sowie Batterie-Status (SoC %, Lade-/Entladeleistung, Spannung, Temperatur) aus.
- **Register-Decoder:** Umfassende Modbus-Register-Tabelle für Deye-Niedervolt- und Hochvolt-Dreiphasen-Hybrid-Wechselrichter.
- **Mehrere Implementierungen:**
  - `deye_reader.py`: Vollwertige Python-Implementierung mit `pysolarmanv5`.
  - `deye_reader_pocketpy.py`: Leichtgewichtige Variante für ressourcensparende Embedded-Systeme.
  - `deye_dashboard.html`: Lokales Web-Dashboard zur visuellen Echtzeit-Darstellung.

---

## ⚙️ Technische Parameter

| Parameter | Standardwert | Beschreibung |
| :--- | :--- | :--- |
| **Inverter IP** | `192.168.188.128` | Lokale IP-Adresse des Deye-Datenloggers |
| **Logger-Seriennummer** | `1109501211` | Solarman Data-Logger Seriennummer |
| **Port** | `8899` | Solarman V5 Modbus TCP Port |
| **Slave ID** | `1` | Modbus Slave-ID des Wechselrichters |
| **Timeout** | `4.0 s` | Socket-Timeout für Modbus-Anfragen |

---

## 📊 Wichtige Modbus-Register (Holding Registers)

| Register | Name / Bedeutung | Einheit / Skalierung |
| :--- | :--- | :--- |
| **588** | Batterie-Ladezustand (SoC) | `%` (1%) |
| **587** | Batterie-Temperatur | `0.1 °C` (Wert / 10 - 100) |
| **586** | Batteriespannung | `0.01 V` (Wert / 100) |
| **590** | Batterie-Leistung (Laden / Entladen) | `W` (vorzeichenbehaftet) |
| **672** | PV Gesamtleistung (PV Total Power) | `W` (1 W) |
| **676** | PV1 Leistung | `W` |
| **677** | PV2 Leistung | `W` |
| **625** | Netz-Gesamtleistung (Grid Total Power) | `W` (+ Bezug / - Einspeisung) |
| **653** | Gesamte Hauslast (Total Inverter Load) | `W` (1 W) |

---

## 🚀 Installation & Abhängigkeiten

```bash
# Im Projektverzeichnis:
pip install pysolarmanv5
```

---

## 💻 Verwendung

### 1. Einzelne Statusabfrage im Terminal
```bash
python3 deye-reader/deye_reader.py
```
Gibt eine formatierte Übersicht aller Wechselrichter-, PV-, Batterie- und Netzwerte auf der Konsole aus.

### 2. Kontinuierliche Überwachung
```bash
python3 deye-reader/deye_reader.py --watch
```

### 3. Diagnose einzelner Register
```bash
# Liest Register 588 (Batterie SoC) direkt aus:
python3 -c "from pysolarmanv5 import PySolarmanV5; c = PySolarmanV5('192.168.188.128', 1109501211, port=8899, mb_slave_id=1); print('SoC:', c.read_holding_registers(588, 1)[0], '%'); c.disconnect()"
```

---

## 🛡️ Best Practices & Fehlerbehebung

1. **Socket-Exhaustion vermeiden:**
   - Deye-Logger (Solarman-Chips) unterstützen maximal **1 bis 2 gleichzeitige TCP-Verbindungen** auf Port 8899.
   - Nach jeder Abfrage muss die Verbindung zwingend mit `client.disconnect()` geschlossen werden.
2. **`V5 Modbus EXCEPTION: AcknowledgeError`:**
   - Tritt auf, wenn der Wechselrichter kurzzeitig beschäftigt ist oder die falsche Slave-ID verwendet wird.
   - Lösung: Kurzer Retry nach 0,5 Sekunden und saubere Trennung des Sockets.
