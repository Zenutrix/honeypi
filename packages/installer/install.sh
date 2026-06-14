#!/usr/bin/env bash
set -euo pipefail

REPO="https://github.com/Zenutrix/honeypi"
INSTALL_DIR="/opt/honeypi"
DATA_DIR="/var/lib/honeypi"
CFG_DIR="/etc/honeypi"

echo "==> HoneyPi Installer"
echo "==> Updating system packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
  git python3 python3-pip python3-dev \
  avahi-daemon \
  i2c-tools \
  libgpiod2 python3-libgpiod \
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

echo "==> Creating honeypi user..."
id -u honeypi &>/dev/null || sudo useradd --system --no-create-home honeypi

# Add honeypi user to i2c and gpio groups for sensor access
sudo usermod -aG i2c,gpio,dialout honeypi 2>/dev/null || true

echo "==> Setting up Python environment..."
cd "$INSTALL_DIR"
sudo uv venv /opt/honeypi/venv
sudo uv pip install --python /opt/honeypi/venv/bin/python \
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
      "i2c_address": "0x76"
    }
  ],
  "exporters": {
    "local": {
      "enabled": true,
      "db_path": "/var/lib/honeypi/data.db"
    }
  }
}
HONEYPI_JSON
fi

echo "==> Installing systemd services..."
sudo cp "$INSTALL_DIR/packages/rpi-agent/systemd/honeypi-agent.service" /etc/systemd/system/
sudo cp "$INSTALL_DIR/packages/dashboard/systemd/honeypi-dashboard.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now honeypi-agent honeypi-dashboard

# Enable ModemManager for 4G sticks
sudo systemctl enable ModemManager
sudo systemctl start ModemManager || true

echo ""
echo "=========================================="
echo "  HoneyPi installed successfully!"
echo "=========================================="
echo "  Dashboard: http://honeypi.local"
echo "  Config:    $CFG_DIR/honeypi.json"
echo "  Logs:      journalctl -u honeypi-agent -f"
echo ""
echo "  Supported sensors:"
echo "    hx711   - Waage (HX711 Load Cell)"
echo "    ds18b20 - Temperatur (1-Wire)"
echo "    bme280  - Temp/Feuchte/Druck (I2C)"
echo "    bme680  - Temp/Feuchte/Druck/Gas (I2C)"
echo "    dht22   - Temp/Feuchte (GPIO)"
echo "    dht11   - Temp/Feuchte (GPIO)"
echo "    sht31   - Temp/Feuchte präzise (I2C)"
echo "    aht10   - Temp/Feuchte (I2C)"
echo "    bh1750  - Licht/Beleuchtung (I2C)"
echo "    ads1115 - ADC / Batteriespannung (I2C)"
echo ""
echo "  4G-Stick einrichten: sudo bash $INSTALL_DIR/packages/installer/setup_4g.sh"
echo "=========================================="
