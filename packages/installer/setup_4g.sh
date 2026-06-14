#!/usr/bin/env bash
# HoneyPi 4G/Surfstick Setup
# Konfiguriert einen USB-Mobilfunkstick via ModemManager + NetworkManager
set -euo pipefail

echo "==> HoneyPi 4G/Surfstick Setup"
echo ""

# Prüfen ob ModemManager läuft
if ! systemctl is-active --quiet ModemManager; then
  echo "Starte ModemManager..."
  sudo systemctl start ModemManager
  sleep 3
fi

# Surfstick erkennen
echo "Suche nach USB-Modem..."
MODEM=$(mmcli -L 2>/dev/null | grep -oP '/org/freedesktop/ModemManager1/Modem/\K[0-9]+' | head -1 || true)

if [ -z "$MODEM" ]; then
  echo ""
  echo "Kein Modem gefunden. Bitte prüfen:"
  echo "  1. Stick eingesteckt?"
  echo "  2. 'lsusb' ausführen und Gerät prüfen"
  echo "  3. Ggf. 'usb_modeswitch' nötig (Stick wechselt von Speicher zu Modem)"
  echo ""
  echo "Bekannte Sticks die automatisch erkannt werden:"
  echo "  - Huawei E3372, E3531, E8372"
  echo "  - ZTE MF79, MF823"
  echo "  - Quectel EC21"
  exit 1
fi

echo "Modem gefunden: /Modem/$MODEM"
mmcli -m "$MODEM"

echo ""
read -rp "APN eingeben (z.B. internet.telekom, web.vodafone.de, internet): " APN
read -rp "Benutzername (leer lassen wenn nicht nötig): " USER
read -rp "Passwort (leer lassen wenn nicht nötig): " PASS

CON_NAME="honeypi-4g"

# Bestehende Verbindung entfernen
nmcli connection delete "$CON_NAME" 2>/dev/null || true

echo "==> Erstelle Mobilfunkverbindung '$CON_NAME'..."
sudo nmcli connection add \
  type gsm \
  con-name "$CON_NAME" \
  ifname "*" \
  gsm.apn "$APN" \
  ${USER:+gsm.username "$USER"} \
  ${PASS:+gsm.password "$PASS"} \
  connection.autoconnect yes

echo "==> Verbinde..."
sudo nmcli connection up "$CON_NAME" || true

sleep 5

if nmcli connection show --active | grep -q "$CON_NAME"; then
  echo ""
  echo "4G-Verbindung aktiv!"
  ip route show default
else
  echo ""
  echo "Verbindung nicht aktiv — Logs prüfen:"
  echo "  journalctl -u ModemManager -n 50"
  echo "  journalctl -u NetworkManager -n 50"
fi
