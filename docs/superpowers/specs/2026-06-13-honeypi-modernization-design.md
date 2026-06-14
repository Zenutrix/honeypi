# HoneyPi Modernization — Design Spec

**Datum:** 2026-06-13  
**Autor:** Thomas + Claude  
**Status:** Genehmigt

---

## Ziel

Fork des bestehenden HoneyPi-Projekts als kompletter Neustart in einem einzigen GitHub-Monorepo. Ziel ist die Wiederbelebung des Projekts mit modernem Tech-Stack, lokalem Dashboard auf dem Pi und einem modularen Exporter-System das ThingSpeak, InfluxDB, MQTT und weitere Backends unterstützt.

---

## Monorepo-Struktur

```
honeypi/
├── packages/
│   ├── rpi-agent/      # Python-Sensor-Agent + Exporter-System
│   ├── dashboard/      # FastAPI + Chart.js lokale Web-UI
│   └── installer/      # Shell-Skript für Pi-Einrichtung
├── docs/               # Dokumentation & Setup-Guides
└── .github/
    └── workflows/      # CI: Tests, Linting, Release-Build
```

Ein `git clone` + ein Installer-Befehl richtet das gesamte System ein.

---

## Package: `rpi-agent`

### Tech-Stack
- Python 3.11+
- `uv` als Package-Manager
- Vollständig typisiert (mypy-kompatibel)
- systemd-Service

### Sensor-Treiber

Alle bestehenden Treiber aus `Honey-Pi/rpi-scripts` werden portiert:

| Sensor | Protokoll | Messgröße |
|--------|-----------|-----------|
| HX711 | GPIO | Gewicht |
| DS18B20 | 1-Wire | Temperatur |
| DHT11/22 | GPIO | Temperatur, Feuchte |
| BME280 | I2C | Temperatur, Feuchte, Druck |
| BME680 | I2C | Temperatur, Feuchte, Druck, Gas |
| SHT31 | I2C | Temperatur, Feuchte |
| BH1750 | I2C | Licht |
| GPS | UART | Position |
| AHT10 | I2C | Temperatur, Feuchte |

### Exporter-Plugin-System

```
rpi-agent/
├── sensors/
│   ├── base.py          # Abstrakte Sensor-Basisklasse
│   ├── hx711.py
│   ├── ds18b20.py
│   ├── bme280.py
│   └── ...
├── exporters/
│   ├── base.py          # Abstrakte Exporter-Basisklasse
│   ├── local.py         # SQLite lokal (Pflicht, für Dashboard)
│   ├── thingspeak.py    # ThingSpeak HTTP API
│   ├── influxdb.py      # InfluxDB v2 HTTP API
│   ├── mqtt.py          # MQTT (→ Home Assistant, Node-RED, Grafana)
│   └── adafruit_io.py   # Adafruit IO (kostenloser Tier)
├── config.py            # Liest honeypi.json
└── main.py              # Hauptschleife
```

**Exporter-Prinzip:** Mehrere Exporter können gleichzeitig aktiv sein. Ein Fehler in einem Exporter bricht die anderen nicht ab. Alle Exporter werden über `honeypi.json` konfiguriert und aktiviert.

### Konfiguration (`honeypi.json`)

```json
{
  "interval": 300,
  "sensors": [
    { "type": "hx711", "name": "Stockgewicht", "data_pin": 5, "clock_pin": 6 },
    { "type": "ds18b20", "name": "Innentemperatur" }
  ],
  "exporters": {
    "local": { "enabled": true },
    "thingspeak": {
      "enabled": false,
      "api_key": ""
    },
    "influxdb": {
      "enabled": false,
      "url": "http://my-server:8086",
      "token": "",
      "org": "",
      "bucket": "honeypi"
    },
    "mqtt": {
      "enabled": false,
      "broker": "192.168.1.100",
      "port": 1883,
      "topic": "honeypi/hive1"
    }
  }
}
```

---

## Package: `dashboard`

### Tech-Stack
- FastAPI + uvicorn (Python, leichtgewichtig)
- Chart.js (Grafiken, kein Framework-Overhead)
- Vanilla HTML/CSS/JS (kein Build-Schritt nötig)
- SQLite als Datenquelle (geschrieben von `local`-Exporter)
- systemd-Service, erreichbar unter `http://honeypi.local`

### Features
- Live-Anzeige aktueller Messwerte
- Verlaufsgraphen (Gewicht, Temperatur, Feuchte) mit wählbarem Zeitraum
- Konfigurationsseite: Sensoren, Exporter, Messintervall (ersetzt das alte Angular-Webinterface)
- Steuerung: Start/Stop/Restart des `rpi-agent`, Reboot, Shutdown
- Mobilfreundlich (responsive)

### Struktur

```
dashboard/
├── main.py          # FastAPI-App + Endpunkte
├── api/
│   ├── data.py      # GET /api/data (aktuelle + historische Werte)
│   └── config.py    # GET/POST /api/config
├── db.py            # SQLite-Lesezugriff
└── static/
    ├── index.html   # Dashboard-Seite
    ├── config.html  # Konfigurations-Seite
    ├── app.js       # Chart.js + fetch-Logik
    └── style.css
```

---

## Package: `installer`

Ein einzelner Shell-Befehl richtet das gesamte System auf einem frischen Raspberry Pi OS Lite ein:

```bash
curl -sSL https://raw.githubusercontent.com/Zenutrix/honeypi/main/install.sh | bash
```

### Was der Installer tut
1. System-Pakete aktualisieren
2. Python 3.11+ + `uv` installieren
3. Repository klonen
4. Python-Abhängigkeiten installieren
5. Initiale `honeypi.json` erstellen
6. Zwei systemd-Services registrieren und starten:
   - `honeypi-agent.service`
   - `honeypi-dashboard.service`
7. mDNS (`honeypi.local`) konfigurieren

---

## CI/CD (`.github/workflows/`)

| Workflow | Trigger | Aufgabe |
|----------|---------|---------|
| `test.yml` | Push / PR | mypy + pytest für rpi-agent und dashboard |
| `lint.yml` | Push / PR | ruff (Python linting) |
| `release.yml` | Tag `v*` | GitHub Release erstellen |

---

## Phasenplan

| Phase | Inhalt |
|-------|--------|
| 1 | Monorepo-Setup, GitHub Fork, Grundstruktur |
| 2 | `rpi-agent`: Kern + Sensor-Treiber + `local`-Exporter |
| 3 | `rpi-agent`: ThingSpeak + InfluxDB + MQTT Exporter |
| 4 | `dashboard`: FastAPI + Chart.js + Konfigurations-UI |
| 5 | `installer`: Ein-Befehl-Setup |
| 6 | Docs, CI/CD, erstes GitHub Release |

---

## Nicht im Scope (bewusst ausgelassen)

- Mobile Native App (PWA reicht)
- LoRaWAN-Support (kann später als Exporter ergänzt werden)
- KI/ML-Auswertung
- Multi-Bienenstock-Management (separate Instanz pro Stock)
