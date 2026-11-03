# ⚡ Deye Wallbox — Comprehensive Documentation (English)

`deye_wallbox.py` is a combined diagnostic, monitoring, and control module for the **Deye Smart EV Wallbox** (e.g., SUN-EVSE11K01 / SUN-EVSE22K01), which also interfaces with the **Deye Hybrid Inverter**.

---

## 🎯 Purpose & Features

- **Real-Time Telemetry:** Queries 3-phase charging power (L1, L2, L3 in Watts), total charging output, and the currently active charge limit.
- **Hardware Control via Modbus TCP:** Direct charging power throttling and start/stop control (0 to 22,000 W) via port 8899.
- **Solar & Inverter Correlation:** Directly correlates EV power demand with solar generation, battery SoC, and grid exchange of the Deye SUN-12K inverter.
- **Control Pilot & Cable Sensing:** Detects the physical connection status of the Type-2 charging cable using the Control Pilot (CP) state.

---

## ⚙️ Technical Specifications & Addressing

| Component | IP Address | Port / Protocol | Identification / Notes |
| :--- | :--- | :--- | :--- |
| **Deye Wallbox (HTTP Telemetry)** | `192.168.188.130` | `80 / HTTP` | Path: `/status.html` (Basic Auth: `admin:admin`) |
| **Deye Wallbox (Modbus TCP)** | `192.168.188.130` | `8899 / Solarman V5` | Serial: `1221073414`, **Slave ID: 3** |
| **Deye Inverter (Modbus TCP)** | `192.168.188.128` | `8899 / Solarman V5` | Serial: `1109501211`, **Slave ID: 1** |

---

## 📊 Modbus Register Map (Deye Wallbox, Slave ID: 3)

| Register | Type / FC | Description / Purpose | Range / Scale |
| :--- | :--- | :--- | :--- |
| **18** | Holding (FC03 / FC16) | **Active Power Limit** | `0` to `22000` Watts |
| **41, 42, 43** | Holding (FC03) | Mains Voltages (L1, L2, L3) | `0.1 V` (e.g. 2350 = 235.0 V) |
| **44, 45, 46** | Holding (FC03) | Output Voltages (L1, L2, L3) | `0.1 V` |
| **47, 48, 49** | Holding (FC03) | Output Currents (L1, L2, L3) | `0.1 A` (e.g. 96 = 9.6 A) |
| **57** | Holding (FC03) | **Control Pilot / Cable Connection Status** | `641` = Unplugged, `416` / `385` = Plugged |

> [!IMPORTANT]
> **Function Code FC16:** Setting Register 18 strictly requires Modbus Function Code 16 (`write_multiple_holding_registers`). Attempting to use FC06 (`write_holding_register`) will be rejected by the firmware with an `AcknowledgeError`.

---

## 💻 Usage

### 1. Querying Status in Terminal
```bash
python3 deye_wallbox.py
```
**Example Output:**
```text
============================================================
           DEYE WALLBOX & INVERTER STATUS                   
============================================================

⚡ WALLBOX (192.168.188.130):
   🔌 Total Power:      6.89 kW
   📊 L1: 2290 W | L2: 2300 W | L3: 2300 W
   🎯 Active Limit:     15.0 kW

☀️ INVERTER (192.168.188.128):
   Solar Generation:    4.50 kW
   Battery SoC:         78 %
   Grid Exchange:       -1.20 kW (Export)
```

### 2. Setting Charge Power Limit
```bash
# Pause / stop charging (0 W):
python3 deye_wallbox.py --set-power 0

# Set charging limit back to 15 kW:
python3 deye_wallbox.py --set-power 15000
```

### 3. Programmatic Usage in Python
```python
from pysolarmanv5 import PySolarmanV5

# Set limit to 11 kW:
client = PySolarmanV5("192.168.188.130", 1221073414, port=8899, mb_slave_id=3, timeout=5.0)
client.write_multiple_holding_registers(18, [11000])
client.disconnect()
```
