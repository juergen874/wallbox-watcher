# 🤖 Wallbox-Watcher — Ausführliche Dokumentation (Deutsch)

`wallbox_watcher.py` ist der **zentrale 24/7-Hintergrunddienst** und vereint Wallbox-Regelung, Inverter-Monitoring, Opel Corsa Electric SoC-Berechnungen, Wettervorhersagen und einen interaktiven Telegram Bot.

---

## 🎯 Zweck und Funktionsumfang

1. **Echtzeit-Ladeerkennung:**  
   Sobald an der Wallbox eine Ladeleistung von mehr als 1.200 W anliegt, erkennt der Dienst einen neuen Ladevorgang und versendet eine detaillierte Status-Push-Nachricht an Telegram.
2. **Dynamische Ladezeitberechnung (Ziel: 66% SoC):**  
   Berechnet anhand des echten Opel-Akkustands (SoC %), der Nettokapazität (46.0 kWh), 90% Ladeeffizienz und der aktuellen Ladeleistung die exakte Restladezeit und die Ziel-Uhrzeit.
3. **Batteriespeicher-Schutz & Überschuss-Empfehlungen:**  
   - **$\le$ 30% Speicher:** Sendet eine Warnung mit Empfehlung zum Pausieren der Ladung, um den Heimspeicher nicht leerzusaugen.  
   - **$\ge$ 85% Speicher:** Sendet eine Benachrichtigung inklusive 3-Tage-Sonnenschein-Vorhersage für Zellertal mit Empfehlung zum Laden.
4. **Interaktive Telegram-Tastatur:**  
   Bietet Inline-Buttons zur Fernsteuerung:
   - `[ ▶️ Laden starten ]`: Setzt Ladelimit auf 15 kW.
   - `[ ⏸️ Laden pausieren ]`: Setzt Ladelimit sofort auf 0 W.
   - `[ 📊 Status aktualisieren ]`: Fragt Wallbox, Inverter, Fahrzeug und Wetter live ab.
5. **Intelligenter Stecker-Reset (Auto-Resume auf 15 kW):**  
   Wurde die Wallbox manuell pausiert (0 W), erkennt der Dienst über Register 57 sofort das Abziehen des Ladekabels am Auto und setzt das Ladelimit automatisch wieder auf **15.0 kW** zurück, sodass beim nächsten Anstecken ohne Handgriff direkt geladen wird.

---

## ⚙️ Architektur & Systemübersicht

```
+-------------------------------------------------------------+
|                     wallbox_watcher.py                      |
+------------------------------+------------------------------+
                               |
       +-----------------------+-----------------------+
       |                       |                       |
       v                       v                       v
[ Deye Wallbox ]       [ Deye Inverter ]       [ Stellantis API ]
192.168.188.130         192.168.188.128         api.groupe-psa.com
Modbus: Port 8899       Modbus: Port 8899       Auto-SoC & Range
Slave 3 / Reg 18        Slave 1 / Reg 588       90s In-Memory-Cache
       ^                       ^                       ^
       +-----------------------+-----------------------+
                               |
                               v
                     [ Telegram Bot API ]
                     Inline-Buttons & Push
```

---

## 🚀 Einrichtung & Start

### 1. Telegram-Bot einrichten
Beim ersten Start auf einem neuen Gerät:
```bash
python3 wallbox_watcher.py --setup
```
Hier werden Bot-Token und Chat-ID abgefragt und in `~/.wallbox_telegram.json` gesichert.

### 2. Hintergrundbetrieb auf dem LG Spirit (Server)
Das beiliegende Start-Skript `start_watcher.sh` übernimmt:
- Aktivierung des Termux Wake-Locks (`termux-wake-lock`) gegen Standby.
- Beenden alter Instanzen.
- Start im Hintergrund via `nohup`:
```bash
bash ~/start_watcher.sh
```

### 3. Logdatei überwachen
```bash
tail -f ~/wallbox_watcher.log
```

---

## 🔘 Telegram-Nachrichtenbeispiel

```text
⚡ *Neuer Ladevorgang erkannt!*

🚗 *Opel Corsa Electric (VR3UPZKXZLT000000)*
🔋 Aktueller Akkustand: *42.0%* (138 km)
🎯 Ziel: *66.0%* (+24.0% / +11.0 kWh netto)
⚡ Ladeleistung: *6.89 kW* (Wallbox: 6.89 kW)
⏱️ Benötigte Ladedauer: *1 Std. 47 Min.*
🏁 Voraussichtlich fertig um: *23:11 Uhr*

🏠 *Heimsystem & PV:*
☀️ PV-Erzeugung: *4.50 kW*
🔋 Heimspeicher: *78%*
⚡ Netzbezug: *-1.20 kW (Einspeisung)*
```
