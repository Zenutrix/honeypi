#!/usr/bin/env bash
set -euo pipefail

REPO="https://github.com/Zenutrix/HaniPi"
INSTALL_DIR="/opt/hanipi"
DATA_DIR="/var/lib/hanipi"
CFG_DIR="/etc/hanipi"

echo "==> HaniPi Installer"
echo "==> Updating system packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
  git python3 python3-pip python3-dev \
  avahi-daemon \
  i2c-tools \
  modemmanager usb-modeswitch usb-modeswitch-data \
  build-essential

# Enable I2C and 1-Wire interfaces if not already active
if ! grep -q "^dtparam=i2c_arm=on" /boot/firmware/config.txt 2>/dev/null && \
   ! grep -q "^dtparam=i2c_arm=on" /boot/config.txt 2>/dev/null; then
  CFG_FILE="/boot/firmware/config.txt"
  [ -f "$CFG_FILE" ] || CFG_FILE="/boot/config.txt"
  echo "==> Enabling I2C and 1-Wire in $CFG_FILE..."
  echo "dtparam=i2c_arm=on" | sudo tee -a "$CFG_FILE" > /dev/null
  echo "dtoverlay=w1-gpio" | sudo tee -a "$CFG_FILE" > /dev/null
fi

echo "==> Installing uv..."
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
sudo ln -sf "$HOME/.local/bin/uv" /usr/local/bin/uv

echo "==> Cloning repository..."
if [ -d "$INSTALL_DIR" ]; then
  cd "$INSTALL_DIR" && sudo git pull
else
  sudo git clone "$REPO" "$INSTALL_DIR"
fi

echo "==> Creating hanipi user..."
id -u hanipi &>/dev/null || sudo useradd --system --no-create-home hanipi

# Add hanipi user to hardware and network groups
sudo usermod -aG i2c,gpio,dialout,netdev hanipi 2>/dev/null || true

echo "==> Configuring sudoers for hanipi..."
cat > /tmp/hanipi-sudoers <<'SUDOERS'
# HaniPi: allow dashboard to control the agent service and manage 4G connections
hanipi ALL=(root) NOPASSWD: /usr/bin/systemctl start hanipi-agent
hanipi ALL=(root) NOPASSWD: /usr/bin/systemctl stop hanipi-agent
hanipi ALL=(root) NOPASSWD: /usr/bin/systemctl restart hanipi-agent
hanipi ALL=(root) NOPASSWD: /usr/bin/nmcli
SUDOERS
sudo visudo -c -f /tmp/hanipi-sudoers && \
  sudo cp /tmp/hanipi-sudoers /etc/sudoers.d/hanipi && \
  sudo chmod 0440 /etc/sudoers.d/hanipi

echo "==> Setting up Python environment..."
cd "$INSTALL_DIR"
sudo uv venv /opt/hanipi/venv
sudo uv pip install --python /opt/hanipi/venv/bin/python \
  packages/rpi-agent packages/dashboard

echo "==> Creating directories..."
sudo mkdir -p "$DATA_DIR" "$CFG_DIR"
sudo chown hanipi:hanipi "$DATA_DIR"

echo "==> Writing default config..."
if [ ! -f "$CFG_DIR/hanipi.json" ]; then
  sudo tee "$CFG_DIR/hanipi.json" > /dev/null <<'HANIPI_JSON'
{
  "interval": 300,
  "sensors": [
    {
      "type": "hx711",
      "name": "Waage",
      "data_pin": 5,
      "clock_pin": 6,
      "reference_unit": 1000
    },
    {
      "type": "ds18b20",
      "name": "Temperatur_Innen"
    },
    {
      "type": "bme280",
      "name": "Aussenklima",
      "i2c_port": 1,
      "i2c_address": 118
    }
  ],
  "exporters": {
    "local": {
      "enabled": true,
      "db_path": "/var/lib/hanipi/data.db"
    }
  }
}
HANIPI_JSON
fi

echo "==> Installing systemd services..."
sudo cp "$INSTALL_DIR/packages/rpi-agent/systemd/hanipi-agent.service" /etc/systemd/system/
sudo cp "$INSTALL_DIR/packages/dashboard/systemd/hanipi-dashboard.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now hanipi-agent hanipi-dashboard

# Enable ModemManager for 4G sticks
sudo systemctl enable ModemManager
sudo systemctl start ModemManager || true

# Set avahi hostname for easy LAN access
if command -v hostnamectl &>/dev/null; then
  sudo hostnamectl set-hostname hanipi
fi

echo ""
echo "=========================================="
echo "  HaniPi installed successfully!"
echo "=========================================="
echo "  Dashboard: http://hanipi.local"
echo "  Config:    $CFG_DIR/hanipi.json"
echo "  Logs:      journalctl -u hanipi-agent -f"
echo ""
echo "  Supported sensors:"
echo "    hx711   - Waage (HX711 Load Cell)"
echo "    ds18b20 - Temperatur (1-Wire)"
echo "    bme280  - Temp/Feuchte/Druck (I2C)"
echo "    bme680  - Temp/Feuchte/Druck/Gas (I2C)"
echo "    bh1750  - Licht/Beleuchtung (I2C)"
echo "    ads1115 - ADC / Batteriespannung (I2C)"
echo ""
echo "  4G-Stick einrichten: sudo bash $INSTALL_DIR/packages/installer/setup_4g.sh"
echo "=========================================="
