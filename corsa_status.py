#!/data/data/com.termux/files/usr/bin/python3
"""
Opel Corsa Electric - Dual Vehicle Status Monitor
Fragt den Ladestand (SoC) und Ladestatus von zwei Corsa Electric direkt über die Opel/Stellantis Cloud ab.
"""

import sys
import os
import json
import time
import base64
import hashlib
import secrets
import urllib.parse
import re
from datetime import datetime

try:
    import requests
except ImportError:
    print("Fehler: 'requests' ist nicht installiert. Bitte ausführen: pip install requests")
    sys.exit(1)

# Stellantis / Opel API Zugangsdaten (Offizieller Client der MyOpel App)
OPEL_CONFIG = {
    "realm": "opel.com",
    "auth_realm": "clientsB2COpel",
    "scheme": "mymopsdk",
    "client_id": "07364655-93cb-4194-8158-6b035ac2c24c",
    "client_secret": "F2kK7lC5kF5qN7tM0wT8kE3cW1dP0wC5pI6vC0sQ5iP5cN8cJ8",
    "token_url": "https://idpcvs.opel.com/am/oauth2/access_token",
    "api_base": "https://api.groupe-psa.com/connectedcar/v4/user",
}

TOKEN_FILE = os.path.expanduser("~/.corsa_tokens.json")


def generate_pkce(length=64):
    """Erzeugt PKCE Code-Verifier und Code-Challenge für sicheren OAuth2-Login."""
    verifier = secrets.token_urlsafe(length)
    digest = hashlib.sha256(verifier.encode('ascii')).digest()
    challenge = base64.urlsafe_b64encode(digest).decode('ascii').rstrip('=')
    return verifier, challenge


def get_basic_auth_header():
    auth_str = f"{OPEL_CONFIG['client_id']}:{OPEL_CONFIG['client_secret']}"
    b64_auth = base64.b64encode(auth_str.encode('ascii')).decode('ascii')
    return {
        "Authorization": f"Basic {b64_auth}",
        "User-Agent": "Mozilla/5.0 (Linux; Android 11; Mobile)",
    }


def extract_auth_code(user_input):
    """Extrahiert zuverlässig den Authorization Code aus der eingegebenen URL oder Zeichenkette."""
    user_input = user_input.strip()
    if "%3D" in user_input or "%2F" in user_input:
        user_input = urllib.parse.unquote(user_input)
    match = re.search(r'code=([^&"\'#\s]+)', user_input)
    if match:
        return match.group(1)
    return user_input


def perform_login():
    """Führt den Login ausschließlich über psa-token-helper.exe durch."""
    print("\n" + "=" * 65)
    print("      OPEL CONNECT - ANMELDUNG MIT PSA-TOKEN-HELPER.EXE")
    print("=" * 65)
    print("\n1. Lade dir die 'psa-token-helper.exe' auf deinen PC herunter:")
    print("   👉 https://github.com/hurzhurz/psa-token-helper/releases")
    print("\n2. Starte die 'psa-token-helper.exe' und wähle 'Opel'.")
    print("3. Melde dich im Fenster mit deinen MyOpel-Zugangsdaten an.")
    print("4. Kopiere nach erfolgreichem Login die Tokens oder das Refresh-Token.")
    print("   (Format z.B.: 'accessToken: ... refreshToken: ...' oder das JSON oder nur das refreshToken)\n")

    try:
        raw = input("Eingabe (Kopierten Text, JSON oder Refresh-Token einfügen): ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\nAbgebrochen.")
        sys.exit(0)

    if not raw:
        print("❌ Keine Eingabe erhalten.")
        sys.exit(1)

    tokens = {}
    # Fall 1: Format "accessToken: ... refreshToken: ..."
    if "accessToken:" in raw or "refreshToken:" in raw:
        acc_match = re.search(r'accessToken:\s*([a-zA-Z0-9\-_]+)', raw)
        ref_match = re.search(r'refreshToken:\s*([a-zA-Z0-9\-_]+)', raw)
        if acc_match:
            tokens["access_token"] = acc_match.group(1)
        if ref_match:
            tokens["refresh_token"] = ref_match.group(1)
        tokens["expires_in"] = 3600

    # Fall 2: JSON
    elif raw.startswith("{"):
        try:
            tokens = json.loads(raw)
        except Exception as e:
            print(f"❌ Ungültiges JSON: {e}")
            sys.exit(1)

    # Fall 3: Nur das Refresh-Token
    else:
        tokens["refresh_token"] = raw
        tokens["access_token"] = ""
        tokens["expires_in"] = 3600

    # Falls wir ein refresh_token haben, aber kein gültiges access_token:
    if tokens.get("refresh_token") and not tokens.get("access_token"):
        print("\n⏳ Hole frisches Access-Token über das Refresh-Token...")
        try:
            tokens = refresh_access_token(tokens["refresh_token"])
        except Exception as e:
            print(f"⚠️ Warnung beim Token-Abruf: {e}")

    tokens["saved_at"] = time.time()
    save_tokens(tokens)
    print("✅ Erfolgreich eingerichtet! Token gespeichert in:", TOKEN_FILE)
    return tokens


def save_tokens(tokens):
    with open(TOKEN_FILE, "w") as f:
        json.dump(tokens, f, indent=2)


def load_tokens():
    if not os.path.exists(TOKEN_FILE):
        return None
    try:
        with open(TOKEN_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return None


def refresh_access_token(refresh_token):
    """Erneuert das abgelaufene Access-Token mit dem Refresh-Token."""
    post_data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    res = requests.post(
        OPEL_CONFIG["token_url"],
        data=post_data,
        headers=get_basic_auth_header(),
        timeout=15
    )
    res.raise_for_status()
    new_tokens = res.json()
    new_tokens["saved_at"] = time.time()
    if "refresh_token" not in new_tokens:
        new_tokens["refresh_token"] = refresh_token
    save_tokens(new_tokens)
    return new_tokens


def get_valid_token():
    tokens = load_tokens()
    if not tokens or "access_token" not in tokens:
        tokens = perform_login()

    saved_at = tokens.get("saved_at", 0)
    expires_in = tokens.get("expires_in", 3600)
    if time.time() - saved_at > (expires_in - 300):
        try:
            tokens = refresh_access_token(tokens["refresh_token"])
        except Exception as e:
            print(f"⚠️ Token-Erneuerung fehlgeschlagen ({e}), starte neuen Login...")
            tokens = perform_login()

    return tokens["access_token"]


def fetch_vehicles(access_token):
    headers = {
        "Authorization": f"Bearer {access_token}",
        "x-introspect-realm": "clientsB2COpel",
        "User-Agent": "Mozilla/5.0 (Linux; Android 11; Mobile)",
        "Accept": "application/hal+json",
    }
    url = f"{OPEL_CONFIG['api_base']}/vehicles?client_id={OPEL_CONFIG['client_id']}"
    res = requests.get(url, headers=headers, timeout=15)
    if res.status_code == 401:
        return None
    res.raise_for_status()
    data = res.json()
    return data.get("_embedded", {}).get("vehicles", [])


def fetch_vehicle_status(vehicle_id, access_token):
    headers = {
        "Authorization": f"Bearer {access_token}",
        "x-introspect-realm": "clientsB2COpel",
        "User-Agent": "Mozilla/5.0 (Linux; Android 11; Mobile)",
        "Accept": "application/hal+json",
    }
    url = f"{OPEL_CONFIG['api_base']}/vehicles/{vehicle_id}/status?client_id={OPEL_CONFIG['client_id']}"
    res = requests.get(url, headers=headers, timeout=15)
    res.raise_for_status()
    return res.json()


def display_status():
    token = get_valid_token()
    vehicles = fetch_vehicles(token)

    if vehicles is None:
        tokens = load_tokens()
        if tokens and "refresh_token" in tokens:
            tokens = refresh_access_token(tokens["refresh_token"])
            token = tokens["access_token"]
            vehicles = fetch_vehicles(token)

    if not vehicles:
        print("⚠️ Keine Fahrzeuge im Opel-Konto gefunden.")
        return

    now_str = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    print("\n" + "=" * 55)
    print(f"       OPEL CORSA ELECTRIC - STATUS ({now_str})")
    print("=" * 55)

    for idx, v in enumerate(vehicles, 1):
        v_id = v.get("id")
        vin = v.get("vin", "Unbekannt")
        label = v.get("label") or f"Corsa #{idx}"
        
        try:
            status = fetch_vehicle_status(v_id, token)
        except Exception as e:
            print(f"\n🚘 {label} (VIN: {vin}):")
            print(f"   ❌ Fehler beim Abrufen des Status: {e}")
            continue

        energy_list = status.get("energy", [])
        soc = "Unbekannt"
        autonomy = "Unbekannt"
        charging_status = "Unbekannt"
        plugged = False
        rate = 0
        updated_at = status.get("updatedAt", "")

        for e in energy_list:
            if e.get("type", "").lower() in ["electric", "battery"]:
                soc = e.get("level", "Unbekannt")
                autonomy = e.get("autonomy", "Unbekannt")
                charging = e.get("charging", {})
                charging_status = charging.get("status", "Unbekannt")
                plugged = charging.get("plugged", False)
                rate = charging.get("chargingRate", 0)

        status_clean = str(charging_status).lower()
        if status_clean in ["inprogress", "charging"]:
            is_charging = "⚡ JA (Wird geladen)"
            if rate:
                is_charging += f" mit {rate} km/h"
        elif status_clean in ["stopped", "paused"]:
            is_charging = "⏸️ Pausiert / Bereit"
        elif status_clean in ["complete", "completed"]:
            is_charging = "✅ Voll aufgeladen"
        else:
            is_charging = f"ℹ️ {charging_status}"

        time_display = ""
        if updated_at:
            try:
                dt = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
                time_display = dt.strftime("%H:%M:%S Uhr")
            except Exception:
                time_display = updated_at

        print(f"\n🚘 Fahrzeug {idx}: {label}")
        print(f"   VIN:             {vin}")
        print(f"   Akkustand (SoC): {soc} %")
        if autonomy != "Unbekannt":
            print(f"   Restreichweite:  ~{autonomy} km")
        print(f"   Ladekabel:       {'🔌 Eingesteckt' if plugged else '⚪ Nicht eingesteckt'}")
        print(f"   Ladevorgang:     {is_charging}")
        if time_display:
            print(f"   Letztes Update:  {time_display}")

    print("\n" + "=" * 55)


def main():
    if "--login" in sys.argv or "-l" in sys.argv:
        perform_login()
        return

    if "--watch" in sys.argv or "-w" in sys.argv:
        interval = 300  # Alle 5 Minuten
        print(f"Starte Überwachung (Aktualisierung alle {interval//60} Minuten, Abbruch mit Strg+C)...")
        while True:
            display_status()
            time.sleep(interval)
    else:
        display_status()


if __name__ == "__main__":
    main()
