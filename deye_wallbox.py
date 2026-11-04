#!/data/data/com.termux/files/usr/bin/python3
"""
Deye Smart EV Wallbox - Reiner Modbus TCP Monitor
Liest sämtliche Telemetrie- und Betriebsdaten direkt per Modbus TCP (Port 8899, Slave 3).
Kein HTTP / Web-Scraping.
"""

import sys
import time
import argparse
from datetime import datetime

try:
    from pysolarmanv5 import PySolarmanV5
except ImportError:
    print("Fehler: 'pysolarmanv5' ist nicht installiert. Bitte mit 'pip install pysolarmanv5' installieren.")
    sys.exit(1)

WB_HOST = "192.168.188.130"
WB_PORT = 8899
WB_SERIAL = 1221073414
WB_SLAVE_ID = 3

CP_STATES = {
    641: "Ausgesteckt / Getrennt (CP offen)",
    385: "Verbunden / Standby (Bereit)",
    392: "Verbunden / Standby (Bereit)",
    416: "⚡ Aktiv wird geladen",
}

def get_modbus_telemetry():
    """Liest Live-Telemetriedaten der Wallbox über Modbus TCP."""
    data = {
        "online": False,
        "sn": "Unbekannt",
        "power1_w": 0.0,
        "power2_w": 0.0,
        "power3_w": 0.0,
        "total_w": 0.0,
        "voltage1_v": 0.0,
        "voltage2_v": 0.0,
        "voltage3_v": 0.0,
        "current1_a": 0.0,
        "current2_a": 0.0,
        "current3_a": 0.0,
        "temp_c": 0.0,
        "charge_limit_w": 0,
        "max_limit_w": 0,
        "cp_code": 0,
        "cp_status": "Unbekannt",
        "relais_closed": False,
        "remote_control": False,
    }

    try:
        c = PySolarmanV5(WB_HOST, WB_SERIAL, port=WB_PORT, mb_slave_id=WB_SLAVE_ID, timeout=3.0, verbose=False)
        
        # 1. Seriennummer (Holding 2..7)
        h0_8 = c.read_holding_registers(0, 8)
        sn_bytes = bytearray()
        for r in h0_8[2:8]:
            sn_bytes.extend(r.to_bytes(2, "big"))
        sn = sn_bytes.decode("ascii", errors="ignore").strip()

        # 2. Ladelimit & Fernsteuerung (Holding 18..19)
        h18_19 = c.read_holding_registers(18, 2)
        limit_w = h18_19[0]
        remote_ctrl = bool(h18_19[1])

        # 3. Temperatur, Leistung (38-40), Spannung (41-43) (Holding 34..43)
        h34_43 = c.read_holding_registers(34, 10)
        temp_c = h34_43[1] / 10.0
        p1 = float(h34_43[4] * 10)
        p2 = float(h34_43[5] * 10)
        p3 = float(h34_43[6] * 10)
        u1 = h34_43[7] / 10.0
        u2 = h34_43[8] / 10.0
        u3 = h34_43[9] / 10.0

        # 4. Phasenströme (Holding 47..49)
        h47_49 = c.read_holding_registers(47, 3)
        i1 = h47_49[0] / 10.0
        i2 = h47_49[1] / 10.0
        i3 = h47_49[2] / 10.0

        # 5. Maximallimit, CP-Status, Relais (Holding 56..58)
        h56_58 = c.read_holding_registers(56, 3)
        max_limit_w = h56_58[0]
        cp_code = h56_58[1]
        relais = bool(h56_58[2])

        c.disconnect()

        total_w = p1 + p2 + p3

        data.update({
            "online": True,
            "sn": sn,
            "power1_w": p1,
            "power2_w": p2,
            "power3_w": p3,
            "total_w": total_w,
            "voltage1_v": u1,
            "voltage2_v": u2,
            "voltage3_v": u3,
            "current1_a": i1,
            "current2_a": i2,
            "current3_a": i3,
            "temp_c": temp_c,
            "charge_limit_w": limit_w,
            "max_limit_w": max_limit_w,
            "cp_code": cp_code,
            "cp_status": CP_STATES.get(cp_code, f"Statuscode {cp_code}"),
            "relais_closed": relais,
            "remote_control": remote_ctrl,
        })
    except Exception as e:
        data["error"] = str(e)

    return data

def display_status():
    data = get_modbus_telemetry()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print("=" * 65)
    print(f"        ⚡ DEYE SMART EV WALLBOX - MODBUS TELEMETRIE ({now})")
    print("=" * 65)

    if not data["online"]:
        print(f"❌ Wallbox unter {WB_HOST}:{WB_PORT} nicht erreichbar!")
        if "error" in data:
            print(f"   Fehler: {data['error']}")
        print("=" * 65)
        return

    relais_str = "Geschlossen (Aktiv)" if data["relais_closed"] else "Geöffnet (Aus)"
    remote_str = "Aktiviert (Modbus)" if data["remote_control"] else "Lokal"

    print(f"Geräte-SN:       {data['sn']}  (IP: {WB_HOST}, Slave: {WB_SLAVE_ID})")
    print(f"Ladelimit:       {data['charge_limit_w']} W (Max: {data['max_limit_w']} W)")
    print(f"Fernsteuerung:   {remote_str} | Relais: {relais_str}")
    print(f"Temperatur:      {data['temp_c']:.1f} °C")
    print(f"Kabel / Status:  {data['cp_status']} (Reg 57 = {data['cp_code']})")
    print("-" * 65)

    print(f"Gesamtleistung:  {data['total_w']:.0f} W ({data['total_w']/1000:.2f} kW)")
    print(f"  Phase 1 (L1):  {data['power1_w']:>6.0f} W  |  {data['voltage1_v']:>5.1f} V  |  {data['current1_a']:>4.1f} A")
    print(f"  Phase 2 (L2):  {data['power2_w']:>6.0f} W  |  {data['voltage2_v']:>5.1f} V  |  {data['current2_a']:>4.1f} A")
    print(f"  Phase 3 (L3):  {data['power3_w']:>6.0f} W  |  {data['voltage3_v']:>5.1f} V  |  {data['current3_a']:>4.1f} A")
    print("=" * 65)

def main():
    parser = argparse.ArgumentParser(description="Deye EV Wallbox Reiner Modbus Monitor")
    parser.add_argument("-w", "--watch", type=int, nargs="?", const=3, help="Live-Überwachung alle N Sekunden (Standard: 3s)")
    parser.add_argument("--json", action="store_true", help="Ausgabe als JSON")
    args = parser.parse_args()

    if args.json:
        import json
        data = get_modbus_telemetry()
        print(json.dumps(data, indent=2))
        return

    if args.watch:
        interval = max(1, args.watch)
        print(f"Starte Live-Modbus-Überwachung alle {interval}s (Abbruch mit Strg+C)...")
        try:
            while True:
                display_status()
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\nÜberwachung beendet.")
    else:
        display_status()

if __name__ == "__main__":
    main()
