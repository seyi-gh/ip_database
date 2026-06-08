import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from psycopg import AsyncConnection
from dotenv import load_dotenv

load_dotenv()

DSN = "postgresql://{user}:{password}@{host}:{port}/{db}".format(
  user     = os.environ['POSTGRES_USER'],
  password = os.environ['POSTGRES_PASSWORD'],
  host     = os.environ.get('POSTGRES_HOST', 'localhost'),
  port     = os.environ.get('POSTGRES_PORT', '5477'),
  db       = os.environ['POSTGRES_DB'],
)

db: AsyncConnection | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
  global db
  db = await AsyncConnection.connect(DSN)
  yield
  await db.close()

app = FastAPI(lifespan=lifespan)

@app.get('/health')
async def health():
  return { 'success': True, 'message': 'The app is working fine' }

COLS = ['start_ip', 'end_ip', 'country', 'country_name',
  'continent', 'continent_name', 'region', 'subregion',
  'city', 'postal_code', 'latitude', 'longitude', 'timezone',
  'asn', 'as_name', 'as_domain', 'company']

async def query_ip(ip: str) -> dict:
  async with db.cursor() as cur:
    await cur.execute("""
      SELECT
        start_ip, end_ip, country, country_name,
        continent, continent_name, region, subregion,
        city, postal_code, latitude, longitude, timezone,
        asn, as_name, as_domain, company
      FROM ip_ranges
      WHERE start_int <= %s AND end_int >= %s
      LIMIT 1
    """, (ip_to_int(ip), ip_to_int(ip)))
    row = await cur.fetchone()

  if not row:
    raise HTTPException(status_code=404, detail='IP not found')

  return { 'ip': ip, **dict(zip(COLS, row)) }

@app.get('/ip')
async def lookup_self(request: Request):
  ip = request.headers.get('X-Forwarded-For', request.client.host).split(',')[0].strip()
  return await query_ip(ip)

@app.get('/ip/{ip}')
async def lookup(ip: str):
  return await query_ip(ip)

def ip_to_int(ip: str) -> int:
  import ipaddress
  return int(ipaddress.ip_address(ip))