# 🤖 Wallbox-Watcher — Comprehensive Documentation (English)

`wallbox_watcher.py` is the **core 24/7 background service** combining wallbox control, solar inverter monitoring, Opel Corsa Electric SoC calculations, weather forecasting, and an interactive Telegram Bot.

---

## 🎯 Purpose & Features

1. **Real-Time Charging Session Detection:**  
   As soon as active power output exceeds 1,200 W, the daemon detects a new charging session and sends a detailed push notification to Telegram.
2. **Dynamic Charging Duration Calculations (Target: 66% SoC):**  
   Calculates required energy (kWh), remaining charge time, and expected completion time based on real vehicle battery SoC, 46.0 kWh net capacity, 90% charging efficiency, and live charging power.
3. **Battery Storage Protection & Solar Surplus Guidance:**  
   - **$\le$ 30% Battery Storage:** Alerts the user with a recommendation to pause EV charging to prevent deep home battery depletion.  
   - **$\ge$ 85% Battery Storage:** Sends an advisory notification including a 3-day sunshine forecast for Zellertal recommending to charge.
4. **Interactive Telegram Keyboard:**  
   Provides inline buttons for instant remote control:
   - `[ ▶️ Laden starten ]`: Sets wallbox limit to 15 kW.
   - `[ ⏸️ Laden pausieren ]`: Throttles wallbox limit immediately to 0 W.
   - `[ 📊 Status aktualisieren ]`: Live query of Wallbox, Inverter, Vehicle, and Weather.
5. **Intelligent Cable Unplug Auto-Reset (Auto-Resume to 15 kW):**  
   When the wallbox was manually paused (0 W), the daemon detects via Register 57 the moment the charging cable is unplugged from the car and automatically resets the limit back to **15.0 kW**, ensuring the next charge starts at full power without manual intervention.

---

## ⚙️ Architecture & Overview

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
Modbus: Port 8899       Modbus: Port 8899       Car SoC & Range
Slave 3 / Reg 18        Slave 1 / Reg 588       90s In-Memory-Cache
       ^                       ^                       ^
       +-----------------------+-----------------------+
                               |
                               v
                     [ Telegram Bot API ]
                     Inline-Buttons & Push
```

---

## 🚀 Setup & Launch

### 1. Telegram Bot Setup
On initial setup:
```bash
python3 wallbox_watcher.py --setup
```
Prompts for Bot Token and Chat ID and securely stores them in `~/.wallbox_telegram.json`.

### 2. Background Daemon on LG Spirit (Server)
The bundled script `start_watcher.sh` manages:
- Enabling Termux Wake Lock (`termux-wake-lock`) against sleep mode.
- Stopping any prior instances.
- Launching in background via `nohup`:
```bash
bash ~/start_watcher.sh
```

### 3. Log Monitoring
```bash
tail -f ~/wallbox_watcher.log
```

---

## 🔘 Telegram Message Example

```text
⚡ *Neuer Ladevorgang erkannt!*

🚗 *Opel Corsa Electric (VR3UPZKXZLT000000)*
🔋 Current Battery: *42.0%* (138 km)
⚡ *Charging Power:* 🟢 Charging at *5.0 kW* _(1-phase / 15 kW limit)_
⏱️ Remaining Duration: *2 hr 27 min*
🏁 Estimated Completion: *23:51*

🏠 *Home System & Solar:*
☀️ PV Generation: *4.50 kW*
🔋 Battery Storage: *78%*
⚡ Grid Exchange: *-1.20 kW (Export)*
```
