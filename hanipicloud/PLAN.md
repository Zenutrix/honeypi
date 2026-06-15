# HaniPi Cloud — Architektur & Umsetzungsplan

> **Status:** Planung  
> **Domain:** hanipicloud.hanimat.at  
> **Ziel:** Multi-User / Multi-Pi Cloud-Plattform für Bienenstock-Monitoring

---

## Übersicht

HaniPi Cloud ist eine selbst gehostete Cloud-Plattform, auf der Imker ihre HaniPi-Geräte registrieren und die Sensordaten zentral einsehen können. Jeder Imker kann mehrere Raspberry Pis an verschiedenen Standorten betreiben und alle Daten in einem einzigen Portal verwalten.

---

## Datenhierarchie

```
User (Imker)
 └── API-Key (1 pro Pi-Gerät)
      └── Standort (z.B. "Apfelgarten", "Waldlichtung")
           └── Hive / Bienenstock (Name + Farbe, vom Pi übermittelt)
                └── Sensordaten (Zeitreihe)
```

Ein Imker kann beliebig viele Pi-Geräte registrieren. Jedes Gerät bekommt einen eigenen API-Key und trägt einen Standortnamen. Hives und Sensorkonfiguration bleiben auf dem Pi — sie werden beim ersten Daten-Upload automatisch in der Cloud angelegt.

---

## Infrastruktur

### Server
- **Hardware:** Mini-PC mit Ryzen 7, 1 TB SSD, ≥16 GB RAM
- **OS:** Ubuntu Server (LTS)
- **Vor dem Server:** Nginx Proxy Manager (NPM) übernimmt SSL (Let's Encrypt) und Portweiterleitung

### Netzwerk / Ports
| Port | Wer | Wohin |
|------|-----|-------|
| 80 | NPM | HTTP → HTTPS Redirect |
| 443 | NPM | HTTPS → API intern |
| 8000 | Docker (nur 127.0.0.1) | FastAPI App |
| 5432 | Docker intern | PostgreSQL (nicht nach außen) |
| 6379 | Docker intern | Redis (nicht nach außen) |
| 22 | Ubuntu | SSH (nur Admin-IP) |

NPM proxied `hanipicloud.hanimat.at → 127.0.0.1:8000`.

### Docker Compose Services
```
api          FastAPI Anwendung         → :8000 (nur localhost)
postgres     PostgreSQL + TimescaleDB  → intern
redis        Session-Cache / Rate-Limit → intern
```

---

## Tech-Stack

| Schicht | Technologie | Begründung |
|---------|-------------|------------|
| Backend API | FastAPI (Python) | Gleiche Basis wie HaniPi-Agent |
| Datenbank | PostgreSQL 16 + TimescaleDB | Optimal für Zeitreihendaten, automatische Kompression |
| Cache / Sessions | Redis | JWT-Blacklist, Rate-Limiting |
| Frontend | Vanilla JS + CSS (wie HaniPi-Dashboard) | Kein Framework, mobile-first |
| Reverse Proxy | Nginx Proxy Manager (bereits vorhanden) | SSL-Terminierung, Let's Encrypt |
| Container | Docker Compose | Einfaches Deployment und Updates |

---

## Datenmodell

```sql
-- Benutzer
users (
  id            UUID PRIMARY KEY,
  email         TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  display_name  TEXT,
  is_active     BOOLEAN DEFAULT TRUE,
  is_admin      BOOLEAN DEFAULT FALSE,
  created_at    TIMESTAMPTZ DEFAULT NOW(),
  last_login    TIMESTAMPTZ
)

-- API-Keys (1 pro Pi-Gerät)
api_keys (
  id            UUID PRIMARY KEY,
  user_id       UUID REFERENCES users(id),
  name          TEXT NOT NULL,          -- z.B. "Apfelgarten Pi"
  location      TEXT NOT NULL,          -- Standortname frei wählbar
  key_hash      TEXT NOT NULL,          -- SHA-256 des Keys, Klartext nur einmal angezeigt
  key_prefix    TEXT NOT NULL,          -- erste 8 Zeichen zur Anzeige (z.B. "hpk_a3f9")
  is_active     BOOLEAN DEFAULT TRUE,
  created_at    TIMESTAMPTZ DEFAULT NOW(),
  last_seen     TIMESTAMPTZ
)

-- Hives (automatisch beim ersten Upload angelegt / aktualisiert)
hives (
  id            UUID PRIMARY KEY,
  api_key_id    UUID REFERENCES api_keys(id),
  remote_id     TEXT NOT NULL,          -- Hive-ID vom Pi
  name          TEXT NOT NULL,
  color         TEXT DEFAULT '#f59e0b',
  updated_at    TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(api_key_id, remote_id)
)

-- Messdaten (TimescaleDB Hypertable)
measurements (
  time          TIMESTAMPTZ NOT NULL,
  api_key_id    UUID NOT NULL,
  hive_id       UUID NOT NULL,
  sensor_name   TEXT NOT NULL,
  key           TEXT NOT NULL,          -- z.B. "weight_kg", "temperature_c"
  value         DOUBLE PRECISION NOT NULL
)
-- TimescaleDB: create_hypertable('measurements', 'time')
-- Kompression nach 7 Tagen, Retention Policy konfigurierbar

-- Admin-Einstellungen
settings (
  key           TEXT PRIMARY KEY,
  value         TEXT NOT NULL,
  updated_at    TIMESTAMPTZ DEFAULT NOW()
)
-- Beispiel-Keys: "retention_days", "max_keys_per_user", "registration_open"
```

---

## API-Endpunkte

### Authentifizierung (Web-User)
```
POST /auth/register          E-Mail + Passwort registrieren
POST /auth/login             JWT Token erhalten
POST /auth/logout            Token invalidieren (Redis Blacklist)
POST /auth/change-password
```

### API-Keys (Pi-Geräte verwalten)
```
GET    /api/keys             Alle Keys des eingeloggten Users
POST   /api/keys             Neuen Key erstellen (gibt Klartext einmalig zurück)
DELETE /api/keys/{id}        Key widerrufen
```

### Daten-Ingest (vom Pi, API-Key Auth)
```
POST /api/v1/ingest

Authorization: Bearer hpk_a3f9x2k1...
Content-Type: application/json

{
  "location": "Apfelgarten",
  "hives": [
    {
      "id": "uuid-vom-pi",
      "name": "Stock 1",
      "color": "#f59e0b",
      "readings": [
        { "sensor": "Waage_1", "key": "weight_kg",    "value": 24.7, "ts": 1718445600 },
        { "sensor": "Temp_1",  "key": "temperature_c","value": 32.1, "ts": 1718445600 }
      ]
    }
  ]
}
```

### Dashboard-Daten (Web-User, JWT Auth)
```
GET /dashboard/summary            Alle Standorte + letzte Werte
GET /dashboard/locations          Standortliste
GET /dashboard/{location}/hives   Hives eines Standorts
GET /dashboard/{location}/{hive}/history?hours=24&key=weight_kg   Verlauf
```

### Admin (nur Admin-User)
```
GET  /admin/users                 Alle User (Email, Pi-Anzahl, Datenmenge, Status)
POST /admin/users/{id}/block      User sperren
POST /admin/users/{id}/unblock    User entsperren
GET  /admin/stats                 Gesamtspeicher, aktive Pi's, Messwerte heute
GET  /admin/active-devices        Alle API-Keys mit last_seen
POST /admin/settings              Retention-Tage, Registrierung offen/geschlossen
```

---

## Daten-Ingest am Pi (neue Cloud-Exporter-Einstellung)

Im bestehenden HaniPi-Dashboard wird ein neuer Bereich "HaniPi Cloud" in den Einstellungen ergänzt:

```
Cloud-URL:  https://hanipicloud.hanimat.at
API-Key:    hpk_a3f9x2k1...
```

Im rpi-agent kommt ein neuer Exporter `cloud.py` — sendet die Daten nach jedem Mess-Zyklus an die Cloud-API. Kein weiterer Aufwand am Pi nötig.

---

## Admin Panel — Funktionen

| Funktion | Detail |
|----------|--------|
| User-Übersicht | Tabelle: E-Mail, Anzahl Pi's, Speicherverbrauch, letzter Upload, Aktiv/Gesperrt |
| Speicher gesamt | TimescaleDB Chunk-Größen, Gesamtgröße DB, freier Speicher |
| Aktive Pi's | API-Keys mit `last_seen` < 15 Min = grün, sonst grau/rot |
| Datenaufbewahrung | Globale Einstellung in Tagen (z.B. 1095 = 3 Jahre). TimescaleDB `drop_chunks` Policy |
| User sperren | `is_active = false` → Login + API-Key-Zugriff sofort gesperrt |
| Registrierung | Schalter: offen für alle / nur Einladung (Setting `registration_open`) |

---

## Web-Portal — Seiten

```
/                    → Login (wenn nicht eingeloggt)
/dashboard           → Übersicht alle Standorte + letzte Werte
/standort/:name      → Hives eines Standorts mit Live-Werten + Charts
/geraete             → API-Keys verwalten (erstellen, widerrufen)
/konto               → Passwort ändern, Account löschen
/admin               → Admin Panel (nur für Admin-User sichtbar)
```

Design: System Dark (identisch mit HaniPi-Dashboard, gleiche CSS-Variablen, gleiche Komponenten).

---

## Bauphasen

### Phase 1 — MVP
- [ ] Docker Compose Setup (FastAPI + PostgreSQL/TimescaleDB + Redis)
- [ ] Datenbankschema + TimescaleDB Hypertable
- [ ] Registrierung / Login / JWT
- [ ] API-Key Verwaltung (erstellen, widerrufen)
- [ ] Ingest-Endpunkt (Pi sendet Daten)
- [ ] Dashboard: Standorte → Hives → Live-Werte
- [ ] Einfache Zeitverlauf-Charts
- [ ] Cloud-Exporter im rpi-agent

### Phase 2 — Admin + Stabilität
- [ ] Admin Panel komplett
- [ ] Datenaufbewahrungs-Policy (TimescaleDB automatisch)
- [ ] User-Speicher-Übersicht
- [ ] Rate-Limiting auf Ingest-Endpunkt (Redis)
- [ ] Heartbeat / Pi-Status (last_seen)

### Phase 3 — Features
- [ ] Telegram-Benachrichtigungen aus der Cloud
- [ ] Vergleichsdiagramme (mehrere Stöcke / Standorte)
- [ ] CSV-Export
- [ ] E-Mail-Benachrichtigungen (SMTP)
- [ ] Einladungssystem (Registrierung nur per Link)

---

## Offene Entscheidungen

- [ ] Speicher-Limit pro User (z.B. 500 MB) oder erstmal unbegrenzt?
- [ ] Registrierung: sofort offen oder erst auf Einladung?
- [ ] E-Mail-Server (SMTP) für Passwort-Reset vorhanden?
- [ ] Backup-Strategie (täglicher DB-Dump, wohin?)
