#!/data/data/com.termux/files/usr/bin/python3
"""
Wallbox Watcher & Telegram Bot Service
Features:
- Live-Überwachung der Deye-Wallbox (192.168.188.130)
- Speicher-Überwachung (Deye SUN-12K):
    * Meldung bei >= 30% Speicher: "Laden sollte gestartet werden" (PV-Überschuss/Puffer da)
    * Meldung bei >= 85% Speicher: "Laden sollte pausiert werden" (oder Auto voll/Netzschonung)
- Interaktive Telegram-Buttons:
    [ ▶️ Laden starten ]  [ ⏸️ Laden pausieren ]
    [ 📊 Status aktualisieren ]
- Wettervorhersage für Zellertal (Sonnenschein-Erwartung der nächsten Tage via Open-Meteo)
- Schnelle asynchrone Button-Quittierung ohne Lade-Verzögerung
- Caching für Opel-Fahrzeugdaten
"""

import sys
import os
import time
import json
import re
import urllib.request
import urllib.parse
import base64
from datetime import datetime, timedelta
import threading

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

try:
    import corsa_status
    HAS_CORSA = True
except Exception:
    HAS_CORSA = False

try:
    import queue
    import pysolarmanv5.pysolarmanv5 as _psm
    _psm.Queue = queue.Queue
    from pysolarmanv5 import PySolarmanV5
    HAS_SOLARMAN = True
except ImportError:
    HAS_SOLARMAN = False

CONFIG_JSON_FILE = os.path.join(BASE_DIR, "config.json")
LEGACY_CONFIG_FILE = os.path.expanduser("~/.wallbox_telegram.json")

def load_app_config():
    cfg = {
        "bot_token": "",
        "chat_id": "",
        "wb_host": "192.168.188.130",
        "wb_serial": 1221073414,
        "inv_host": "192.168.188.128",
        "inv_serial": 1109501211,
        "target_soc": 66.0,
        "battery_netto_kwh": 46.0,
        "charging_efficiency": 0.90,
        "charging_phases": 1,
        "fixed_1p_power_w": 5000.0,
        "location_name": "Zellertal",
        "latitude": 49.65,
        "longitude": 8.14
    }
    # 1. Versuche config.json
    if os.path.exists(CONFIG_JSON_FILE):
        try:
            with open(CONFIG_JSON_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "telegram" in data:
                    cfg["bot_token"] = data["telegram"].get("bot_token", cfg["bot_token"])
                    cfg["chat_id"] = str(data["telegram"].get("chat_id", cfg["chat_id"]))
                if "wallbox" in data:
                    cfg["wb_host"] = data["wallbox"].get("host", cfg["wb_host"])
                    cfg["wb_serial"] = int(data["wallbox"].get("serial", cfg["wb_serial"]))
                if "inverter" in data:
                    cfg["inv_host"] = data["inverter"].get("host", cfg["inv_host"])
                    cfg["inv_serial"] = int(data["inverter"].get("serial", cfg["inv_serial"]))
                if "vehicle" in data:
                    cfg["vehicle_type"] = data["vehicle"].get("type", "none")
                    cfg["target_soc"] = float(data["vehicle"].get("target_soc", cfg["target_soc"]))
                    cfg["battery_netto_kwh"] = float(data["vehicle"].get("battery_netto_kwh", cfg["battery_netto_kwh"]))
                    cfg["charging_phases"] = int(data["vehicle"].get("charging_phases", cfg["charging_phases"]))
                    cfg["charging_efficiency"] = float(data["vehicle"].get("charging_efficiency", cfg["charging_efficiency"]))
                    cfg["fixed_1p_power_w"] = float(data["vehicle"].get("fixed_1p_power_w", cfg["fixed_1p_power_w"]))
                if "weather" in data:
                    cfg["location_name"] = data["weather"].get("location_name", cfg["location_name"])
                    cfg["latitude"] = float(data["weather"].get("latitude", cfg["latitude"]))
                    cfg["longitude"] = float(data["weather"].get("longitude", cfg["longitude"]))
        except Exception:
            pass

    # Fallback für Fahrzeugtyp
    if "vehicle_type" not in cfg:
        cfg["vehicle_type"] = "opel" if os.path.exists(os.path.expanduser("~/.corsa_tokens.json")) else "none"

    # 2. Fallback auf ~/.wallbox_telegram.json falls Bot-Token noch fehlt
    if not cfg["bot_token"] and os.path.exists(LEGACY_CONFIG_FILE):
        try:
            with open(LEGACY_CONFIG_FILE, "r", encoding="utf-8") as f:
                leg = json.load(f)
                cfg["bot_token"] = leg.get("bot_token", cfg["bot_token"])
                cfg["chat_id"] = str(leg.get("chat_id", cfg["chat_id"]))
        except Exception:
            pass

    return cfg

APP_CFG = load_app_config()
CONFIG_FILE = CONFIG_JSON_FILE if os.path.exists(CONFIG_JSON_FILE) else LEGACY_CONFIG_FILE

WB_HOST = APP_CFG["wb_host"]
WB_SERIAL = APP_CFG["wb_serial"]
INV_HOST = APP_CFG["inv_host"]
INV_SERIAL = APP_CFG["inv_serial"]
VEHICLE_TYPE = APP_CFG.get("vehicle_type", "none")
TARGET_SOC = APP_CFG["target_soc"]
BATTERY_NETTO_KWH = APP_CFG["battery_netto_kwh"]
CHARGING_EFFICIENCY = APP_CFG["charging_efficiency"]
CHARGING_PHASES = APP_CFG["charging_phases"]
FIXED_1P_CHARGING_POWER_W = APP_CFG["fixed_1p_power_w"]

WEATHER_LOCATION = APP_CFG["location_name"]
WEATHER_LAT = APP_CFG["latitude"]
WEATHER_LON = APP_CFG["longitude"]

# Caches
CARS_CACHE = {"data": [], "timestamp": 0}
CACHE_TTL_SECONDS = 300  # Opel-Cloud Abfrageintervall: alle 5 Minuten

WEATHER_CACHE = {"text": "", "timestamp": 0}
WEATHER_CACHE_TTL = 3600  # Stündlich aktualisieren

# Status-Flags für Speicherbenachrichtigungen (damit nicht im Sekundentakt gespammt wird)
NOTIFIED_SOC_30 = False
NOTIFIED_SOC_85 = False

# Merker für manuell pausierte Wallbox (wird bei Stecker-Trennung und Neu-Anstecken zurückgesetzt)
WALLBOX_PAUSED_BY_USER = False

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"bot_token": "", "chat_id": ""}

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)

def telegram_api(method, payload=None, timeout=10):
    cfg = load_config()
    token = cfg.get("bot_token")
    if not token:
        return None
    url = f"https://api.telegram.org/bot{token}/{method}"
    if payload:
        data = urllib.parse.urlencode(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data)
    else:
        req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None

def send_telegram(text, reply_markup=None):
    cfg = load_config()
    chat_id = cfg.get("chat_id")
    if not chat_id:
        return None
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    return telegram_api("sendMessage", payload)

def answer_callback(callback_query_id, text=None):
    payload = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
    return telegram_api("answerCallbackQuery", payload, timeout=5)

# Cache für Inverter-Daten (falls Port 8899 kurzzeitig belegt ist)
INVERTER_CACHE = {"data": {"pv_power_w": 0, "battery_soc": 0, "grid_power_w": 0, "online": False}, "timestamp": 0}

def get_inverter_data():
    """Liest PV-Leistung, Speicher-SoC und Netzstatus vom Deye SUN-12K mit Retry, Cache und sauberem Disconnect."""
    global INVERTER_CACHE
    if not HAS_SOLARMAN:
        return INVERTER_CACHE["data"]

    for attempt in range(2):
        client = None
        try:
            client = PySolarmanV5(INV_HOST, INV_SERIAL, port=8899, mb_slave_id=1, timeout=4.0, verbose=False)
            regs_soc = client.read_holding_registers(588, 1)    # Battery SOC %
            regs_pv = client.read_holding_registers(672, 4)     # PV1 Power (672), PV2 Power (673), PV3 (674), PV4 (675)
            regs_grid_w = client.read_holding_registers(625, 1) # Grid Power Total W
            
            # Wichtig: Sofort sauber trennen, damit Port 8899 nicht blockiert bleibt!
            client.disconnect()
            client = None

            total_pv_w = sum(regs_pv) if regs_pv else 0

            grid_raw = regs_grid_w[0] if regs_grid_w else 0
            if grid_raw > 32767:
                grid_raw -= 65536
            fresh_data = {
                "pv_power_w": total_pv_w,
                "battery_soc": regs_soc[0] if regs_soc else 0,
                "grid_power_w": grid_raw,
                "online": True
            }
            INVERTER_CACHE["data"] = fresh_data
            INVERTER_CACHE["timestamp"] = time.time()
            return fresh_data
        except Exception:
            if client:
                try:
                    client.disconnect()
                except Exception:
                    pass
            if attempt == 0:
                time.sleep(0.5)

    # Falls beide Versuche fehlschlagen: Behalte den letzten bekannten Cache für bis zu 10 Minuten
    if INVERTER_CACHE["timestamp"] > 0 and (time.time() - INVERTER_CACHE["timestamp"]) < 600:
        cached = dict(INVERTER_CACHE["data"])
        cached["online"] = True
        return cached

    return INVERTER_CACHE["data"]

def get_wallbox_telemetry():
    """Liest Live-Daten der Wallbox (192.168.188.130)."""
    url = f"http://{WB_HOST}/status.html"
    req = urllib.request.Request(url)
    auth = base64.b64encode(b"admin:admin").decode("utf-8")
    req.add_header("Authorization", f"Basic {auth}")
    data = {
        "online": False,
        "total_w": 0.0,
        "p1": 0.0,
        "p2": 0.0,
        "p3": 0.0,
        "limit_w": getattr(get_wallbox_telemetry, "_last_limit_w", 11000),
        "reg57": getattr(get_wallbox_telemetry, "_last_reg57", None),
        "plugged": getattr(get_wallbox_telemetry, "_last_plugged", True)
    }

    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=3.5) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
                p1 = float(re.search(r'var webdata_power1\s*=\s*"([0-9.]+)"', html).group(1))
                p2 = float(re.search(r'var webdata_power2\s*=\s*"([0-9.]+)"', html).group(1))
                p3 = float(re.search(r'var webdata_power3\s*=\s*"([0-9.]+)"', html).group(1))
                raw_w = p1 + p2 + p3
                real_total_w = raw_w if raw_w > 50 else 0.0

                data.update({
                    "online": True,
                    "total_w": real_total_w,
                    "p1": p1, "p2": p2, "p3": p3,
                })
                break
        except Exception:
            if attempt == 0:
                time.sleep(0.4)
            pass

    # Prüfe physischen Kabel-Status (Reg 57) und echtes Ladelimit (Reg 18) direkt per Modbus TCP
    if HAS_SOLARMAN and data["online"]:
        try:
            c = PySolarmanV5(WB_HOST, WB_SERIAL, port=8899, mb_slave_id=3, timeout=3.0, verbose=False)
            reg18 = c.read_holding_registers(18, 1)[0]
            reg57 = c.read_holding_registers(57, 1)[0]
            c.disconnect()
            data["limit_w"] = reg18
            data["reg57"] = reg57
            # Register 57:
            # 641 = Unplugged (Stecker gezogen / kein CP)
            # 385, 392 oder 416 = Plugged / Ready / Charging (Stecker gesteckt)
            data["plugged"] = (reg57 not in [0, 641])
            get_wallbox_telemetry._last_limit_w = reg18
            get_wallbox_telemetry._last_reg57 = reg57
            get_wallbox_telemetry._last_plugged = data["plugged"]
        except Exception:
            # Bei kurzem Modbus-Timeout oder wenn Leistung fließt:
            if data["total_w"] > 200:
                data["plugged"] = True
                data["reg57"] = 416
            else:
                data["plugged"] = getattr(get_wallbox_telemetry, "_last_plugged", True)
                data["reg57"] = getattr(get_wallbox_telemetry, "_last_reg57", None)
    return data

def get_corsa_status(force_refresh=False):
    """Liest Fahrzeugdaten beider Corsa-e ab (mit 90s In-Memory-Cache)."""
    global CARS_CACHE
    now = time.time()
    if not force_refresh and CARS_CACHE["data"] and (now - CARS_CACHE["timestamp"]) < CACHE_TTL_SECONDS:
        return CARS_CACHE["data"]

    res = []
    if not HAS_CORSA:
        return CARS_CACHE["data"]

    try:
        token = corsa_status.get_valid_token()
        vehicles = corsa_status.fetch_vehicles(token)
        if not vehicles:
            return CARS_CACHE["data"]

        for idx, v in enumerate(vehicles, 1):
            v_id = v.get("id")
            label = v.get("label") or f"Corsa #{idx}"
            st = corsa_status.fetch_vehicle_status(v_id, token)
            soc = None
            autonomy = None
            charging_st = "Unbekannt"
            rate = 0
            remaining_time = None
            updated_at = st.get("updatedAt", "")
            for e in st.get("energy", []):
                if e.get("type", "").lower() in ["electric", "battery"]:
                    soc = e.get("level")
                    autonomy = e.get("autonomy")
                    ch = e.get("charging", {})
                    plugged = ch.get("plugged", False)
                    charging_st = ch.get("status", "")
                    rate = ch.get("chargingRate", 0)
                    remaining_time = ch.get("remainingTime")
                    if e.get("updatedAt"):
                        updated_at = e.get("updatedAt")
            res.append({
                "id": v_id,
                "label": label,
                "soc": soc,
                "autonomy": autonomy,
                "plugged": plugged,
                "charging": charging_st,
                "rate": rate,
                "remaining_time": remaining_time,
                "updated_at": updated_at
            })
        if res:
            CARS_CACHE["data"] = res
            CARS_CACHE["timestamp"] = now
    except Exception:
        pass

    return CARS_CACHE["data"] if CARS_CACHE["data"] else res

def get_weather_condition_desc(code):
    """Übersetzt den WMO-Wettercode in prägnante Beschreibung und passendes Icon."""
    if code == 0:
        return "☀️", "Klar / Sonnig"
    elif code in [1, 2]:
        return "🌤️", "Heiter bis wolkig"
    elif code == 3:
        return "☁️", "Bedeckt / Wolkig"
    elif code in [45, 48]:
        return "🌫️", "Nebel / Hochnebel"
    elif code in [51, 53, 55]:
        return "🌧️", "Nieselregen"
    elif code in [61, 63, 65, 80, 81, 82]:
        return "🌧️", "Regen"
    elif code in [71, 73, 75, 85, 86]:
        return "🌨️", "Schneefall"
    elif code in [95, 96, 99]:
        return "⛈️", "Gewitter"
    return "⛅", "Teilweise wolkig"

def get_weather_forecast_zellertal():
    """Holt die Wetter- & Sonnenschein-Vorhersage für Zellertal via Open-Meteo."""
    global WEATHER_CACHE
    now = time.time()
    if WEATHER_CACHE["text"] and (now - WEATHER_CACHE["timestamp"]) < WEATHER_CACHE_TTL:
        return WEATHER_CACHE["text"]

    url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={WEATHER_LAT}&longitude={WEATHER_LON}"
        "&daily=weathercode,sunshine_duration,temperature_2m_max,precipitation_probability_max,cloud_cover_mean&timezone=Europe%2FBerlin"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "WallboxSolar/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode())
            daily = data.get("daily", {})
            times = daily.get("time", [])
            wcodes = daily.get("weathercode", [])
            sun_secs = daily.get("sunshine_duration", [])
            t_max = daily.get("temperature_2m_max", [])
            rain_probs = daily.get("precipitation_probability_max", [])
            clouds = daily.get("cloud_cover_mean", [])

            lines = [f"🌤️ *Wetter- & Solarprognose ({WEATHER_LOCATION}):*"]
            days_de = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
            
            # Die nächsten 3 Tage anzeigen
            for i, (d_str, wcode, s_sec, temp) in enumerate(zip(times[:3], wcodes[:3], sun_secs[:3], t_max[:3])):
                dt = datetime.strptime(d_str, "%Y-%m-%d")
                d_name = days_de[dt.weekday()]
                sun_hours = s_sec / 3600.0
                tag_label = "Heute" if dt.date() == datetime.now().date() else f"{d_name} ({dt.strftime('%d.%m.')})"
                icon, condition_txt = get_weather_condition_desc(wcode)
                
                detail_parts = [f"~*{sun_hours:.1f}h* Sonne", condition_txt]
                if i < len(clouds) and clouds[i] is not None:
                    detail_parts.append(f"☁️ {clouds[i]}% Bewölkung")
                detail_parts.append(f"max {temp:.0f}°C")
                if i < len(rain_probs) and rain_probs[i] and rain_probs[i] >= 20:
                    detail_parts.append(f"💧 {rain_probs[i]}%")

                lines.append(f"   {icon} *{tag_label}:* " + " | ".join(detail_parts))

            WEATHER_CACHE["text"] = "\n".join(lines)
            WEATHER_CACHE["timestamp"] = now
            return WEATHER_CACHE["text"]
    except Exception:
        return "🌤️ *Wetter Zellertal:* Sonnendaten aktuell nicht abrufbar"

def parse_opel_timestamp(iso_str):
    """Parst ISO-Zeitstempel von Opel (z.B. 2026-11-03T21:20:13Z) in lokale Zeit."""
    if not iso_str:
        return datetime.now()
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        # Konvertiere in lokale Zeitzone des Systems
        return dt.astimezone().replace(tzinfo=None)
    except Exception:
        return datetime.now()

def parse_iso_duration(dur_str):
    """Parst ISO 8601 Dauer wie PT3H55M in Minuten."""
    if not dur_str:
        return 0
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", dur_str)
    if not m:
        return 0
    h = int(m.group(1) or 0)
    mins = int(m.group(2) or 0)
    return h * 60 + mins

def calculate_time_to_66(current_soc, power_watts, base_time=None):
    if base_time is None:
        base_time = datetime.now()
    if power_watts <= 200 or current_soc is None:
        return None, None, 0
    if current_soc >= TARGET_SOC:
        return 0, base_time.strftime("%H:%M Uhr"), 0
    power_kw = (power_watts / 1000.0) * CHARGING_EFFICIENCY
    delta_soc = TARGET_SOC - current_soc
    needed_kwh = BATTERY_NETTO_KWH * (delta_soc / 100.0)
    hours = needed_kwh / power_kw
    minutes = int(round(hours * 60))
    target_time = base_time + timedelta(minutes=minutes)
    return minutes, target_time.strftime("%H:%M Uhr"), needed_kwh

def format_full_status_message(header="📊 *Aktueller Energie- & Ladestatus*", force_car_refresh=False):
    wb = get_wallbox_telemetry()
    inv = get_inverter_data()
    cars = get_corsa_status(force_refresh=force_car_refresh)
    weather = get_weather_forecast_zellertal()

    now_str = datetime.now().strftime("%H:%M:%S")
    lines = [f"{header} _({now_str})_\n"]

    # Wallbox
    if wb["online"]:
        if wb["total_w"] > 50:
            limit_str = f"{wb.get('limit_w', 11000)/1000:.1f} kW Limit"
            lines.append(f"⚡ *Ladeleistung:* 🟢 Lädt mit *{wb['total_w']/1000.0:.2f} kW* _({limit_str})_")
            lines.append(f"   _(L1: {wb['p1']:.0f} W | L2: {wb['p2']:.0f} W | L3: {wb['p3']:.0f} W)_")
        else:
            limit_kw = wb.get('limit_w', 11000) / 1000.0
            lines.append(f"⚡ *Wallbox:* ⏸️ Standby / Bereit (0 W | Limit: {limit_kw:.1f} kW)")
    else:
        lines.append("⚡ *Wallbox:* ❌ Offline")

    # Photovoltaik & Speicher
    lines.append("\n☀️ *Photovoltaik & Speicher:*")
    if inv["online"]:
        lines.append(f"   • PV-Leistung: *{inv['pv_power_w']} W*")
        lines.append(f"   • Heimspeicher: *{inv['battery_soc']} %*")
        grid_dir = "Bezug" if inv['grid_power_w'] >= 0 else "Einspeisung"
        lines.append(f"   • Netz: *{grid_dir} ({abs(inv['grid_power_w'])} W)*")
    else:
        lines.append("   • _Wechselrichter-Daten temporär nicht erreichbar_")

    # Fahrzeuge / Ladeinformation
    if VEHICLE_TYPE == "opel":
        lines.append("\n🚘 *Fahrzeuge (Opel Corsa Electric):*")
        active_charging_car = None
        if cars:
            for c in cars:
                plug = "🔌 Eingesteckt" if c["plugged"] else "⚪ Nicht eingesteckt"
                lines.append(f"   *{c['label']}:* {c['soc']}% (Restreichweite ~{c['autonomy']} km) | {plug}")
                if c["plugged"] and wb["total_w"] > 50:
                    active_charging_car = c
        else:
            lines.append("   • _Fahrzeugdaten werden geladen..._")

        # Prognose auf 66% & Langzeit (Opel-Daten)
        if active_charging_car and wb["total_w"] > 50:
            base_time = parse_opel_timestamp(active_charging_car.get("updated_at"))
            time_str_opel = base_time.strftime("%H:%M Uhr")
            mins, target_clock, needed_kwh = calculate_time_to_66(active_charging_car["soc"], wb["total_w"], base_time=base_time)
            lines.append(f"\n🎯 *Ladezeitprognose (Basis Opel: {time_str_opel}):*")
            if mins == 0:
                lines.append(f"   ✅ Ziel von {TARGET_SOC:.0f}% ist bereits erreicht!")
            elif mins:
                h, m = mins // 60, mins % 60
                dur_str = f"{h}h {m}m" if h > 0 else f"{m} Minuten"
                lines.append(f"   • Ziel {TARGET_SOC:.0f}%: ca. *{dur_str}* (um ~*{target_clock}*) | ~*{needed_kwh:.1f} kWh*")

            # Langzeitprognose bis 100% (aus Opel Bordcomputer-Daten)
            rem_str = active_charging_car.get("remaining_time")
            rate_val = active_charging_car.get("rate")
            rem_mins = parse_iso_duration(rem_str)
            if rem_mins > 0:
                rh, rm = rem_mins // 60, rem_mins % 60
                full_clock = (base_time + timedelta(minutes=rem_mins)).strftime("%H:%M Uhr")
                rate_info = f" ({rate_val} km/h)" if rate_val else ""
                lines.append(f"   • Voll (100%): ca. *{rh}h {rm}m*{rate_info} (um ~*{full_clock}*)")
    else:
        # Universeller Modus (ohne Fahrzeug-Cloud)
        if wb["total_w"] > 50:
            lines.append("\n🚘 *Fahrzeug:* 🟢 Lädt über Wallbox")
        elif wb.get("plugged"):
            lines.append("\n🚘 *Fahrzeug:* 🔌 Angesteckt (Bereit)")
        else:
            lines.append("\n🚘 *Fahrzeug:* ⚪ Nicht angesteckt")

    # Wetter / Sonnenschein
    lines.append(f"\n{weather}")

    return "\n".join(lines)

def get_inline_keyboard(current_watts=None):
    return {
        "inline_keyboard": [
            [
                {"text": "⏸️ Pause (0W)", "callback_data": "set_0"},
                {"text": "⚡ 4.1 kW", "callback_data": "set_4100"},
                {"text": "⚡ 7.4 kW", "callback_data": "set_7400"},
                {"text": "⚡ 11 kW", "callback_data": "set_11000"}
            ],
            [
                {"text": "➖ 1 kW", "callback_data": "step_down"},
                {"text": "➕ 1 kW", "callback_data": "step_up"},
                {"text": "📊 Status", "callback_data": "status"}
            ]
        ]
    }

def async_reply_status():
    wb = get_wallbox_telemetry()
    cur_w = wb.get("limit_w", 11000)
    msg = format_full_status_message("📊 *Aktualisierter Status*", force_car_refresh=True)
    send_telegram(msg, reply_markup=get_inline_keyboard(cur_w))


def set_wallbox_charge_power(watts):
    """Setzt die Ladeleistungsgrenze der Deye-Wallbox direkt per Modbus TCP Port 8899 (Slave 3, Reg 18)."""
    if not HAS_SOLARMAN:
        return False
    for attempt in range(2):
        try:
            c = PySolarmanV5(WB_HOST, WB_SERIAL, port=8899, mb_slave_id=3, timeout=5.0, verbose=False)
            c.write_multiple_holding_registers(18, [int(watts)])
            c.disconnect()
            get_wallbox_telemetry._last_limit_w = int(watts)
            return True
        except Exception as e:
            time.sleep(0.5)
    return False

def async_execute_set(watts, user="Jemand"):
    global WALLBOX_PAUSED_BY_USER
    watts = max(0, min(11000, int(watts)))
    ok = set_wallbox_charge_power(watts)
    time.sleep(1)
    if ok:
        WALLBOX_PAUSED_BY_USER = (watts == 0)
        if watts == 0:
            send_telegram(
                f"⏸️ *Ladung von {user} pausiert!*\n"
                "⚡ Ladelimit der Wallbox über Modbus auf *0 W* gesetzt.",
                reply_markup=get_inline_keyboard(watts)
            )
        else:
            send_telegram(
                f"⚡ *Ladelimit von {user} geändert!*\n"
                f"Ladeleistung auf *{watts/1000:.1f} kW* ({watts} W) eingestellt.",
                reply_markup=get_inline_keyboard(watts)
            )
    else:
        send_telegram(
            f"⚠️ *Fehler beim Einstellen von {watts} W durch {user}:* Keine Verbindung zur Wallbox.",
            reply_markup=get_inline_keyboard()
        )

def async_execute_step(delta_watts, user="Jemand"):
    wb = get_wallbox_telemetry()
    current_w = wb.get("limit_w", 11000)
    new_w = max(0, min(11000, current_w + delta_watts))
    async_execute_set(new_w, user=user)

def parse_set_power(text):
    """Parst Eingaben wie '/set 7.5', '/set 7500', '/set 11kw', 'set 6' etc."""
    m = re.search(r"^(?:/set|set)\s*([0-9]+(?:[\.,][0-9]+)?)\s*(kw|w)?", text, re.IGNORECASE)
    if not m:
        # Fallback falls jemand nur '/set' ohne Zahl schickt
        if text.strip() in ["/set", "set"]:
            return "HELP"
        return None
    val = float(m.group(1).replace(",", "."))
    unit = (m.group(2) or "").lower()

    if unit == "kw" or val <= 22:
        watts = int(round(val * 1000))
    else:
        watts = int(round(val))
    return watts

def handle_telegram_updates():
    """Hintergrund-Thread: Hört auf Button-Klicks und Befehle via Long-Polling."""
    offset = 0
    while True:
        try:
            params = {"timeout": 15, "offset": offset}
            res = telegram_api("getUpdates", params, timeout=25)
            if res and res.get("ok"):
                for update in res.get("result", []):
                    offset = update["update_id"] + 1

                    if "callback_query" in update:
                        cb = update["callback_query"]
                        cb_id = cb["id"]
                        data = cb.get("data", "")
                        user = cb.get("from", {}).get("first_name", "Jemand")
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] Button geklickt: {data} von {user}")

                        # Sofortige Quittierung!
                        if data == "status":
                            answer_callback(cb_id, "Werte werden aktualisiert...")
                            threading.Thread(target=async_reply_status, daemon=True).start()

                        elif data == "start":
                            answer_callback(cb_id, "Setze auf 11 kW...")
                            threading.Thread(target=async_execute_set, args=(11000, user), daemon=True).start()

                        elif data == "pause":
                            answer_callback(cb_id, "Pausiere Ladung...")
                            threading.Thread(target=async_execute_set, args=(0, user), daemon=True).start()

                        elif data.startswith("set_"):
                            try:
                                target_w = int(data.split("_")[1])
                                answer_callback(cb_id, f"Setze auf {target_w/1000:.1f} kW...")
                                threading.Thread(target=async_execute_set, args=(target_w, user), daemon=True).start()
                            except Exception as ex:
                                print(f"Fehler in set_: {ex}")

                        elif data == "step_up":
                            answer_callback(cb_id, "+1 kW...")
                            threading.Thread(target=async_execute_step, args=(1000, user), daemon=True).start()

                        elif data == "step_down":
                            answer_callback(cb_id, "-1 kW...")
                            threading.Thread(target=async_execute_step, args=(-1000, user), daemon=True).start()

                    elif "message" in update:
                        msg = update["message"]
                        text = msg.get("text", "").strip()
                        lower_text = text.lower()
                        user = msg.get("from", {}).get("first_name", "Jemand")

                        if lower_text in ["/start", "/help", "hilfe"]:
                            help_msg = (
                                "⚡ *Wallbox & Solar Watcher Hilfe*\n\n"
                                "Folgende Befehle stehen zur Verfügung:\n"
                                "• `/status` - Aktueller Status & Ladeübersicht\n"
                                "• `/set <kW>` - Ladeleistung einstellen (z.B. `/set 7.5` oder `/set 11`)\n"
                                "• `/set 0` - Ladevorgang pausieren (0 W)\n\n"
                                "Oder nutze direkt die Buttons unter jeder Meldung!"
                            )
                            send_telegram(help_msg, reply_markup=get_inline_keyboard())

                        elif lower_text.startswith("/set") or lower_text.startswith("set"):
                            parsed = parse_set_power(text)
                            if parsed == "HELP":
                                send_telegram(
                                    "ℹ️ *Benutzung von /set:*\n"
                                    "Gib die gewünschte Ladeleistung an, z.B.:\n"
                                    "• `/set 11` (11 kW)\n"
                                    "• `/set 7.5` (7.5 kW)\n"
                                    "• `/set 4.1` (4.1 kW / 6A)\n"
                                    "• `/set 0` (Pause)",
                                    reply_markup=get_inline_keyboard()
                                )
                            elif parsed is not None:
                                threading.Thread(target=async_execute_set, args=(parsed, user), daemon=True).start()
                            else:
                                send_telegram("⚠️ Ungültiger Wert für `/set`. Beispiel: `/set 8` oder `/set 7.5`")

                        elif lower_text in ["/status", "status", "ladung", "solar", "strom", "wetter"]:
                            threading.Thread(target=async_reply_status, daemon=True).start()

        except Exception:
            time.sleep(2)
        time.sleep(0.5)

def monitor_wallbox_and_battery_loop():
    """Überwacht die Wallbox und meldet Ladebeginn/Ende sowie Speicherstände (30% / 85%)."""
    global NOTIFIED_SOC_30, NOTIFIED_SOC_85
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Wallbox & Batterie Watcher aktiv. Überwache {WB_HOST} & {INV_HOST}...")
    try:
        # Einmalig im Hintergrund initial abrufen, damit Daten direkt im Cache sind
        threading.Thread(target=get_corsa_status, kwargs={"force_refresh": True}, daemon=True).start()
    except Exception:
        pass
    is_charging_session = False

    while True:
        try:
            wb = get_wallbox_telemetry()
            inv = get_inverter_data()
            power_w = wb["total_w"]
            bat_soc = inv["battery_soc"]

            # 1. Speicher-Schwellenwerte prüfen
            if inv["online"]:
                # <= 30% Meldung (Laden sollte pausiert werden, um Heimspeicher zu schonen)
                if bat_soc <= 30 and not NOTIFIED_SOC_30:
                    NOTIFIED_SOC_30 = True
                    msg = (
                        f"🔋 *Speicher bei nur {bat_soc}%!*\n\n"
                        "⚠️ *Empfehlung:* Das Laden des Fahrzeugs sollte pausiert werden, "
                        "um den Heimspeicher nicht weiter zu entleeren."
                    )
                    send_telegram(msg, reply_markup=get_inline_keyboard())

                elif bat_soc > 35:
                    NOTIFIED_SOC_30 = False  # Reset mit Hysterese

                # >= 85% Meldung (Laden sollte gestartet werden, Überschuss verbrauchen)
                if bat_soc >= 85 and not NOTIFIED_SOC_85:
                    NOTIFIED_SOC_85 = True
                    weather = get_weather_forecast_zellertal()
                    msg = (
                        f"🔋 *Speicher voll ({bat_soc}%)!*\n\n"
                        "💡 *Empfehlung:* Das Laden des Fahrzeugs sollte gestartet werden, "
                        "da reichlich Energie im Heimspeicher verfügbar ist!\n\n"
                        f"{weather}"
                    )
                    send_telegram(msg, reply_markup=get_inline_keyboard())

                elif bat_soc < 80:
                    NOTIFIED_SOC_85 = False  # Reset mit Hysterese

            # 2. Wallbox Ladebeginn / Ladeende
            if power_w > 1200 and not is_charging_session:
                is_charging_session = True
                print(f"\n⚡ Ladevorgang gestartet mit {power_w:.0f} W!")
                time.sleep(4)
                msg = format_full_status_message("⚡ *Neuer Ladevorgang erkannt!*", force_car_refresh=True)
                send_telegram(msg, reply_markup=get_inline_keyboard())

            elif power_w < 100 and is_charging_session:
                is_charging_session = False
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Ladevorgang beendet.")
                send_telegram("⏸️ *Ladevorgang an der Wallbox beendet / pausiert.*", reply_markup=get_inline_keyboard())

        except Exception:
            pass

        time.sleep(10)

def main():
    if "--setup" in sys.argv:
        try:
            import configure
            configure.main()
        except Exception:
            print("=== TELEGRAM BOT EINRICHTUNG ===")
            tok = input("Telegram Bot-Token: ").strip()
            cid = input("Chat-ID / Gruppen-ID: ").strip()
            save_config({"bot_token": tok, "chat_id": cid})
            print("✓ Gespeichert.")
            send_telegram("👋 *Wallbox Watcher eingerichtet!*", reply_markup=get_inline_keyboard())
        sys.exit(0)

    # 1. Telegram Bot Polling Thread
    bot_thread = threading.Thread(target=handle_telegram_updates, daemon=True)
    bot_thread.start()

    # 2. Haupt-Überwachungsschleife
    monitor_wallbox_and_battery_loop()

if __name__ == "__main__":
    main()
