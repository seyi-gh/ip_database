import os
import psycopg
from dotenv import load_dotenv

load_dotenv()

DSN = "postgresql://{user}:{password}@{host}:{port}/{db}".format(
  user     = os.environ['POSTGRES_USER'],
  password = os.environ['POSTGRES_PASSWORD'],
  host     = os.environ.get('POSTGRES_HOST', 'localhost'),
  port     = os.environ.get('POSTGRES_PORT', '5477'),
  db       = os.environ['POSTGRES_DB'],
)
CSV = os.path.join(os.path.dirname(__file__), '..', 'database.csv')
CSV = os.path.normpath(os.path.abspath(CSV))

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS ip_ranges (
  start_ip       TEXT        NOT NULL,
  end_ip         TEXT        NOT NULL,
  start_int      BIGINT      NOT NULL,
  end_int        BIGINT      NOT NULL,
  country        TEXT,
  region         TEXT,
  subregion      TEXT,
  city           TEXT,
  postal_code    TEXT,
  latitude       DOUBLE PRECISION,
  longitude      DOUBLE PRECISION,
  timezone       TEXT,
  asn            BIGINT,
  as_name        TEXT,
  country_name   TEXT,
  continent      TEXT,
  continent_name TEXT,
  as_domain      TEXT,
  company        TEXT
);
"""

CREATE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_ip_ranges_start ON ip_ranges (start_int);
CREATE INDEX IF NOT EXISTS idx_ip_ranges_end   ON ip_ranges (end_int);
"""

def main():
  print(f'> Connecting to {DSN}')
  with psycopg.connect(DSN) as conn:
    with conn.cursor() as cur:
      print('> Creating table...')
      cur.execute(CREATE_TABLE)

      print('> Truncating existing data...')
      cur.execute('TRUNCATE TABLE ip_ranges;')

      print(f'> Loading {CSV}...')
      with open(CSV, 'r') as f:
        next(f)  # skip header
        with cur.copy("""
          COPY ip_ranges (
            start_ip, end_ip, start_int, end_int,
            country, region, subregion, city, postal_code,
            latitude, longitude, timezone,
            asn, as_name, country_name, continent, continent_name,
            as_domain, company
          )
          FROM STDIN WITH (FORMAT csv, NULL '')
        """) as copy:
          for line in f:
            copy.write(line)

      print('> Creating indexes...')
      cur.execute(CREATE_INDEX)

    conn.commit()
  print('> Done.')

if __name__ == '__main__':
  main()
