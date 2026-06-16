#!/usr/bin/env bash
set -euo pipefail

REPO="https://github.com/Zenutrix/HaniPi"
RAW_UPDATE_URL="https://raw.githubusercontent.com/Zenutrix/HaniPi/main/packages/installer/update.sh"
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
  network-manager \
  modemmanager usb-modeswitch usb-modeswitch-data \
  build-essential swig liblgpio-dev fonts-dejavu-core

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
sudo usermod -aG i2c,gpio,dialout,netdev,video,input,render hanipi 2>/dev/null || true

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
sudo chown hanipi:hanipi "$DATA_DIR" "$CFG_DIR"

echo "==> Writing default config..."
if [ ! -f "$CFG_DIR/hanipi.json" ]; then
  sudo tee "$CFG_DIR/hanipi.json" > /dev/null <<'HANIPI_JSON'
{
  "interval": 300,
  "sensors": [],
  "exporters": {
    "local": {
      "enabled": true,
      "db_path": "/var/lib/hanipi/data.db"
    }
  }
}
HANIPI_JSON
fi

echo "==> Setting up HaniPi-Wartung hotspot connection..."
if ! sudo nmcli connection show "HaniPi-Wartung" &>/dev/null; then
  sudo nmcli connection add \
    type wifi \
    con-name "HaniPi-Wartung" \
    ssid "HaniPi-Setup" \
    ifname wlan0 \
    mode ap \
    ipv4.method shared \
    ipv4.addresses "10.42.0.1/24" \
    wifi-sec.key-mgmt wpa-psk \
    wifi-sec.psk "hanipi123" \
    connection.autoconnect no
  echo "    Hotspot 'HaniPi-Setup' (SSID) created, password: hanipi123"
else
  echo "    HaniPi-Wartung connection already exists – skipping"
fi

echo "==> Erstelle 'hanipi-update' Befehl..."
sudo tee /usr/local/bin/hanipi-update > /dev/null <<HANIPI_UPDATE_WRAPPER
#!/usr/bin/env bash
set -euo pipefail
# Holt update.sh immer frisch von GitHub statt einer lokalen, ggf. veralteten Kopie -
# so laeuft bei jedem Aufruf garantiert die aktuelle Update-Logik.
curl -fsSL "$RAW_UPDATE_URL" | sudo bash
HANIPI_UPDATE_WRAPPER
sudo chmod +x /usr/local/bin/hanipi-update

echo "==> Installing systemd services..."
sudo cp "$INSTALL_DIR/packages/rpi-agent/systemd/hanipi-agent.service" /etc/systemd/system/
sudo cp "$INSTALL_DIR/packages/dashboard/systemd/hanipi-dashboard.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now hanipi-agent hanipi-dashboard

# Enable ModemManager for 4G sticks
sudo systemctl enable ModemManager
sudo systemctl start ModemManager || true

# Cursor auf Framebuffer permanent deaktivieren (kein blinkender Cursor)
CMDLINE="/boot/firmware/cmdline.txt"
[ -f "$CMDLINE" ] || CMDLINE="/boot/cmdline.txt"
if ! grep -q "vt.global_cursor_default=0" "$CMDLINE" 2>/dev/null; then
  sudo sed -i 's/$/ vt.global_cursor_default=0 loglevel=3 logo.nologo/' "$CMDLINE"
fi

# Disable login prompt on HDMI (tty1) so display can take over
sudo systemctl disable getty@tty1 2>/dev/null || true
sudo mkdir -p /etc/systemd/system/getty@tty1.service.d
sudo tee /etc/systemd/system/getty@tty1.service.d/override.conf > /dev/null <<'GETTY_OVERRIDE'
[Service]
ExecStart=
ExecStart=-/bin/sleep infinity
GETTY_OVERRIDE

# Allow hanipi to write to framebuffer
echo 'SUBSYSTEM=="graphics", KERNEL=="fb*", GROUP="video", MODE="0660"' | \
  sudo tee /etc/udev/rules.d/99-hanipi-fb.rules > /dev/null

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
echo "  Update:    sudo hanipi-update   (holt update.sh immer frisch von GitHub)"
echo ""
echo "  Supported sensors:"
echo "    hx711   - Waage (HX711 Load Cell)"
echo "    ds18b20 - Temperatur (1-Wire)"
echo "    bme280  - Temp/Feuchte/Druck (I2C)"
echo "    bme680  - Temp/Feuchte/Druck/Gas (I2C)"
echo "    bh1750  - Licht/Beleuchtung (I2C)"
echo "    ads1115 - ADC / Batteriespannung (I2C)"
echo ""
echo "  Wartungs-Hotspot: SSID 'HaniPi-Setup', PW: hanipi123"
echo "  4G-Stick einrichten: sudo bash $INSTALL_DIR/packages/installer/setup_4g.sh"
echo "=========================================="
