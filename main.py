import os
import ipaddress
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from psycopg import AsyncConnection
from dotenv import load_dotenv
import redis.asyncio as aioredis

load_dotenv()

DSN = "postgresql://{user}:{password}@{host}:{port}/{db}".format(
  user     = os.environ['POSTGRES_USER'],
  password = os.environ['POSTGRES_PASSWORD'],
  host     = os.environ.get('POSTGRES_HOST', 'localhost'),
  port     = os.environ.get('POSTGRES_PORT', '5477'),
  db       = os.environ['POSTGRES_DB'],
)

RATE_LIMIT_REQUESTS = int(os.environ.get('RATE_LIMIT_REQUESTS', 60))
RATE_LIMIT_WINDOW   = int(os.environ.get('RATE_LIMIT_WINDOW', 60))

db:    AsyncConnection | None = None
cache: aioredis.Redis  | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
  global db, cache
  db = await AsyncConnection.connect(DSN)
  cache = aioredis.Redis(
    host = os.environ.get('REDIS_HOST', 'localhost'),
    port = int(os.environ.get('REDIS_PORT', 6344)),
    decode_responses = True,
  )
  yield
  await db.close()
  await cache.aclose()

SECURITY_HEADERS = {
  'X-Content-Type-Options': 'nosniff',
  'Referrer-Policy': 'no-referrer',
  'X-Permitted-Cross-Domain-Policies': 'none',
  'Cache-Control': 'no-store',
}

# RFC 1918, loopback, link-local, and other reserved blocks
RESERVED_NETWORKS = [
  ipaddress.ip_network('0.0.0.0/8'),
  ipaddress.ip_network('10.0.0.0/8'),
  ipaddress.ip_network('100.64.0.0/10'),
  ipaddress.ip_network('127.0.0.0/8'),
  ipaddress.ip_network('169.254.0.0/16'),
  ipaddress.ip_network('172.16.0.0/12'),
  ipaddress.ip_network('192.0.0.0/24'),
  ipaddress.ip_network('192.168.0.0/16'),
  ipaddress.ip_network('198.18.0.0/15'),
  ipaddress.ip_network('224.0.0.0/4'),
  ipaddress.ip_network('240.0.0.0/4'),
  ipaddress.ip_network('255.255.255.255/32'),
]

app = FastAPI(lifespan=lifespan)
app.add_middleware(
  CORSMiddleware,
  allow_origins=['*'],
  allow_methods=['GET'],
  allow_headers=['*'],
)
app.mount('/static', StaticFiles(directory=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')), name='static')


#? Middleware for rate limiting and helper functions
def client_ip(request: Request) -> str:
  return (
    request.headers.get('X-Real-IP') or
    request.headers.get('X-Forwarded-For', request.client.host).split(',')[0].strip()
  )

def assert_public_ip(ip: str):
  try:
    addr = ipaddress.ip_address(ip)
  except ValueError:
    raise HTTPException(status_code=400, detail=f'Invalid IP address: {ip}')
  if any(addr in net for net in RESERVED_NETWORKS):
    raise HTTPException(status_code=400, detail='Private or reserved IP addresses are not supported')

async def rate_limit(request: Request):
  ip  = client_ip(request)
  key = f'rl:{ip}'
  count = await cache.incr(key)
  if count == 1:
    await cache.expire(key, RATE_LIMIT_WINDOW)
  if count > RATE_LIMIT_REQUESTS:
    ttl = await cache.ttl(key)
    raise HTTPException(
      status_code = 429,
      detail      = f'Too many requests. Try again in {ttl}s.',
      headers     = { 'Retry-After': str(ttl) },
    )

@app.middleware('http')
async def security_middleware(request: Request, call_next):
  try:
    await rate_limit(request)
  except HTTPException as e:
    return JSONResponse(status_code=e.status_code, content={ 'detail': e.detail }, headers={ **e.headers, **SECURITY_HEADERS })
  response = await call_next(request)
  for k, v in SECURITY_HEADERS.items():
    response.headers[k] = v
  return response


#? Helpers for getting the columns right
COLS = ['start_ip', 'end_ip', 'country', 'country_name',
  'continent', 'continent_name', 'region', 'subregion',
  'city', 'postal_code', 'latitude', 'longitude', 'timezone',
  'asn', 'as_name', 'as_domain', 'company']

def ip_to_int(ip: str) -> int:
  try:
    return int(ipaddress.ip_address(ip))
  except ValueError:
    raise HTTPException(status_code=400, detail=f'Invalid IP address: {ip}')

async def query_ip(ip: str) -> dict:
  assert_public_ip(ip)
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


#? Main routes for production
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

@app.get('/')
@app.get('/ip')
async def index():
  return FileResponse(os.path.join(BASE_DIR, 'static', 'index.html'))

@app.get('/ip/health')
async def health():
  return { 'success': True, 'message': 'The app is working fine' }

@app.get('/ip/me')
async def lookup_self(request: Request):
  ip = client_ip(request)
  return await query_ip(ip)

@app.get('/ip/{ip}')
async def lookup(ip: str):
  return await query_ip(ip)
