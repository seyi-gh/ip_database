# IP Database

REST API to look up geolocation, ASN, and company data for any IPv4 address. Built with FastAPI, PostgreSQL, and Redis — runs locally and is exposed publicly through a shared reverse tunnel managed separately.

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.136-009688?style=flat&logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-17-4169E1?style=flat&logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-7-DC382D?style=flat&logo=redis&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat&logo=docker&logoColor=white)
![pandas](https://img.shields.io/badge/pandas-3.0-150458?style=flat&logo=pandas&logoColor=white)
![NumPy](https://img.shields.io/badge/NumPy-2.4-013243?style=flat&logo=numpy&logoColor=white)

## How it works

The project is split into three independent layers:

1. **Data pipeline** — raw CSV files from multiple IP databases are merged into a single `database.csv` using pandas and numpy. The merge uses vectorized binary search (`np.searchsorted`) to perform range-overlap joins across datasets with different range boundaries.

2. **Database** — `database.csv` is loaded into PostgreSQL via `COPY` (bulk import). Each IP range is stored with integer representations of `start_ip` and `end_ip`, which allows the query `WHERE start_int <= ? AND end_int >= ?` to use btree indexes efficiently.

3. **API** — FastAPI serves lookups over the PostgreSQL data. Redis handles per-IP rate limiting using an atomic increment + TTL pattern.

```
client → seyiwb.com/ip (HTTPS)
  → VPS nginx → autossh tunnel → Caddy:5050 (local router)
  → localhost:8000 (uvicorn)
  → PostgreSQL (rate limit via Redis)
```

The tunnel and Caddy are shared infrastructure — this service is just one of potentially many apps routed through the same tunnel. See the [tunnel section](#public-exposure-tunnel) for details.

---

## Requirements

- Python 3.11+
- Docker + Docker Compose

---

## Project structure

```
.
├── _loader/
│   ├── data/              # Raw CSV source files
│   └── loader.py          # Data pipeline: merge all sources → database.csv
├── _pg_import/
│   └── pg_import.py       # Bulk-loads database.csv into PostgreSQL
├── static/
│   └── index.html         # Landing page
├── main.py                # FastAPI app
├── exec.sh                # Start the API
├── loader.sh              # Run the data pipeline
├── import_to_postgres.sh  # Import CSV to PostgreSQL
├── install_service.sh     # Install systemd service for the API
├── ip-database.service    # systemd service for the API
├── docker-compose.yml     # PostgreSQL + Redis
├── .env.example           # Environment variable template
└── requirements.txt
```

---

## Setup

### 1. Install dependencies

```bash
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

```env
POSTGRES_USER=ip_user
POSTGRES_PASSWORD=your_password
POSTGRES_DB=ip_database
POSTGRES_HOST=localhost
POSTGRES_PORT=5477

REDIS_HOST=localhost
REDIS_PORT=6344

# Max requests per window per IP
RATE_LIMIT_REQUESTS=60
# Window duration in seconds
RATE_LIMIT_WINDOW=60
```

### 3. Start PostgreSQL and Redis

```bash
docker compose up -d
```

PostgreSQL runs on `5477` and Redis on `6344` — non-standard ports to avoid conflicts with other local projects.

### 4. (Optional) Regenerate the database

Only needed if you want to update or rebuild `database.csv` from the source files in `_loader/data/`:

```bash
./loader.sh
```

Merges all data sources using range-overlap joins and overwrites `database.csv` (~900MB, ~5.6M rows).

### 5. Import data into PostgreSQL

```bash
./import_to_postgres.sh
```

Uses PostgreSQL `COPY` for bulk loading. Creates indexes on `start_int` and `end_int` after import.

### 6. Start the API

```bash
./exec.sh
```

Available at `http://localhost:8000`.

---

## Running as a system service

```bash
./install_service.sh
```

Installs `ip-database.service`, which starts Docker containers, waits for them to be healthy, then launches uvicorn.

```bash
sudo systemctl status ip-database
sudo journalctl -u ip-database -f
```

---

## Public exposure (tunnel)

This service is exposed publicly via a shared autossh reverse tunnel that lives at `~/identity/tunnel.sh` — not in this repo. The tunnel connects the local machine to the VPS at `seyiwb.com` and is managed independently of any individual service.

```
~/identity/tunnel.sh         # autossh -R 9000:localhost:5050 littleshit@seyiwb.com
/etc/systemd/system/seyiwb-reverse-tunnel.service
```

Caddy runs locally on `:5050` and routes traffic by path. To expose this service, the Caddyfile entry is:

```
:5050 {
    handle /ip {
        rewrite * /
        reverse_proxy localhost:8000
    }
    handle /ip/* {
        reverse_proxy localhost:8000
    }
}
```

To add a new service at a different path, add another `handle` block pointing to its local port — the tunnel and VPS nginx don't change.

---

## Usage

### Landing page

```
GET /ip  →  seyiwb.com/ip
```

### Look up your own IP

```
GET /ip/me
```

```bash
curl https://seyiwb.com/ip/me
```

Detects the client IP from the request. When behind a proxy, reads `X-Forwarded-For`.

### Look up a specific IP

```
GET /ip/{ip}
```

```bash
curl https://seyiwb.com/ip/8.8.8.8
```

```json
{
  "ip": "8.8.8.8",
  "start_ip": "8.8.0.0",
  "end_ip": "8.8.31.255",
  "country": "US",
  "country_name": "United States",
  "continent": "NA",
  "continent_name": "North America",
  "region": "California",
  "city": "Mountain View",
  "postal_code": null,
  "latitude": 37.386,
  "longitude": -122.0838,
  "timezone": "America/Los_Angeles",
  "asn": 15169,
  "as_name": "Google LLC",
  "as_domain": "google.com",
  "company": null
}
```

### Health check

```
GET /health
```

---

## Security

### Rate limiting

Requests are limited per client IP using Redis. Defaults: 60 requests per 60 seconds. Configurable via `.env`.

Returns `429 Too Many Requests` with a `Retry-After` header when exceeded.

### Blocked IPs

Private, reserved, and non-routable addresses are rejected with `400 Bad Request`:

- `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16` — RFC 1918 private
- `127.0.0.0/8` — loopback
- `169.254.0.0/16` — link-local
- `224.0.0.0/4` — multicast
- `240.0.0.0/4`, `255.255.255.255/32` — reserved/broadcast

### Security headers

| Header | Value |
|---|---|
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `DENY` |
| `Referrer-Policy` | `no-referrer` |
| `X-Permitted-Cross-Domain-Policies` | `none` |
| `Cache-Control` | `no-store` |

---

## Data sources

The database is built by merging 8 source files using range-overlap joins. dbip takes priority for city-level data, with geolite2 as fallback.

| File | Content |
|---|---|
| `dbip-city-ipv4.csv` | City-level geolocation (primary) |
| `geolite2-city-ipv4.csv` | City-level geolocation (fallback) |
| `country_asn.csv` | Country, continent, and ASN info |
| `asn-ipv4.csv` | ASN to organization mapping |
| `geo-whois-asn-country-ipv4.csv` | Country fallback |
| `hpe.com_IP_Range_WL.csv` | HPE IP ranges |
| `webex.com_IP_Range_WL.csv` | Webex IP ranges |
| `microsoft_ip_range_20240129.txt` | Microsoft IP ranges |

> Free geolocation databases have variable accuracy by region. Coverage is generally better for North America and Europe.

---

## Stack

| Component | Technology |
|---|---|
| API | FastAPI + uvicorn |
| Database | PostgreSQL 17 |
| Cache / rate limit | Redis 7 |
| Data pipeline | pandas + numpy |
| Reverse proxy (local) | Caddy |
| Reverse proxy (VPS) | nginx + Let's Encrypt |
| Tunnel | autossh (shared, `~/identity/tunnel.sh`) |
| Process management | systemd |
