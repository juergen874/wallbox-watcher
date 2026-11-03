# 🚗 Corsa-Status — Ausführliche Dokumentation (Deutsch)

`corsa_status.py` ist ein eigenständiges Modul zur Abfrage von Fahrzeugdaten und Ladestatus für **Opel / Stellantis Elektrofahrzeuge** (z. B. Opel Corsa Electric) über die offizielle Stellantis Connected Car API.

---

## 🎯 Zweck und Funktionsumfang

- **Akkustand & Restreichweite:** Liest den genauen Ladezustand (SoC in %) und die berechnete Reichweite in Kilometern aus.
- **Kabel- & Ladestatus:** Erkennt, ob das Ladekabel gesteckt ist (`cable_plugged`) und welcher Lademodus aktiv ist (`InProgress`, `Stopped`, `Complete`, `Disconnected`).
- **Multi-Fahrzeug-Unterstützung:** Listet automatisch alle im Stellantis-Account hinterlegten Fahrzeuge mit Modellbezeichnung und FIN (VIN) auf.
- **Automatisches Token-Management:** Speichert Zugangs- und Aktualisierungstokens lokal in `~/.corsa_tokens.json` und erneuert abgelaufene Access-Tokens selbstständig im Hintergrund über den Refresh-Token-Endpunkt.

---

## ⚙️ Technische Details & Schnittstellen

- **API-Host:** `api.groupe-psa.com` / `idpcvs.opel.com`
- **Authentifizierung:** OAuth2 mit PKCE / Stellantis Connected Vehicle IDP.
- **Token-Ablage:** `~/.corsa_tokens.json` (wird per `.gitignore` vor Git-Commits geschützt).
- **In-Memory Cache:** 90 Sekunden Cache in übergeordneten Diensten zur Vermeidung von HTTP 429 (Rate Limiting).

---

## 🔑 Erstmalige Anmeldung & Authentifizierung

Stellantis erfordert für Drittanwendungen ein OAuth2-Token. Die einfachste Methode ist die Nutzung des bewährten Open-Source-Tools `psa-token-helper`:

1. **Token Helper herunterladen:**
   👉 [https://github.com/hurzhurz/psa-token-helper/releases](https://github.com/hurzhurz/psa-token-helper/releases)
2. **Starten & Anmelden:**
   - Programm starten, Marke **Opel** wählen.
   - Mit deinen normalen MyOpel-Zugangsdaten anmelden.
   - Das generierte Token (oder der gesamte JSON-Block) in die Zwischenablage kopieren.
3. **Im Terminal speichern:**
   ```bash
   python3 corsa_status.py --login
   ```
   Den kopierten Token-Text einfügen und mit Enter bestätigen. Der Token wird in `~/.corsa_tokens.json` gesichert und zukünftig vollautomatisch erneuert.

---

## 💻 Verwendung

### 1. Einmalige Statusabfrage
```bash
python3 corsa_status.py
```
**Beispiel-Ausgabe:**
```text
============================================================
              OPEL CONNECT - FAHRZEUGSTATUS                 
============================================================

🚗 CORSA-E ELECTRIC (FIN: VR3UPZKXZLT000000)
   🔋 Akkustand (SoC):  42 %
   🛣️ Restreichweite:   138 km
   🔌 Ladekabel:        Angesteckt
   ⚡ Ladestatus:       InProgress (6.8 kW)
```

### 2. Fortlaufende Überwachung (Terminal-Watch)
```bash
python3 corsa_status.py --watch
```
Fragt die Daten standardmäßig alle 5 Minuten ab, ohne die Stellantis-Server zu überlasten.

### 3. Programmatische Nutzung in Python
```python
import corsa_status

token = corsa_status.get_valid_token()
vehicles = corsa_status.fetch_vehicles(token)

for v in vehicles:
    status = corsa_status.fetch_vehicle_status(v["id"], token)
    soc = status.get("energy", [{}])[0].get("level", 0)
    print(f"Fahrzeug {v.get('label')}: {soc}%")
```

---

## 🛡️ Best Practices & Ratschläge

- **API Rate Limits beachten:** Stellantis drosselt Konten bei zu vielen API-Aufrufen innerhalb kurzer Zeit. In Produktivdiensten (`wallbox_watcher.py`) sollte immer ein Cache von mindestens 60–90 Sekunden verwendet werden.
- **Token-Sicherheit:** Die Datei `~/.corsa_tokens.json` darf niemals in öffentliche Repositories gelangen.
