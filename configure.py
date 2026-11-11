#!/usr/bin/env python3
"""
Interaktiver Konfigurations-Assistent für die Deye Wallbox & Inverter Watcher Suite
Erstellt oder bearbeitet 'config.json' und synchronisiert auf Wunsch ~/.wallbox_telegram.json.
"""

import os
import sys
import json
import urllib.request
import urllib.parse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")
CONFIG_EXAMPLE = os.path.join(SCRIPT_DIR, "config.example.json")
LEGACY_TELEGRAM_PATH = os.path.expanduser("~/.wallbox_telegram.json")
LEGACY_CORSA_TOKENS = os.path.expanduser("~/.corsa_tokens.json")

DEFAULT_CONFIG = {
    "telegram": {
        "bot_token": "",
        "chat_id": ""
    },
    "wallbox": {
        "host": "192.168.188.130",
        "serial": 1221073414,
        "port": 8899,
        "slave_id": 3
    },
    "inverter": {
        "host": "192.168.188.128",
        "serial": 1109501211,
        "port": 8899,
        "slave_id": 1
    },
    "vehicle": {
        "type": "none",
        "target_soc": 66.0,
        "battery_netto_kwh": 46.0,
        "charging_efficiency": 0.90
    },
    "weather": {
        "location_name": "Zellertal",
        "latitude": 49.65,
        "longitude": 8.14
    }
}

def load_existing_config():
    """Lädt bestehende Konfiguration oder migriert aus Legacy-Dateien."""
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))

    # 1. config.json im Projektordner laden
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
                for section in ("telegram", "wallbox", "inverter", "vehicle", "weather"):
                    if section in saved and isinstance(saved[section], dict):
                        cfg[section].update(saved[section])
        except Exception as e:
            print(f"⚠️ Hinweis: Fehler beim Laden von config.json: {e}")

    # 2. Falls Telegram-Daten noch leer sind: aus Legacy ~/.wallbox_telegram.json übernehmen
    if (not cfg["telegram"]["bot_token"] or not cfg["telegram"]["chat_id"]) and os.path.exists(LEGACY_TELEGRAM_PATH):
        try:
            with open(LEGACY_TELEGRAM_PATH, "r", encoding="utf-8") as f:
                old_tg = json.load(f)
                if not cfg["telegram"]["bot_token"]:
                    cfg["telegram"]["bot_token"] = old_tg.get("bot_token", "")
                if not cfg["telegram"]["chat_id"]:
                    cfg["telegram"]["chat_id"] = str(old_tg.get("chat_id", ""))
        except Exception:
            pass

    return cfg

def prompt(label, default_val, help_text=None, val_type=str):
    """
    Fragt einen Wert ab:
    - Zeigt eine Hilfebeschreibung / Erklärung, wo man die Information herbekommt
    - Zeigt den aktuellen / bisherigen Wert an
    - Behält bei leerer Eingabe (nur [ENTER]) exakt den bisherigen Wert bei
    """
    if help_text:
        print(f"\033[0;36m💡 {help_text}\033[0m")

    val_str = "" if default_val is None else str(default_val)
    if val_str:
        prompt_text = f"\033[1;37m{label}\033[0m (Aktuell: \033[1;32m{val_str}\033[0m): "
    else:
        prompt_text = f"\033[1;37m{label}\033[0m (Aktuell: \033[1;33mkein Wert gesetzt\033[0m): "

    res = input(prompt_text).strip()

    if not res:
        return default_val

    if val_type == int:
        try:
            return int(res)
        except ValueError:
            print(f"⚠️ Ungültige Zahl! Behalte bisherigen Wert: {default_val}")
            return default_val
    elif val_type == float:
        try:
            return float(res)
        except ValueError:
            print(f"⚠️ Ungültige Dezimalzahl! Behalte bisherigen Wert: {default_val}")
            return default_val
    return res

def geocode_location(place_name):
    """Ermittelt automatisch Breitengrad & Längengrad für einen Ortsnamen."""
    if not place_name or not place_name.strip():
        return None
    name = place_name.strip()
    # 1. Open-Meteo Geocoding
    try:
        url = f"https://geocoding-api.open-meteo.com/v1/search?name={urllib.parse.quote(name)}&count=1&language=de&format=json"
        req = urllib.request.Request(url, headers={"User-Agent": "WallboxSetup/1.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read().decode())
            if "results" in data and len(data["results"]) > 0:
                res = data["results"][0]
                return float(res["latitude"]), float(res["longitude"]), res.get("name", name)
    except Exception:
        pass

    # 2. Fallback: OpenStreetMap Nominatim
    try:
        url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(name)}&format=json&limit=1"
        req = urllib.request.Request(url, headers={"User-Agent": "WallboxSetup/1.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read().decode())
            if len(data) > 0:
                return float(data[0]["lat"]), float(data[0]["lon"]), data[0].get("name", name)
    except Exception:
        pass

    return None

def is_host_reachable(host, port=8899, timeout=0.5):
    """Prüft blitzschnell, ob der Host im aktuellen WLAN erreichbar ist."""
    if not host:
        return False
    import socket
    try:
        s = socket.create_connection((host, port), timeout=timeout)
        s.close()
        return True
    except Exception:
        return False

def detect_logger_serial(host):
    """
    Versucht die 10-stellige Seriennummer des Deye/Solarman WLAN-Sticks
    vollautomatisch via UDP-Broadcast/Unicast (Port 48899) abzufragen.
    """
    if not host or not is_host_reachable(host, port=8899, timeout=0.4):
        return None
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(1.0)
    try:
        sock.sendto(b"HF-A11ASSISTHREAD", (host, 48899))
        data, _ = sock.recvfrom(1024)
        msg = data.decode("latin1", errors="ignore").strip()
        parts = msg.replace(",", " ").replace(";", " ").split()
        for p in parts:
            p_clean = p.strip()
            if p_clean.isdigit() and len(p_clean) in (10, 11):
                return int(p_clean)
    except Exception:
        pass
    finally:
        sock.close()
    return None

def scan_modbus_slave_id(host, serial, port=8899, candidates=(1, 3, 2, 4)):
    """
    Testet Kandidaten-Slave-IDs auf Antwort via Modbus RTU over TCP.
    Gibt die erste erfolgreich antwortende Slave-ID zurück.
    """
    if not host or not serial or not is_host_reachable(host, port=port, timeout=0.4):
        return None
    try:
        import queue
        import pysolarmanv5.pysolarmanv5 as _psm
        _psm.Queue = queue.Queue
        from pysolarmanv5 import PySolarmanV5
    except Exception:
        return None

    for slave_id in candidates:
        try:
            client = PySolarmanV5(host, int(serial), port=port, mb_slave_id=slave_id, timeout=1.0, verbose=False)
            res = client.read_holding_registers(register_addr=3, quantity=1)
            if res is not None:
                return slave_id
        except Exception:
            continue
    return None

def test_telegram(token, chat_id):
    if not token or not chat_id:
        return False
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": "⚡ *Wallbox Watcher Konfigurations-Test erfolgreich!*",
            "parse_mode": "Markdown"
        }).encode("utf-8")
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=8) as resp:
            res = json.loads(resp.read().decode())
            return res.get("ok", False)
    except Exception as e:
        print(f"Telegram-Test fehlgeschlagen: {e}")
        return False

def main():
    print("\033[1;36m=================================================================\033[0m")
    print("\033[1;32m      ⚡ Deye Wallbox Watcher - Konfigurations-Assistent        \033[0m")
    print("\033[1;36m=================================================================\033[0m")
    print("👉 Drücke bei jedem Feld einfach \033[1;37m[ENTER]\033[0m, um den bestehenden Wert beizubehalten.\n")

    cfg = load_existing_config()

    print("\033[1;33m--- 1. Telegram Benachrichtigungen ---\033[0m")
    cfg["telegram"]["bot_token"] = prompt(
        "Telegram Bot Token",
        cfg["telegram"]["bot_token"],
        help_text="Erstellen über Telegram mit @BotFather -> /newbot. Sieht aus wie: 123456789:AAH..."
    )
    cfg["telegram"]["chat_id"] = str(prompt(
        "Telegram Chat- / Gruppen-ID",
        cfg["telegram"]["chat_id"],
        help_text="Ermitteln: Sende /start an deinen Bot oder @userinfobot (z.B. 123456789 oder negativ für Gruppen -100...)"
    ))

    print("\n\033[1;33m--- 2. Deye Smart EV Wallbox ---\033[0m")
    cfg["wallbox"]["host"] = prompt(
        "IP-Adresse Wallbox",
        cfg["wallbox"]["host"],
        help_text="Lokale WLAN-IP der Wallbox im Heimnetzwerk (z.B. in der FRITZ!Box / Router-Übersicht nachsehen)."
    )

    # Automatische Erkennung Seriennummer Wallbox
    print("🔍 Prüfe automatische Erkennung der Wallbox-Seriennummer...")
    detected_wb_serial = detect_logger_serial(cfg["wallbox"]["host"])
    default_wb_serial = detected_wb_serial if detected_wb_serial else cfg["wallbox"]["serial"]
    if detected_wb_serial:
        print(f"\033[1;32m✓ Seriennummer automatisch per WLAN erkannt: {detected_wb_serial}\033[0m")

    cfg["wallbox"]["serial"] = prompt(
        "Seriennummer Logger / Wallbox",
        default_wb_serial,
        help_text="Die 10-stellige Seriennummer des Deye WLAN-Sticks / Wallbox (steht auf dem Aufkleber oder im Router-Hostnamen).",
        val_type=int
    )

    # Automatische Erkennung Slave-ID Wallbox
    default_wb_slave = cfg["wallbox"]["slave_id"]
    if cfg["wallbox"]["host"] and cfg["wallbox"]["serial"]:
        print("🔍 Teste Modbus-Verbindung zur Wallbox (Slave-ID Scan)...")
        detected_wb_slave = scan_modbus_slave_id(cfg["wallbox"]["host"], cfg["wallbox"]["serial"], candidates=(3, 1, 2, 4))
        if detected_wb_slave is not None:
            print(f"\033[1;32m✓ Modbus-Antwort erhalten auf Slave-ID: {detected_wb_slave}\033[0m")
            default_wb_slave = detected_wb_slave

    cfg["wallbox"]["slave_id"] = prompt(
        "Modbus Slave-ID",
        default_wb_slave,
        help_text="Modbus RTU/TCP Geräte-ID der Deye Wallbox (Standard ist 3).",
        val_type=int
    )

    print("\n\033[1;33m--- 3. Deye Hybrid-Wechselrichter (Inverter) ---\033[0m")
    cfg["inverter"]["host"] = prompt(
        "IP-Adresse Wechselrichter",
        cfg["inverter"]["host"],
        help_text="IP-Adresse des Solarman / Deye WLAN-Datenloggers am Wechselrichter (im Router ersichtlich)."
    )

    # Automatische Erkennung Seriennummer Wechselrichter
    print("🔍 Prüfe automatische Erkennung der Inverter-Seriennummer...")
    detected_inv_serial = detect_logger_serial(cfg["inverter"]["host"])
    default_inv_serial = detected_inv_serial if detected_inv_serial else cfg["inverter"]["serial"]
    if detected_inv_serial:
        print(f"\033[1;32m✓ Seriennummer automatisch per WLAN erkannt: {detected_inv_serial}\033[0m")

    cfg["inverter"]["serial"] = prompt(
        "Seriennummer Inverter Logger",
        default_inv_serial,
        help_text="Seriennummer des Datenloggers am Wechselrichter (10-stellig, steht direkt auf dem Stick unter 'S/N').",
        val_type=int
    )

    # Automatische Erkennung Slave-ID Inverter
    default_inv_slave = cfg["inverter"]["slave_id"]
    if cfg["inverter"]["host"] and cfg["inverter"]["serial"]:
        print("🔍 Teste Modbus-Verbindung zum Wechselrichter (Slave-ID Scan)...")
        detected_inv_slave = scan_modbus_slave_id(cfg["inverter"]["host"], cfg["inverter"]["serial"], candidates=(1, 3, 2, 4))
        if detected_inv_slave is not None:
            print(f"\033[1;32m✓ Modbus-Antwort erhalten auf Slave-ID: {detected_inv_slave}\033[0m")
            default_inv_slave = detected_inv_slave

    cfg["inverter"]["slave_id"] = prompt(
        "Modbus Slave-ID",
        default_inv_slave,
        help_text="Modbus Slave-ID des Wechselrichters (Standard ist 1).",
        val_type=int
    )

    print("\n\033[1;33m--- 4. Fahrzeug & SoC-Anbindung ---\033[0m")
    v_type_default = cfg["vehicle"].get("type", "opel" if os.path.exists(LEGACY_CORSA_TOKENS) else "none")
    print("\033[0;36m💡 Wähle, ob der Watcher den Akkustand (SoC) über eine Fahrzeug-Cloud abfragen soll:")
    print("   1 = Keine Fahrzeug-Cloud (Universell für jedes Auto, reine Messung über Wallbox-Zähler)")
    print("   2 = Opel / PSA / Stellantis (Live-SoC & Reichweite über psa-token-helper)\033[0m")
    
    v_choice = prompt(
        "Fahrzeug-Anbindung (1=Keine, 2=Opel/PSA)",
        "2" if v_type_default == "opel" else "1"
    )
    if v_choice.strip() == "2":
        cfg["vehicle"]["type"] = "opel"
        print("\n\033[1;32m✓ Opel / PSA Cloud-Anbindung gewählt.\033[0m")
        print("\033[0;36m💡 Anleitung zur Einrichtung:")
        print("   1. Lade dir 'psa-token-helper.exe' herunter: https://github.com/hurzhurz/psa-token-helper/releases")
        print("   2. Starte das Tool, wähle 'Opel' und logge dich mit deinem MyOpel-Account ein.")
        print("   3. Kopiere die Ausgabe (JSON oder Refresh-Token) und füge sie unten ein.\033[0m")
        
        has_existing_tokens = os.path.exists(LEGACY_CORSA_TOKENS)
        token_prompt_label = "Neuen Token / JSON einfügen (oder leer lassen zum Beibehalten)" if has_existing_tokens else "Token / JSON einfügen"
        raw_token = input(f"\033[1;37m{token_prompt_label}\033[0m: ").strip()
        
        if raw_token:
            tokens_saved = False
            try:
                import re
                tok_dict = {}
                if "accessToken:" in raw_token or "refreshToken:" in raw_token:
                    acc_match = re.search(r'accessToken:\s*([a-zA-Z0-9\-_]+)', raw_token)
                    ref_match = re.search(r'refreshToken:\s*([a-zA-Z0-9\-_]+)', raw_token)
                    if acc_match: tok_dict["access_token"] = acc_match.group(1)
                    if ref_match: tok_dict["refresh_token"] = ref_match.group(1)
                    tok_dict["expires_in"] = 3600
                elif raw_token.startswith("{"):
                    tok_dict = json.loads(raw_token)
                else:
                    tok_dict = {"refresh_token": raw_token, "access_token": "", "expires_in": 3600}
                
                tok_dict["saved_at"] = time.time()
                with open(LEGACY_CORSA_TOKENS, "w", encoding="utf-8") as f:
                    json.dump(tok_dict, f, indent=2)
                print(f"\033[1;32m✓ Opel-Token erfolgreich in {LEGACY_CORSA_TOKENS} gespeichert!\033[0m")
                tokens_saved = True
            except Exception as e:
                print(f"⚠️ Konnte Token nicht verarbeiten: {e}")
        elif has_existing_tokens:
            print(f"\033[1;32m✓ Bestehender Token aus {LEGACY_CORSA_TOKENS} bleibt erhalten.\033[0m")

    else:
        cfg["vehicle"]["type"] = "none"
        print("\033[1;32m✓ Universeller Modus gewählt (Keine Cloud-Abfrage, reine Wallbox-Messung).\033[0m")

    cfg["vehicle"]["target_soc"] = prompt(
        "Standard-Ziel-SoC in %",
        cfg["vehicle"].get("target_soc", 66.0),
        help_text="Gewünschter Zielladestand für die Ladezeitberechnung (z.B. 66 oder 80 für Akkuschonung).",
        val_type=float
    )
    cfg["vehicle"]["battery_netto_kwh"] = prompt(
        "Netto Akkugröße in kWh",
        cfg["vehicle"].get("battery_netto_kwh", 46.0),
        help_text="Nutzbare Batteriekapazität deines E-Autos (z.B. 46.0 kWh für Corsa/e-208, 60.0 für ID.3, etc.).",
        val_type=float
    )

    print("\n\033[1;33m--- 5. Wetter- & Solarprognose (Open-Meteo) ---\033[0m")
    loc_input = prompt(
        "Ortsname",
        cfg["weather"]["location_name"],
        help_text="Name deines Wohnorts (z.B. Zellertal, Göllheim, Berlin). Koordinaten werden automatisch ermittelt!"
    )
    cfg["weather"]["location_name"] = loc_input

    # Automatische Geocoding-Abfrage
    auto_coords = geocode_location(loc_input)
    default_lat = auto_coords[0] if auto_coords else cfg["weather"]["latitude"]
    default_lon = auto_coords[1] if auto_coords else cfg["weather"]["longitude"]

    if auto_coords:
        print(f"\033[1;32m✓ Koordinaten für '{auto_coords[2]}' automatisch ermittelt: {auto_coords[0]:.4f}, {auto_coords[1]:.4f}\033[0m")

    cfg["weather"]["latitude"] = prompt(
        "Breitengrad (Latitude)",
        default_lat,
        help_text="Geografische Breite (wurde automatisch ermittelt oder manuell anpassen).",
        val_type=float
    )
    cfg["weather"]["longitude"] = prompt(
        "Längengrad (Longitude)",
        default_lon,
        help_text="Geografische Länge (wurde automatisch ermittelt oder manuell anpassen).",
        val_type=float
    )

    # Speichern in config.json
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    print(f"\n\033[1;32m✓ Konfiguration erfolgreich gespeichert in:\033[0m {CONFIG_PATH}")

    # Synchronisiere ~/.wallbox_telegram.json für Abwärtskompatibilität
    try:
        with open(LEGACY_TELEGRAM_PATH, "w", encoding="utf-8") as f:
            json.dump({
                "bot_token": cfg["telegram"]["bot_token"],
                "chat_id": cfg["telegram"]["chat_id"]
            }, f, indent=2)
        print(f"\033[1;32m✓ Telegram-Daten mit {LEGACY_TELEGRAM_PATH} synchronisiert.\033[0m")
    except Exception:
        pass

    # Optionaler Telegram-Test
    if cfg["telegram"]["bot_token"] and cfg["telegram"]["chat_id"]:
        do_test = input("\n👉 Möchtest du eine Testnachricht an Telegram senden? [J/n]: ").strip().lower()
        if do_test not in ("n", "no", "nein"):
            print("Sende Testnachricht an Telegram...")
            if test_telegram(cfg["telegram"]["bot_token"], cfg["telegram"]["chat_id"]):
                print("\033[1;32m✓ Testnachricht erfolgreich empfangen!\033[0m")
            else:
                print("\033[1;31m✗ Konnte keine Nachricht senden. Bitte Bot-Token und Chat-ID prüfen.\033[0m")

    print("\n✅ Fertig! Du kannst den Watcher nun mit './start_watcher.sh' oder 'python3 wallbox_watcher.py' starten.")

if __name__ == "__main__":
    main()
