import pandas as pd
import ipaddress
import bisect
import numpy as np


#? Helper functions to convert the ips from csv to searching formats
def ip_to_int(ip: str) -> int:
  return int(ipaddress.ip_address(ip))

def cidr_to_range(cidr: str):
  net = ipaddress.ip_network(cidr, strict=False)
  return int(net.network_address), int(net.broadcast_address)


#? Loaders functions (The creme)
def load_asn_ipv4():
  df = pd.read_csv('./_loader/data/asn-ipv4.csv', header=None,
    names=['start_ip', 'end_ip', 'asn', 'as_name'])
  df['start_int'] = df['start_ip'].apply(ip_to_int)
  df['end_int']   = df['end_ip'].apply(ip_to_int)
  return df

def load_country_asn():
  df = pd.read_csv('./_loader/data/country_asn.csv')
  # only ipv4 rows (skip ipv6)
  df = df[~df['start_ip'].str.contains(':')]
  df['start_int'] = df['start_ip'].apply(ip_to_int)
  df['end_int']   = df['end_ip'].apply(ip_to_int)
  return df

def load_dbip_city():
  df = pd.read_csv('./_loader/data/dbip-city-ipv4.csv', header=None,
    names=['start_ip', 'end_ip', 'country', 'region',
      'subregion', 'city', 'postal_code',
      'latitude', 'longitude', 'timezone'])
  df['start_int'] = df['start_ip'].apply(ip_to_int)
  df['end_int']   = df['end_ip'].apply(ip_to_int)
  return df

def load_geolite2_city():
  df = pd.read_csv('./_loader/data/geolite2-city-ipv4.csv', header=None,
    names=['start_ip', 'end_ip', 'country', 'region',
      'subregion', 'city', 'postal_code',
      'latitude', 'longitude', 'timezone'])
  df['start_int'] = df['start_ip'].apply(ip_to_int)
  df['end_int']   = df['end_ip'].apply(ip_to_int)
  return df

def load_geo_whois():
  df = pd.read_csv('./_loader/data/geo-whois-asn-country-ipv4.csv', header=None,
    names=['start_ip', 'end_ip', 'country'])
  df['start_int'] = df['start_ip'].apply(ip_to_int)
  df['end_int']   = df['end_ip'].apply(ip_to_int)
  return df

def load_hpe():
  df = pd.read_csv('./_loader/data/hpe.com_IP_Range_WL.csv')
  ranges = df['dest_ip'].apply(cidr_to_range)
  df['start_int'] = ranges.apply(lambda x: x[0])
  df['end_int']   = ranges.apply(lambda x: x[1])
  df = df.rename(columns={'metadata.company': 'company', 'metadata.date': 'date'})
  return df[['start_int', 'end_int', 'company', 'date', 'dest_ip']]

def load_webex():
  df = pd.read_csv('./_loader/data/webex.com_IP_Range_WL.csv')
  ranges = df['dest_ip'].apply(cidr_to_range)
  df['start_int'] = ranges.apply(lambda x: x[0])
  df['end_int']   = ranges.apply(lambda x: x[1])
  df = df.rename(columns={'metadata.company': 'company', 'metadata.date': 'date'})
  return df[['start_int', 'end_int', 'company', 'date', 'dest_ip']]

def load_microsoft():
  with open('./_loader/data/microsoft_ip_range_20240129.txt') as f:
    cidrs = [l.strip() for l in f if l.strip()]
  ranges = [cidr_to_range(c) for c in cidrs]
  df = pd.DataFrame(ranges, columns=['start_int', 'end_int'])
  df['company'] = 'microsoft.com'
  return df


#? Functions to look for the ips correctly for all the data
def build_lookup(df: pd.DataFrame) -> tuple[pd.DataFrame, list]:
  df = df.sort_values('start_int').reset_index(drop=True)
  starts = df['start_int'].tolist()
  return df, starts

def lookup_ip(ip: str, lookup_df: pd.DataFrame, starts: list, cols: list[str]) -> dict:
  ip_int = ip_to_int(ip)
  # find the rightmost start_int <= ip_int
  idx = bisect.bisect_right(starts, ip_int) - 1
  if idx < 0:
    return {}
  row = lookup_df.iloc[idx]
  if row['end_int'] >= ip_int:
    return row[cols].to_dict()
  return {}


#? Merge all for a single ip
def enrich_ip(ip: str, sources: dict) -> dict:
  result = {'ip': ip}
  for _, (df, starts, cols) in sources.items():
    match = lookup_ip(ip, df, starts, cols)
    result.update(match)
  return result


#? Build all the file, the main export
def range_join(base: pd.DataFrame, other: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
  other_s = other.sort_values('start_int').reset_index(drop=True)
  starts  = other_s['start_int'].to_numpy()
  ends    = other_s['end_int'].to_numpy()
  probes  = base['start_int'].to_numpy()

  # for each probe find the rightmost start <= probe (vectorized binary search)
  idx = np.searchsorted(starts, probes, side='right') - 1

  # mask rows where no range contains the probe
  valid = (idx >= 0) & (ends[np.maximum(idx, 0)] >= probes)

  base = base.copy()
  for c in cols:
    values = other_s[c].to_numpy(dtype=object)
    col_vals = np.where(valid, values[np.maximum(idx, 0)], None)
    base[c] = col_vals

  return base


def build_combined() -> pd.DataFrame:
  # geo: prefer dbip, fall back to geolite2
  dbip = load_dbip_city()
  geo2 = load_geolite2_city()
  geo_cols = ['start_ip', 'end_ip', 'start_int', 'end_int',
    'country', 'region', 'subregion', 'city', 'postal_code',
    'latitude', 'longitude', 'timezone']
  city = pd.concat([dbip[geo_cols], geo2[geo_cols]], ignore_index=True)
  city = city.drop_duplicates(subset=['start_int', 'end_int'], keep='first')

  asn   = load_asn_ipv4()[['start_int', 'end_int', 'asn', 'as_name']]
  casn  = load_country_asn()[['start_int', 'end_int',
    'country_name', 'continent', 'continent_name', 'asn', 'as_name', 'as_domain']]
  whois = load_geo_whois()[['start_int', 'end_int', 'country']]
  companies = pd.concat([load_hpe(), load_webex(), load_microsoft()], ignore_index=True)
  companies = companies[['start_int', 'end_int', 'company']]

  merged = range_join(city, asn,  ['asn', 'as_name'])
  merged = range_join(merged, casn, ['country_name', 'continent', 'continent_name', 'as_domain'])

  # whois as country fallback rename to avoid collision then coalesce
  whois = whois.rename(columns={'country': 'country_whois'})
  merged = range_join(merged, whois, ['country_whois'])
  merged['country'] = merged['country'].combine_first(merged['country_whois'])
  merged.drop(columns=['country_whois'], inplace=True)

  # company: exact range match is fine here (small whitelists)
  merged = merged.merge(
    companies, on=['start_int', 'end_int'], how='left'
  )

  return merged


if __name__ == '__main__':
  import os
  output = os.path.join(os.path.dirname(__file__), '..', 'database.csv')
  output = os.path.normpath(output)
  print('> Building combined database...')
  df = build_combined()
  print(f'> Total rows: {len(df):,} | writing to {output}')
  df.to_csv(output, index=False)
  print('> Done.')
