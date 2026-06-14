#!/usr/bin/env bash
set -euo pipefail

REPO="https://github.com/Zenutrix/honeypi"
INSTALL_DIR="/opt/honeypi"
DATA_DIR="/var/lib/honeypi"
CFG_DIR="/etc/honeypi"

echo "==> HoneyPi Installer"
echo "==> Updating system packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq git python3 python3-pip avahi-daemon

echo "==> Installing uv..."
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
UV="$HOME/.local/bin/uv"

echo "==> Cloning repository..."
if [ -d "$INSTALL_DIR" ]; then
  cd "$INSTALL_DIR" && sudo git pull
else
  sudo git clone "$REPO" "$INSTALL_DIR"
fi

echo "==> Creating honeypi user..."
id -u honeypi &>/dev/null || sudo useradd --system --no-create-home honeypi

echo "==> Setting up Python environment..."
cd "$INSTALL_DIR"
sudo "$UV" venv /opt/honeypi/venv
sudo "$UV" pip install --python /opt/honeypi/venv/bin/python \
  packages/rpi-agent packages/dashboard

echo "==> Creating directories..."
sudo mkdir -p "$DATA_DIR" "$CFG_DIR"
sudo chown honeypi:honeypi "$DATA_DIR"

echo "==> Writing default config..."
if [ ! -f "$CFG_DIR/honeypi.json" ]; then
  sudo tee "$CFG_DIR/honeypi.json" > /dev/null <<'HONEYPI_JSON'
{
  "interval": 300,
  "sensors": [
    {"type": "dummy", "name": "Demo", "values": {"weight_kg": 10.0, "temperature_c": 20.0}}
  ],
  "exporters": {
    "local": {"enabled": true, "db_path": "/var/lib/honeypi/data.db"}
  }
}
HONEYPI_JSON
fi

echo "==> Installing systemd services..."
sudo cp "$INSTALL_DIR/packages/rpi-agent/systemd/honeypi-agent.service" /etc/systemd/system/
sudo cp "$INSTALL_DIR/packages/dashboard/systemd/honeypi-dashboard.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now honeypi-agent honeypi-dashboard

echo ""
echo "HoneyPi installed successfully!"
echo "  Dashboard: http://honeypi.local"
echo "  Config:    $CFG_DIR/honeypi.json"
echo "  Logs:      journalctl -u honeypi-agent -f"
