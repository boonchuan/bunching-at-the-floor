"""
NYC HVFHS January 2024 Audit
Purpose: verify schema, field completeness, and baseline dispatch latency
distributions before committing to full 12-month pull.

Outputs: console diagnostics + 4 PNG plots in C:\research\gig\output\
"""
import os
import sys
import time
import urllib.request
from pathlib import Path

import duckdb
import numpy as np
import polars as pl
import matplotlib.pyplot as plt

DATA_DIR = Path(r"C:\research\gig\data\hvfhs")
OUT_DIR = Path(r"C:\research\gig\output")
OUT_DIR.mkdir(parents=True, exist_ok=True)

URL = "https://d37ci6vzurychx.cloudfront.net/trip-data/fhvhv_tripdata_2024-01.parquet"
LOCAL = DATA_DIR / "fhvhv_2024-01.parquet"

# 1. Download if not cached
if not LOCAL.exists():
    print(f"Downloading {URL}")
    t0 = time.time()
    urllib.request.urlretrieve(URL, LOCAL)
    sz_mb = LOCAL.stat().st_size / 1024 / 1024
    print(f"  done in {time.time()-t0:.1f}s, {sz_mb:.1f} MB")
else:
    sz_mb = LOCAL.stat().st_size / 1024 / 1024
    print(f"Using cached {LOCAL} ({sz_mb:.1f} MB)")

# 2. Schema inspection
con = duckdb.connect()
schema = con.execute(f"DESCRIBE SELECT * FROM '{LOCAL}'").fetchall()
print("\nSchema:")
for col, typ, *_ in schema:
    print(f"  {col:<30} {typ}")

# 3. Row count and basic stats
n_rows = con.execute(f"SELECT COUNT(*) FROM '{LOCAL}'").fetchone()[0]
print(f"\nRows: {n_rows:,}")

# 4. Per-base trip counts (Uber HV0003, Lyft HV0005, Via HV0004, Juno HV0002)
base_counts = con.execute(f"""
    SELECT hvfhs_license_num, COUNT(*) AS trips,
           ROUND(100.0 * COUNT(*) / {n_rows}, 2) AS pct
    FROM '{LOCAL}'
    GROUP BY hvfhs_license_num
    ORDER BY trips DESC
""").fetchall()
print("\nTrips by HVFHS license:")
for lic, n, pct in base_counts:
    name = {"HV0002": "Juno", "HV0003": "Uber", "HV0004": "Via", "HV0005": "Lyft"}.get(lic, lic)
    print(f"  {lic} ({name:<5}): {n:>12,} ({pct:>5.2f}%)")

# 5. Critical field nullness
print("\nField nullness (% null):")
key_fields = [
    "request_datetime", "on_scene_datetime", "pickup_datetime", "dropoff_datetime",
    "PULocationID", "DOLocationID", "trip_miles", "trip_time",
    "base_passenger_fare", "driver_pay", "tips",
    "originating_base_num", "dispatching_base_num",
]
for f in key_fields:
    try:
        null_pct = con.execute(f"""
            SELECT ROUND(100.0 * SUM(CASE WHEN {f} IS NULL THEN 1 ELSE 0 END) / COUNT(*), 3)
            FROM '{LOCAL}'
        """).fetchone()[0]
        print(f"  {f:<25} {null_pct:>7.3f}%")
    except Exception as e:
        print(f"  {f:<25} ERROR: {e}")

# 6. Dispatch latency: pickup_datetime - request_datetime
print("\nDispatch latency (pickup - request) percentiles, in seconds:")
latency_pct = con.execute(f"""
    SELECT
      quantile_cont(EXTRACT(EPOCH FROM (pickup_datetime - request_datetime)), [0.05, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99])
    FROM '{LOCAL}'
    WHERE pickup_datetime IS NOT NULL AND request_datetime IS NOT NULL
      AND pickup_datetime > request_datetime
      AND EXTRACT(EPOCH FROM (pickup_datetime - request_datetime)) < 7200
""").fetchone()[0]
for p, v in zip([5, 25, 50, 75, 90, 95, 99], latency_pct):
    print(f"  P{p:<3}: {v:>7.1f}s ({v/60:>5.2f} min)")

# 7. Driver search (on_scene - request) where available
print("\nDriver search latency (on_scene - request) percentiles, in seconds:")
search_pct = con.execute(f"""
    SELECT
      quantile_cont(EXTRACT(EPOCH FROM (on_scene_datetime - request_datetime)), [0.05, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99])
    FROM '{LOCAL}'
    WHERE on_scene_datetime IS NOT NULL AND request_datetime IS NOT NULL
      AND on_scene_datetime > request_datetime
      AND EXTRACT(EPOCH FROM (on_scene_datetime - request_datetime)) < 7200
""").fetchone()[0]
for p, v in zip([5, 25, 50, 75, 90, 95, 99], search_pct):
    print(f"  P{p:<3}: {v:>7.1f}s ({v/60:>5.2f} min)")

# 8. Plots
print("\nGenerating plots...")

# Plot 1: latency CDF by base (Uber vs Lyft)
df = con.execute(f"""
    SELECT hvfhs_license_num,
           EXTRACT(EPOCH FROM (pickup_datetime - request_datetime)) AS lat
    FROM '{LOCAL}'
    WHERE pickup_datetime IS NOT NULL AND request_datetime IS NOT NULL
      AND pickup_datetime > request_datetime
      AND EXTRACT(EPOCH FROM (pickup_datetime - request_datetime)) BETWEEN 0 AND 1800
      AND hvfhs_license_num IN ('HV0003', 'HV0005')
    USING SAMPLE 500000 ROWS
""").pl()

fig, ax = plt.subplots(figsize=(8, 5))
for lic, label in [("HV0003", "Uber"), ("HV0005", "Lyft")]:
    sub = df.filter(pl.col("hvfhs_license_num") == lic)["lat"].sort()
    if len(sub) > 0:
        ax.plot(sub, np.linspace(0, 1, len(sub)), label=f"{label} (n={len(sub):,})")
ax.set_xlabel("Dispatch latency (s)")
ax.set_ylabel("CDF")
ax.set_title("Dispatch latency CDF by platform, NYC HVFHS Jan 2024")
ax.legend()
ax.grid(True, alpha=0.3)
fig.savefig(OUT_DIR / "01_latency_cdf_by_base.png", dpi=120, bbox_inches="tight")
plt.close()

# Plot 2: latency by hour of day
hourly = con.execute(f"""
    SELECT EXTRACT(HOUR FROM request_datetime) AS hr,
           quantile_cont(EXTRACT(EPOCH FROM (pickup_datetime - request_datetime)), 0.5) AS p50,
           quantile_cont(EXTRACT(EPOCH FROM (pickup_datetime - request_datetime)), 0.9) AS p90
    FROM '{LOCAL}'
    WHERE pickup_datetime IS NOT NULL AND request_datetime IS NOT NULL
      AND pickup_datetime > request_datetime
      AND EXTRACT(EPOCH FROM (pickup_datetime - request_datetime)) BETWEEN 0 AND 3600
    GROUP BY hr
    ORDER BY hr
""").pl()

fig, ax = plt.subplots(figsize=(8, 5))
ax.plot(hourly["hr"], hourly["p50"], marker="o", label="P50")
ax.plot(hourly["hr"], hourly["p90"], marker="s", label="P90")
ax.set_xlabel("Hour of day (UTC of request)")
ax.set_ylabel("Dispatch latency (s)")
ax.set_title("Dispatch latency by hour of day, NYC HVFHS Jan 2024")
ax.legend()
ax.grid(True, alpha=0.3)
fig.savefig(OUT_DIR / "02_latency_by_hour.png", dpi=120, bbox_inches="tight")
plt.close()

# Plot 3: trip volume by hour
volume = con.execute(f"""
    SELECT EXTRACT(HOUR FROM request_datetime) AS hr, COUNT(*) AS trips
    FROM '{LOCAL}'
    WHERE request_datetime IS NOT NULL
    GROUP BY hr ORDER BY hr
""").pl()

fig, ax = plt.subplots(figsize=(8, 5))
ax.bar(volume["hr"], volume["trips"])
ax.set_xlabel("Hour of day")
ax.set_ylabel("Trip count")
ax.set_title("Demand intensity by hour, NYC HVFHS Jan 2024")
ax.grid(True, alpha=0.3, axis="y")
fig.savefig(OUT_DIR / "03_demand_by_hour.png", dpi=120, bbox_inches="tight")
plt.close()

# Plot 4: driver pay distribution
pay = con.execute(f"""
    SELECT driver_pay
    FROM '{LOCAL}'
    WHERE driver_pay BETWEEN 0 AND 100
    USING SAMPLE 500000 ROWS
""").pl()

fig, ax = plt.subplots(figsize=(8, 5))
ax.hist(pay["driver_pay"], bins=80, edgecolor="black", linewidth=0.3)
ax.set_xlabel("Driver pay per trip ($)")
ax.set_ylabel("Trip count")
ax.set_title("Driver pay distribution, NYC HVFHS Jan 2024 (sample)")
ax.grid(True, alpha=0.3, axis="y")
fig.savefig(OUT_DIR / "04_driver_pay.png", dpi=120, bbox_inches="tight")
plt.close()

print(f"\nPlots saved to {OUT_DIR}")
print("\nAudit complete.")
