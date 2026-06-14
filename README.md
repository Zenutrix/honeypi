# HoneyPi

Modern Raspberry Pi beehive monitoring system.

- **rpi-agent**: Sensor data collection + modular exporters (ThingSpeak, InfluxDB, MQTT, local)
- **dashboard**: Local web dashboard at `http://honeypi.local` (FastAPI + Chart.js)
- **installer**: One-command setup for Raspberry Pi OS Lite

## Quick Install

```bash
curl -sSL https://raw.githubusercontent.com/Zenutrix/honeypi/main/packages/installer/install.sh | bash
```

## Documentation

See `docs/` for design spec and implementation plan.
