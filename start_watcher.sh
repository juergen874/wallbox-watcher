#!/data/data/com.termux/files/usr/bin/bash
# 1. Termux Wake Lock aktivieren
termux-wake-lock

# 2. Bestehenden Watcher beenden
pkill -9 -f wallbox_watcher.py 2>/dev/null
pkill -9 -f wifi_keepalive.py 2>/dev/null

sleep 1

# 3. Wallbox Watcher starten
nohup python3 /data/data/com.termux/files/home/wallbox_watcher.py > /data/data/com.termux/files/home/wallbox_watcher.log 2>&1 &

echo "Wallbox Watcher gestartet:"
ps -ef | grep python
