# IP Database

REST API to look up geolocation, ASN, and company data for any IPv4 address. Built with FastAPI, PostgreSQL, and Redis — designed to run locally and be exposed publicly through a secure reverse tunnel.

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.136-009688?style=flat&logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-17-4169E1?style=flat&logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-7-DC382D?style=flat&logo=redis&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat&logo=docker&logoColor=white)
![nginx](https://img.shields.io/badge/nginx-1.26-009639?style=flat&logo=nginx&logoColor=white)
![pandas](https://img.shields.io/badge/pandas-3.0-150458?style=flat&logo=pandas&logoColor=white)
![NumPy](https://img.shields.io/badge/NumPy-2.4-013243?style=flat&logo=numpy&logoColor=white)

## How it works

The project is split into three independent layers:

1. **Data pipeline** — raw CSV files from multiple IP databases are merged into a single `database.csv` using pandas and numpy. The merge uses vectorized binary search (`np.searchsorted`) to perform range-overlap joins across datasets with different range boundaries — much faster than row-by-row lookups.

2. **Database** — `database.csv` is loaded into PostgreSQL via `COPY` (bulk import). Each IP range is stored with integer representations of `start_ip` and `end_ip`, which allows the query `WHERE start_int <= ? AND end_int >= ?` to use btree indexes efficiently.

3. **API** — FastAPI serves lookups over the PostgreSQL data. Redis handles per-IP rate limiting using an atomic increment + TTL pattern. The API runs locally and is exposed publicly through an autossh reverse tunnel to a VPS running nginx with HTTPS.

```
client → nginx (VPS, HTTPS :8000) → SSH tunnel → uvicorn (local :8000) → PostgreSQL
                                                                         ↑
                                                                       Redis (rate limit)
```

---

## Requirements

- Python 3.11+
- Docker + Docker Compose
- autossh (for the tunnel)

---

## Project structure

```
.
├── _loader/
│   ├── data/          # Raw CSV source files
│   └── loader.py      # Data pipeline: merge all sources → database.csv
├── _pg_import/
│   └── pg_import.py   # Bulk-loads database.csv into PostgreSQL
├── static/
│   └── index.html     # Landing page
├── main.py            # FastAPI app
├── exec.sh            # Start the API
├── loader.sh          # Run the data pipeline
├── import_to_postgres.sh  # Import CSV to PostgreSQL
├── install_service.sh # Install systemd service for the API
├── tunnel.sh          # autossh reverse tunnel
├── tunnel.service     # systemd service for the tunnel
├── ip-database.service # systemd service for the API
├── docker-compose.yml # PostgreSQL + Redis
├── .env.example       # Environment variable template
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

Wait a few seconds for the services to initialize. PostgreSQL runs on port `5477` and Redis on `6344` — non-standard ports to avoid conflicts when running multiple projects on the same machine.

### 4. (Optional) Regenerate the database

Only needed if you want to update or rebuild `database.csv` from the source files in `_loader/data/`:

```bash
./loader.sh
```

This merges all data sources using range-overlap joins and overwrites `database.csv` in the project root (~900MB, ~5.6M rows).

### 5. Import data into PostgreSQL

```bash
./import_to_postgres.sh
```

Uses PostgreSQL `COPY` for bulk loading — much faster than row-by-row inserts. Creates indexes on `start_int` and `end_int` after import. Takes a few minutes depending on hardware.

### 6. Start the API

```bash
./exec.sh
```

The API will be available at `http://localhost:8000`. The landing page is at `http://localhost:8000/`.

---

## Running as a system service

To start the API automatically on boot:

```bash
./install_service.sh
```

This installs and enables `ip-database.service`, which starts Docker containers, waits for them to be healthy, then launches uvicorn.

To check status or logs:

```bash
sudo systemctl status ip-database
sudo journalctl -u ip-database -f
```

---

## Reverse tunnel (public exposure)

The API runs locally and is exposed publicly via an autossh reverse tunnel. The tunnel forwards `VPS:5050 → localhost:8000`, and nginx on the VPS proxies `seyiwb.com:8000 → 127.0.0.1:5050` over HTTPS.

Start the tunnel manually:

```bash
./tunnel.sh
```

Or install it as a service to start on boot:

```bash
sudo cp tunnel.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now tunnel
```

---

## Usage

### Landing page

```
GET /
```

Opens the interactive landing page with a live IP lookup demo.

### Look up your own IP

```
GET /ip
```

```bash
curl http://localhost:8000/ip
```

Automatically detects the client IP from the request. When behind a proxy, reads `X-Forwarded-For`.

### Look up a specific IP

```
GET /ip/{ip}
```

```bash
curl http://localhost:8000/ip/8.8.8.8
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

When the limit is exceeded the API returns `429 Too Many Requests` with a `Retry-After` header indicating how many seconds to wait.

### Blocked IPs

Private, reserved, and non-routable addresses are rejected with `400 Bad Request`:

- `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16` — RFC 1918 private
- `127.0.0.0/8` — loopback
- `169.254.0.0/16` — link-local
- `224.0.0.0/4` — multicast
- `240.0.0.0/4`, `255.255.255.255/32` — reserved/broadcast

### Security headers

All responses include:

| Header | Value |
|---|---|
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `DENY` |
| `Referrer-Policy` | `no-referrer` |
| `X-Permitted-Cross-Domain-Policies` | `none` |
| `Cache-Control` | `no-store` |

---

## Data sources

The database is built by merging 8 source files using range-overlap joins. dbip takes priority for city-level data, with geolite2 as fallback. ASN and country data is enriched from separate sources that may use different range boundaries.

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

> **Note:** Free geolocation databases have variable accuracy by region. Coverage is generally better for North America and Europe than for Latin America, Africa, and parts of Asia.

---

## Stack

| Component | Technology |
|---|---|
| API | FastAPI + uvicorn |
| Database | PostgreSQL 17 |
| Cache / rate limit | Redis 7 |
| Data pipeline | pandas + numpy |
| Tunnel | autossh |
| Reverse proxy | nginx + Let's Encrypt |
| Process management | systemd |
