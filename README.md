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
```

### 3. Start PostgreSQL

```bash
docker compose up -d
```

Wait a few seconds for the database to initialize.

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

### Look up an IP

```
GET /ip/{ip}
```

```bash
curl http://localhost:8000/ip/8.8.8.8
```

```json
{
  "ip": "8.8.8.8",
  "country": "US",
  "country_name": "United States",
  "continent": "NA",
  "continent_name": "North America",
  "region": "California",
  "city": "Mountain View",
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