#!/data/data/com.termux/files/usr/bin/python3
"""
Deye Wallbox & Hybrid Inverter Monitor / Control Tool
Liest Live-Telemetrie der Deye EV Wallbox (192.168.188.130) und des Deye SUN-12K (192.168.188.128) aus.
"""

import sys
import os
import re
import time
import argparse
import urllib.request
import base64
from datetime import datetime

try:
    from pysolarmanv5 import PySolarmanV5
    HAS_SOLARMAN = True
except ImportError:
    HAS_SOLARMAN = False

WB_HOST = "192.168.188.130"
INV_HOST = "192.168.188.128"
INV_SERIAL = 1109501211
WB_SERIAL = 1221073414

def get_wallbox_telemetry():
    """Liest die aktuellen Statuswerte direkt aus der Deye-Wallbox aus."""
    url = f"http://{WB_HOST}/status.html"
    req = urllib.request.Request(url)
    auth = base64.b64encode(b"admin:admin").decode("utf-8")
    req.add_header("Authorization", f"Basic {auth}")

    data = {
        "online": False,
        "sn": "N/A",
        "power1": 0.0,
        "power2": 0.0,
        "power3": 0.0,
        "power_total": 0.0,
        "charge_limit_w": 0,
        "mode1": "Unbekannt",
        "mode2": "Unbekannt"
    }

    try:
        with urllib.request.urlopen(req, timeout=3) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
            data["online"] = True
            
            sn_m = re.search(r'var webdata_sn\s*=\s*"([^"]+)"', html)
            if sn_m:
                data["sn"] = sn_m.group(1).strip()

            p1_m = re.search(r'var webdata_power1\s*=\s*"([0-9.]+)"', html)
            p2_m = re.search(r'var webdata_power2\s*=\s*"([0-9.]+)"', html)
            p3_m = re.search(r'var webdata_power3\s*=\s*"([0-9.]+)"', html)
            ch_m = re.search(r'var webdata_charge\s*=\s*"([0-9]+)"', html)
            wm1_m = re.search(r'var webdata_wm1\s*=\s*"([0-9]+)"', html)
            wm2_m = re.search(r'var webdata_wm2\s*=\s*"([0-9]+)"', html)

            if p1_m: data["power1"] = float(p1_m.group(1))
            if p2_m: data["power2"] = float(p2_m.group(1))
            if p3_m: data["power3"] = float(p3_m.group(1))
            data["power_total"] = data["power1"] + data["power2"] + data["power3"]

            if ch_m: data["charge_limit_w"] = int(ch_m.group(1))
            if wm1_m:
                data["mode1"] = "Plug & Play" if wm1_m.group(1) == "0" else "Autorisierung / Termin"
            if wm2_m:
                data["mode2"] = "WLAN" if wm2_m.group(1) == "0" else "LoRa"
    except Exception as e:
        data["error"] = str(e)

    return data

def get_inverter_pv_summary():
    """Liest die PV-Erzeugung und den Batteriespeicher aus dem Deye SUN-12K."""
    if not HAS_SOLARMAN:
        return None
    try:
        client = PySolarmanV5(INV_HOST, INV_SERIAL, port=8899, mb_slave_id=1, verbose=False)
        regs_solar = client.read_holding_registers(529, 1)  # PV Ertrag heute kWh / 10
        regs_soc = client.read_holding_registers(588, 1)    # Battery SOC %
        regs_pv_w = client.read_holding_registers(672, 1)   # PV Power Total W
        regs_grid_w = client.read_holding_registers(625, 1) # Grid Power Total W
        return {
            "pv_power_w": regs_pv_w[0] if regs_pv_w else 0,
            "battery_soc": regs_soc[0] if regs_soc else 0,
            "grid_power_w": regs_grid_w[0] if regs_grid_w else 0
        }
    except Exception:
        return None

def display_status():
    wb = get_wallbox_telemetry()
    inv = get_inverter_pv_summary()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print("=" * 65)
    print(f"        ⚡ DEYE SMART EV WALLBOX MONITOR ({now})")
    print("=" * 65)
    
    if not wb["online"]:
        print(f"❌ Wallbox unter {WB_HOST} nicht erreichbar!")
        if "error" in wb:
            print(f"   Fehler: {wb['error']}")
        print("=" * 65)
        return

    print(f"Geräte-SN:       {wb['sn']}  (IP: {WB_HOST})")
    print(f"Betriebsmodus:   {wb['mode1']} | Funk: {wb['mode2']}")
    print(f"Leistungslimit:  {wb['charge_limit_w']} W ({wb['charge_limit_w']/1000:.1f} kW)")
    print("-" * 65)

    charging = wb["power_total"] > 50
    status_sym = "⚡ AKTIV WIRD GELADEN" if charging else "⏸️  STANDBY / PAUSIERT"
    print(f"Ladestatus:      {status_sym}")
    print(f"Gesamtleistung:  {wb['power_total']:.0f} W ({wb['power_total']/1000:.2f} kW)")
    print(f"   Phase 1 (L1): {wb['power1']:.0f} W")
    print(f"   Phase 2 (L2): {wb['power2']:.0f} W")
    print(f"   Phase 3 (L3): {wb['power3']:.0f} W")

    if inv:
        print("-" * 65)
        print("☀️  WECHSELRICHTER STATUS (Deye SUN-12K):")
        print(f"   PV-Leistung:      {inv['pv_power_w']} W")
        print(f"   Batteriespeicher: {inv['battery_soc']} %")
        grid_status = "Bezug" if inv['grid_power_w'] >= 0 else "Einspeisung"
        print(f"   Netzstatus:       {grid_status} ({abs(inv['grid_power_w'])} W)")

    print("=" * 65)

def main():
    parser = argparse.ArgumentParser(description="Deye EV Wallbox & Inverter Monitor Tool")
    parser.add_argument("-w", "--watch", type=int, nargs="?", const=3, help="Live-Überwachung alle N Sekunden (Standard: 3s)")
    parser.add_argument("--json", action="store_true", help="Ausgabe als JSON")
    args = parser.parse_args()

    if args.json:
        import json
        wb = get_wallbox_telemetry()
        wb["inverter"] = get_inverter_pv_summary()
        print(json.dumps(wb, indent=2))
        return

    if args.watch:
        interval = max(1, args.watch)
        print(f"Starte Live-Überwachung alle {interval}s (Abbruch mit Strg+C)...")
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
