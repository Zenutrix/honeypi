#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="/opt/hanipi"
STATIC_SRC="$INSTALL_DIR/packages/dashboard/hanipi_dashboard/static"

echo "==> HaniPi Update"

echo "==> Code aktualisieren..."
git -C "$INSTALL_DIR" pull

echo "==> Python-Pakete aktualisieren..."
"$INSTALL_DIR/venv/bin/pip" install -q \
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
