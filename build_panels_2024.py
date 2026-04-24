"""
NYC HVFHS 2024 full-year download and base aggregation.
Downloads 12 monthly parquet files (~5.5 GB total), then builds
zone-hour-base panels for subsequent analysis.

Idempotent: skips files that already exist.
"""
import time
import urllib.request
from pathlib import Path
import duckdb

DATA_DIR = Path(r"C:\research\gig\data\hvfhs")
PANEL_DIR = Path(r"C:\research\gig\data\panels")
DATA_DIR.mkdir(parents=True, exist_ok=True)
PANEL_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = "https://d37ci6vzurychx.cloudfront.net/trip-data"
MONTHS = [f"2024-{m:02d}" for m in range(1, 13)]

# 1. Download
print("=" * 60)
print("Phase 1: Download")
print("=" * 60)
total_mb = 0
for m in MONTHS:
    local = DATA_DIR / f"fhvhv_{m}.parquet"
    if local.exists():
        sz = local.stat().st_size / 1024 / 1024
        total_mb += sz
        print(f"  cached  {local.name:<30} {sz:>7.1f} MB")
        continue
    url = f"{BASE_URL}/fhvhv_tripdata_{m}.parquet"
    t0 = time.time()
    urllib.request.urlretrieve(url, local)
    sz = local.stat().st_size / 1024 / 1024
    total_mb += sz
    print(f"  DL      {local.name:<30} {sz:>7.1f} MB in {time.time()-t0:>5.1f}s")
print(f"\nTotal: {total_mb:.1f} MB")

# 2. Build the base panel: trip-level table with derived fields
# Kept as parquet for reusability. One row per trip.
print("\n" + "=" * 60)
print("Phase 2: Build trip-level panel with derived fields")
print("=" * 60)

con = duckdb.connect(database=":memory:")
con.execute("PRAGMA threads=12")
con.execute("PRAGMA memory_limit='20GB'")

trip_panel = PANEL_DIR / "trips_2024.parquet"
if trip_panel.exists():
    print(f"  cached  {trip_panel.name}")
else:
    t0 = time.time()
    con.execute(f"""
        COPY (
            SELECT
                hvfhs_license_num AS lic,
                CASE
                    WHEN hvfhs_license_num = 'HV0003' THEN 'Uber'
                    WHEN hvfhs_license_num = 'HV0005' THEN 'Lyft'
                    ELSE 'Other'
                END AS platform,
                request_datetime,
                on_scene_datetime,
                pickup_datetime,
                dropoff_datetime,
                PULocationID AS pu_zone,
                DOLocationID AS do_zone,
                trip_miles,
                trip_time,
                base_passenger_fare,
                driver_pay,
                tips,
                shared_request_flag,
                shared_match_flag,
                -- Derived latencies (seconds)
                EXTRACT(EPOCH FROM (pickup_datetime - request_datetime))::BIGINT AS dispatch_lat_s,
                EXTRACT(EPOCH FROM (on_scene_datetime - request_datetime))::BIGINT AS search_lat_s,
                EXTRACT(EPOCH FROM (pickup_datetime - on_scene_datetime))::BIGINT AS board_lat_s,
                -- Time buckets (UTC as stored)
                EXTRACT(HOUR FROM request_datetime)::TINYINT AS hr,
                EXTRACT(DOW FROM request_datetime)::TINYINT AS dow,
                DATE_TRUNC('day', request_datetime)::DATE AS dt
            FROM read_parquet('{DATA_DIR}/fhvhv_2024-*.parquet')
            WHERE hvfhs_license_num IN ('HV0003', 'HV0005')
              AND request_datetime IS NOT NULL
              AND pickup_datetime IS NOT NULL
              AND pickup_datetime > request_datetime
              AND EXTRACT(EPOCH FROM (pickup_datetime - request_datetime)) BETWEEN 30 AND 3600
        ) TO '{trip_panel}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    print(f"  built   {trip_panel.name} in {time.time()-t0:.1f}s")

n_trips = con.execute(f"SELECT COUNT(*) FROM '{trip_panel}'").fetchone()[0]
print(f"  trips   {n_trips:,}")

# 3. Zone-hour-platform panel
zh_panel = PANEL_DIR / "zone_hour_platform_2024.parquet"
if zh_panel.exists():
    print(f"  cached  {zh_panel.name}")
else:
    t0 = time.time()
    con.execute(f"""
        COPY (
            SELECT
                pu_zone,
                hr,
                dow,
                platform,
                COUNT(*) AS n_trips,
                quantile_cont(dispatch_lat_s, 0.5) AS p50_dispatch_s,
                quantile_cont(dispatch_lat_s, 0.9) AS p90_dispatch_s,
                quantile_cont(dispatch_lat_s, 0.95) AS p95_dispatch_s,
                AVG(dispatch_lat_s) AS mean_dispatch_s,
                AVG(trip_miles) AS mean_miles,
                AVG(trip_time) AS mean_trip_time_s,
                AVG(base_passenger_fare) AS mean_fare,
                AVG(driver_pay) AS mean_driver_pay,
                AVG(tips) AS mean_tips
            FROM '{trip_panel}'
            GROUP BY pu_zone, hr, dow, platform
        ) TO '{zh_panel}' (FORMAT PARQUET)
    """)
    print(f"  built   {zh_panel.name} in {time.time()-t0:.1f}s")

# 4. Zone summary
zone_panel = PANEL_DIR / "zone_summary_2024.parquet"
if zone_panel.exists():
    print(f"  cached  {zone_panel.name}")
else:
    t0 = time.time()
    con.execute(f"""
        COPY (
            SELECT
                pu_zone,
                platform,
                COUNT(*) AS n_trips,
                quantile_cont(dispatch_lat_s, 0.5) AS p50_dispatch_s,
                quantile_cont(dispatch_lat_s, 0.9) AS p90_dispatch_s,
                AVG(dispatch_lat_s) AS mean_dispatch_s,
                AVG(trip_miles) AS mean_miles,
                AVG(driver_pay) AS mean_driver_pay
            FROM '{trip_panel}'
            GROUP BY pu_zone, platform
        ) TO '{zone_panel}' (FORMAT PARQUET)
    """)
    print(f"  built   {zone_panel.name} in {time.time()-t0:.1f}s")

# 5. Daily summary
daily_panel = PANEL_DIR / "daily_2024.parquet"
if daily_panel.exists():
    print(f"  cached  {daily_panel.name}")
else:
    t0 = time.time()
    con.execute(f"""
        COPY (
            SELECT
                dt,
                platform,
                COUNT(*) AS n_trips,
                quantile_cont(dispatch_lat_s, 0.5) AS p50_dispatch_s,
                quantile_cont(dispatch_lat_s, 0.9) AS p90_dispatch_s,
                AVG(dispatch_lat_s) AS mean_dispatch_s,
                AVG(driver_pay) AS mean_driver_pay
            FROM '{trip_panel}'
            GROUP BY dt, platform
            ORDER BY dt, platform
        ) TO '{daily_panel}' (FORMAT PARQUET)
    """)
    print(f"  built   {daily_panel.name} in {time.time()-t0:.1f}s")

print("\n" + "=" * 60)
print("Panel builds complete. Files:")
print("=" * 60)
for f in PANEL_DIR.glob("*.parquet"):
    sz = f.stat().st_size / 1024 / 1024
    print(f"  {f.name:<40} {sz:>7.1f} MB")
