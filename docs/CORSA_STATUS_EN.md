# 🚗 Corsa-Status — Comprehensive Documentation (English)

`corsa_status.py` is an independent module designed to query vehicle telemetry and charging status for **Opel / Stellantis Electric Vehicles** (e.g. Opel Corsa Electric) using the official Stellantis Connected Car API.

---

## 🎯 Purpose & Features

- **Battery State & Range:** Queries precise battery charge level (SoC in %) and calculated remaining driving range in kilometers.
- **Cable & Charging State:** Detects whether the charging cable is connected (`cable_plugged`) and the active charge state (`InProgress`, `Stopped`, `Complete`, `Disconnected`).
- **Multi-Vehicle Support:** Automatically enumerates and queries all registered vehicles tied to the user's Stellantis account.
- **Automated Token Management:** Stores access and refresh tokens locally in `~/.corsa_tokens.json` and automatically refreshes expired tokens in the background.

---

## ⚙️ Technical Details & APIs

- **API Host:** `api.groupe-psa.com` / `idpcvs.opel.com`
- **Authentication:** OAuth2 with PKCE / Stellantis Connected Vehicle IDP.
- **Token Location:** `~/.corsa_tokens.json` (protected by `.gitignore` from Git commits).
- **In-Memory Cache:** 90-second cache in host applications to prevent HTTP 429 (Rate Limiting).

---

## 🔑 Initial Setup & Authentication

Stellantis requires OAuth2 credentials. The easiest and most reliable method is utilizing the open-source `psa-token-helper`:

1. **Download Token Helper:**
   👉 [https://github.com/hurzhurz/psa-token-helper/releases](https://github.com/hurzhurz/psa-token-helper/releases)
2. **Login:**
   - Launch the helper, select **Opel**.
   - Log in with your standard MyOpel account credentials.
   - Copy the generated tokens or JSON output to your clipboard.
3. **Save in Terminal:**
   ```bash
   python3 corsa_status.py --login
   ```
   Paste the clipboard text and press Enter. The token will be saved to `~/.corsa_tokens.json` and kept valid automatically.

---

## 💻 Usage

### 1. One-off Status Check
```bash
python3 corsa_status.py
```
**Example Output:**
```text
============================================================
              OPEL CONNECT - VEHICLE STATUS                 
============================================================

🚗 CORSA-E ELECTRIC (VIN: VR3UPZKXZLT000000)
   🔋 Battery (SoC):    42 %
   🛣️ Range:            138 km
   🔌 Charging Cable:   Connected
   ⚡ Charging State:   InProgress (6.8 kW)
```

### 2. Live Terminal Watch Mode
```bash
python3 corsa_status.py --watch
```
Polls vehicle data every 5 minutes without exceeding Stellantis rate limits.

### 3. Programmatic Usage in Python
```python
import corsa_status

token = corsa_status.get_valid_token()
vehicles = corsa_status.fetch_vehicles(token)

for v in vehicles:
    status = corsa_status.fetch_vehicle_status(v["id"], token)
    soc = status.get("energy", [{}])[0].get("level", 0)
    print(f"Vehicle {v.get('label')}: {soc}%")
```

---

## 🛡️ Best Practices & Warnings

- **Respect Rate Limits:** Stellantis throttles accounts if too many requests are sent within a short window. Always maintain a 60–90 second cache in automated daemons.
- **Credential Protection:** Never commit `~/.corsa_tokens.json` to version control.
