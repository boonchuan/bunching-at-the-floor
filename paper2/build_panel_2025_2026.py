"""
Build trips_2025_2026.parquet from the 14 monthly HVFHS files.
Analogous to build_panels_2024.py but covers Jan 2025 - Feb 2026.
Preserves the new cbd_congestion_fee column added in 2025.
"""
import duckdb
from pathlib import Path
import time

DATA = Path(r"C:\research\gig\data\hvfhs")
PANELS = Path(r"C:\research\gig\data\panels")
PANELS.mkdir(parents=True, exist_ok=True)
OUT = PANELS / "trips_2025_2026.parquet"

con = duckdb.connect(":memory:")
con.execute("PRAGMA threads=12")
con.execute("PRAGMA memory_limit='24GB'")
con.execute("PRAGMA temp_directory='C:/research/gig/data/duckdb_temp'")

# Months to process
months = [f"2025-{m:02d}" for m in range(1, 13)] + [f"2026-{m:02d}" for m in range(1, 3)]
files_present = [DATA / f"fhvhv_tripdata_{ym}.parquet" for ym in months]

missing = [f for f in files_present if not f.exists()]
if missing:
    print("MISSING FILES:")
    for f in missing:
        print(f"  {f}")
    raise SystemExit(1)

print(f"Found all {len(files_present)} files. Building combined panel.")
print(f"Output: {OUT}")
print(f"Started: {time.strftime('%H:%M:%S')}")

t0 = time.time()

# Use UNION ALL via glob; DuckDB infers the union schema.
# Add a source_month column derived from filename for time-series analysis.
src_glob = str(DATA / "fhvhv_tripdata_2025-*.parquet").replace("\\", "/")
src_glob_2026 = str(DATA / "fhvhv_tripdata_2026-*.parquet").replace("\\", "/")

con.execute(f"""
    COPY (
        SELECT
            *,
            STRFTIME(pickup_datetime, '%Y-%m') AS source_month,
            CAST(STRFTIME(pickup_datetime, '%Y%m') AS INTEGER) AS month_int
        FROM read_parquet([
            '{src_glob}',
            '{src_glob_2026}'
        ], union_by_name = true)
        WHERE hvfhs_license_num IN ('HV0003', 'HV0005')
          AND pickup_datetime >= '2025-01-01'
          AND pickup_datetime <  '2026-03-01'
    )
    TO '{OUT.as_posix()}'
    (FORMAT 'parquet', COMPRESSION 'zstd', ROW_GROUP_SIZE 100000)
""")

elapsed = time.time() - t0
print(f"\nDone in {elapsed:.0f}s. Output size: {OUT.stat().st_size / 1024 / 1024 / 1024:.2f} GB")

# Quick sanity check
n = con.execute(f"SELECT COUNT(*) FROM '{OUT}'").fetchone()[0]
print(f"Total trips in panel: {n:,}")

print("\n--- Trips by source month ---")
result = con.execute(f"""
    SELECT source_month, COUNT(*) AS n
    FROM '{OUT}'
    GROUP BY source_month
    ORDER BY source_month
""").fetchall()
for ym, c in result:
    print(f"  {ym}: {c:>12,}")

print("\n--- Trips by platform ---")
plat = con.execute(f"""
    SELECT
        CASE hvfhs_license_num
            WHEN 'HV0003' THEN 'Uber'
            WHEN 'HV0005' THEN 'Lyft'
        END AS platform,
        COUNT(*) AS n
    FROM '{OUT}'
    GROUP BY platform
    ORDER BY platform
""").fetchall()
for p, c in plat:
    print(f"  {p}: {c:>14,}")

print("\n--- cbd_congestion_fee summary ---")
ccf = con.execute(f"""
    SELECT
        COUNT(*) AS n,
        COUNT(cbd_congestion_fee) AS n_non_null,
        SUM(CASE WHEN cbd_congestion_fee > 0 THEN 1 ELSE 0 END) AS n_positive,
        ROUND(AVG(cbd_congestion_fee), 4) AS mean_fee,
        ROUND(MAX(cbd_congestion_fee), 2) AS max_fee
    FROM '{OUT}'
""").fetchone()
print(f"  total trips: {ccf[0]:,}")
print(f"  non-null cbd_congestion_fee: {ccf[1]:,}")
print(f"  positive cbd_congestion_fee: {ccf[2]:,}")
print(f"  mean fee (across all trips): ${ccf[3]:.4f}")
print(f"  max fee: ${ccf[4]:.2f}")
