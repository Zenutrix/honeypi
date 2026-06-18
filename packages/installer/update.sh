#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="/opt/hanipi"
STATIC_SRC="$INSTALL_DIR/packages/dashboard/hanipi_dashboard/static"

echo "==> HaniPi Update"

echo "==> Code aktualisieren..."
git -C "$INSTALL_DIR" pull

echo "==> System-Build-Abhaengigkeiten pruefen..."
# swig wird zum Bauen der lgpio-C-Extension (rpi-lgpio) benoetigt; idempotent,
# falls schon installiert macht apt-get hier praktisch nichts.
sudo apt-get install -y -qq swig python3-dev build-essential liblgpio-dev fonts-dejavu-core
# SPI-Kernel-Modul aktivieren (idempotent)
sudo raspi-config nonint do_spi 0 2>/dev/null || true

echo "==> Python-Pakete aktualisieren..."
PYTHON="$INSTALL_DIR/venv/bin/python3"
if [ ! -f "$PYTHON" ]; then PYTHON="$INSTALL_DIR/venv/bin/python"; fi
"$PYTHON" -m ensurepip -q 2>/dev/null || true
# Erst neue/geaenderte Abhaengigkeiten normal aufloesen ...
"$PYTHON" -m pip install -q \
  "$INSTALL_DIR/packages/dashboard" \
  "$INSTALL_DIR/packages/rpi-agent"
# ... dann hanipi-agent/-dashboard selbst IMMER neu bauen+installieren.
# Ohne --force-reinstall ueberspringt pip lokale Pfad-Installs, wenn die
# Versionsnummer gleich bleibt ("Requirement already satisfied") - der
# eigentliche Quellcode wuerde dann NIE aktualisiert werden, nur neue
# Abhaengigkeiten kaemen an.
"$PYTHON" -m pip install -q --force-reinstall --no-deps \
  "$INSTALL_DIR/packages/dashboard" \
  "$INSTALL_DIR/packages/rpi-agent"

STATIC_DST=$(find /opt/hanipi/venv/lib -maxdepth 4 -name "static" \
  -path "*/hanipi_dashboard/static" 2>/dev/null | head -1)

if [ -n "$STATIC_DST" ]; then
  echo "==> Static Files → $STATIC_DST"
  cp "$STATIC_SRC"/* "$STATIC_DST"/
else
  echo "    [Warnung] Static-Ziel nicht gefunden, übersprungen."
fi

echo "==> Services neu starten..."
systemctl restart hanipi-dashboard
systemctl restart hanipi-agent

echo ""
echo "==> Fertig!"
