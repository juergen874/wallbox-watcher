# 📖 Deye-Reader — Comprehensive Documentation (English)

`deye-reader` is a specialized diagnostic and monitoring tool for **Deye Hybrid Inverters** (such as Deye SUN-12K-SG04LP3 / SG01HP3 series) via the **Solarman V5 Protocol** and **Modbus TCP (Port 8899)**.

---

## 🎯 Purpose & Features

- **Real-time Telemetry:** Reads solar generation (PV1, PV2, Total), grid feed-in/consumption, total household load, and battery metrics (SoC %, charge/discharge power, voltage, temperature) with second-level precision.
- **Register Decoder:** Comprehensive Modbus register table for Deye low-voltage and high-voltage three-phase hybrid inverters.
- **Multiple Implementations:**
  - `deye_reader.py`: Full-featured Python implementation using `pysolarmanv5`.
  - `deye_reader_pocketpy.py`: Lightweight variant for resource-constrained embedded systems.
  - `deye_dashboard.html`: Local web dashboard for visual real-time metrics.

---

## ⚙️ Technical Specifications

| Parameter | Default Value | Description |
| :--- | :--- | :--- |
| **Inverter IP** | `192.168.188.128` | Local IP address of the Deye data logger |
| **Logger Serial Number** | `1109501211` | Solarman Data-Logger Serial Number |
| **Port** | `8899` | Solarman V5 Modbus TCP Port |
| **Slave ID** | `1` | Modbus Slave ID of the inverter |
| **Timeout** | `4.0 s` | Socket timeout for Modbus requests |

---

## 📊 Essential Modbus Registers (Holding Registers)

| Register | Name / Description | Unit / Scale |
| :--- | :--- | :--- |
| **588** | Battery State of Charge (SoC) | `%` (1%) |
| **587** | Battery Temperature | `0.1 °C` (Value / 10 - 100) |
| **586** | Battery Voltage | `0.01 V` (Value / 100) |
| **590** | Battery Charge / Discharge Power | `W` (Signed) |
| **672** | PV Total Power | `W` (1 W) |
| **676** | PV1 Power | `W` |
| **677** | PV2 Power | `W` |
| **625** | Grid Total Power | `W` (+ Import / - Export) |
| **653** | Total Inverter Load | `W` (1 W) |

---

## 🚀 Installation & Prerequisites

```bash
# In your project directory:
pip install pysolarmanv5
```

---

## 💻 Usage

### 1. One-off Status Query in Terminal
```bash
python3 deye-reader/deye_reader.py
```
Prints a structured console output showing inverter, PV, battery, and grid values.

### 2. Continuous Monitoring
```bash
python3 deye-reader/deye_reader.py --watch
```

### 3. Querying Specific Registers
```bash
# Query Register 588 (Battery SoC) directly:
python3 -c "from pysolarmanv5 import PySolarmanV5; c = PySolarmanV5('192.168.188.128', 1109501211, port=8899, mb_slave_id=1); print('SoC:', c.read_holding_registers(588, 1)[0], '%'); c.disconnect()"
```

---

## 🛡️ Best Practices & Troubleshooting

1. **Avoid Socket Exhaustion:**
   - Deye Solarman loggers support only **1 to 2 concurrent TCP connections** on port 8899.
   - Always invoke `client.disconnect()` immediately after executing register queries.
2. **`V5 Modbus EXCEPTION: AcknowledgeError`:**
   - Occurs when the inverter is temporarily busy or when using the wrong Slave ID.
   - Solution: Implement a brief retry after 0.5s and ensure strict connection closure.
