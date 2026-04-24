"""
Download TLC taxi zone lookup (zone_id -> borough, zone, service_zone).
This is the authoritative reference for spatial classification.
"""
import urllib.request
from pathlib import Path
import polars as pl

DATA_DIR = Path(r"C:\research\gig\data")
URL = "https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv"
LOCAL = DATA_DIR / "taxi_zone_lookup.csv"

if not LOCAL.exists():
    print(f"Downloading {URL}")
    urllib.request.urlretrieve(URL, LOCAL)

df = pl.read_csv(LOCAL)
print(df.head(20))
print("\nRows:", len(df))
print("\nBorough counts:")
print(df.group_by("Borough").agg(pl.count()).sort("count", descending=True))
print("\nService zone counts:")
print(df.group_by("service_zone").agg(pl.count()).sort("count", descending=True))
