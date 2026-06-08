# IP Database

REST API to look up geolocation, ASN, and company data for any IPv4 address.

## Requirements

- Python 3.11+
- Docker + Docker Compose

---

## Setup

### 1. Install dependencies

```bash
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

### 2. Configure environment

Copy the example and fill in your values:

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

Wait a few seconds for the services to initialize.

### 4. (Optional) Regenerate the database

Only needed if you want to update or rebuild `database.csv` from the source files in `_loader/data/`:

```bash
./loader.sh
```

This will overwrite `database.csv` in the project root.

### 5. Import data into PostgreSQL

Loads `database.csv` into the database. Run this on first setup or after regenerating the CSV:

```bash
./import_to_postgres.sh
```

This will take a few minutes depending on your hardware (~5.6M rows).

### 6. Start the API

```bash
./exec.sh
```

The API will be available at `http://localhost:8000`.

---

## Usage

### Look up your own IP

Automatically detects the IP of the incoming request:

```
GET /ip
```

```bash
curl http://localhost:8000/ip
```

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

```bash
curl http://localhost:8000/health
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
