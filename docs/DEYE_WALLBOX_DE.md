# ⚡ Deye Wallbox — Ausführliche Dokumentation (Deutsch)

`deye_wallbox.py` ist ein kombiniertes Diagnose-, Monitoring- und Regelungsmodul für die **Deye Smart EV Wallbox** (z. B. SUN-EVSE11K01 / SUN-EVSE22K01) und bindet zusätzlich den **Deye Hybrid-Wechselrichter** ein.

---

## 🎯 Zweck und Funktionsumfang

- **Echtzeit-Telemetrie:** Liest dreiphasige Ladeleistungen (L1, L2, L3 in Watt), Gesamtleistung und das momentan aktive Ladelimit aus.
- **Hardware-Steuerung via Modbus TCP:** Direkte Vorgabe der maximalen Ladeleistung (0 bis 22.000 W) über Port 8899.
- **PV- & Inverter-Integration:** Verknüpft die Wallbox-Leistung direkt mit PV-Erzeugung, Heimspeicher-SoC und Netzbezug des Deye SUN-12K.
- **Kabel- & CP-Erkennung:** Identifiziert den physischen Zustand des Typ-2-Ladekabels über den Control-Pilot-Status.

---

## ⚙️ Technische Spezifikationen & Adressierung

| Komponente | IP-Adresse | Port / Protokoll | Parameter / Identifikation |
| :--- | :--- | :--- | :--- |
| **Deye Wallbox (Web-Telemetrie)** | `192.168.188.130` | `80 / HTTP` | Status-URL: `/status.html` (Basic Auth: `admin:admin`) |
| **Deye Wallbox (Modbus TCP)** | `192.168.188.130` | `8899 / Solarman V5` | Seriennummer: `1221073414`, **Slave ID: 3** |
| **Deye Inverter (Modbus TCP)** | `192.168.188.128` | `8899 / Solarman V5` | Seriennummer: `1109501211`, **Slave ID: 1** |

---

## 📊 Modbus-Register der Deye-Wallbox (Slave ID: 3)

| Register | Typ / FC | Bedeutung / Funktion | Wertebereich |
| :--- | :--- | :--- | :--- |
| **18** | Holding (FC03 / FC16) | **Ladeleistungslimit (Active Power Limit)** | `0` bis `22000` Watt |
| **41, 42, 43** | Holding (FC03) | Netzspannungen Phase L1, L2, L3 | `0.1 V` (z. B. 2350 = 235.0 V) |
| **44, 45, 46** | Holding (FC03) | Phasenspannungen Ausgang | `0.1 V` |
| **47, 48, 49** | Holding (FC03) | Phasenströme L1, L2, L3 | `0.1 A` (z. B. 96 = 9.6 A) |
| **57** | Holding (FC03) | **Control Pilot / Kabelstatus (CP)** | `641` = Abgesteckt, `416` / `385` = Gesteckt |

> [!IMPORTANT]
> **Funktionscode FC16:** Das Setzen von Register 18 erfordert zwingend den Modbus-Funktionscode 16 (`write_multiple_holding_registers`), da FC06 von der Firmware mit einem `AcknowledgeError` abgelehnt wird.

---

## 💻 Verwendung

### 1. Statusabfrage im Terminal
```bash
python3 deye_wallbox.py
```
**Beispiel-Ausgabe:**
```text
============================================================
           DEYE WALLBOX & WECHSELRICHTER STATUS             
============================================================

⚡ WALLBOX (192.168.188.130):
   🔌 Gesamtleistung:   6.89 kW
   📊 L1: 2290 W | L2: 2300 W | L3: 2300 W
   🎯 Aktives Limit:    15.0 kW

☀️ WECHSELRICHTER (192.168.188.128):
   PV-Erzeugung:        4.50 kW
   Batterie-SoC:        78 %
   Netzbezug/-einspeisung: -1.20 kW
```

### 2. Ladelimit direkt einstellen
```bash
# Ladevorgang stoppen / pausieren (0 W):
python3 deye_wallbox.py --set-power 0

# Ladevorgang mit 15 kW freigeben:
python3 deye_wallbox.py --set-power 15000
```

### 3. Programmatische Nutzung in Python
```python
from pysolarmanv5 import PySolarmanV5

# Ladeleistung auf 11 kW drosseln:
client = PySolarmanV5("192.168.188.130", 1221073414, port=8899, mb_slave_id=3, timeout=5.0)
client.write_multiple_holding_registers(18, [11000])
client.disconnect()
```
