"""
Enrich the 2025-2026 panel with fixed-counterfactual minima.

Uses paper 1's Mar-Dec 2024 rates ($0.789/mile, $0.338/min, 0.58 util)
as the fixed yardstick for ALL trips, regardless of trip date.

This isolates platform pay behaviour from regulatory floor changes.

Output: trips_2025_2026_welfare.parquet
"""
import duckdb
from pathlib import Path
import time

PANELS = Path(r"C:\research\gig\data\panels")
SRC = PANELS / "trips_2025_2026.parquet"
OUT = PANELS / "trips_2025_2026_welfare.parquet"

con = duckdb.connect(":memory:")
con.execute("PRAGMA threads=12")
con.execute("PRAGMA memory_limit='24GB'")
con.execute("PRAGMA temp_directory='C:/research/gig/data/duckdb_temp'")

# Paper 1 rate schedule (used as FIXED COUNTERFACTUAL for all 2025-2026 trips)
RATE_MILE_2024B = 0.789
RATE_MIN_2024B = 0.338
UTIL_CONTEMP = 0.58
UTIL_TIME_RETRO = 0.533
UTIL_DIST_RETRO = 0.685

# Period boundaries
TRANSITION_START = "2025-06-01"
POST_START = "2025-07-01"
CONGESTION_PRICING_START = "2025-01-05"

# Zone classification (from taxi_zone_lookup.csv)
# 1=Newark airport, 132=JFK, 138=LGA — all "Airport" zones
# Yellow Zone: Manhattan zones below 96th St (specific list from paper 1)
# Boro Zone: everything else in city
# We pull the lookup live to avoid duplicating the file here

print(f"Source: {SRC}")
print(f"Output: {OUT}")
print(f"Started: {time.strftime('%H:%M:%S')}")
t0 = time.time()

# Yellow Zone LocationIDs (Manhattan below 96th St + airports), from paper 1
# Manhattan zones:
YELLOW_ZONES = [
    4, 12, 13, 24, 41, 42, 43, 45, 48, 50, 68, 74, 75, 79, 87, 88, 90,
    100, 103, 104, 105, 107, 113, 114, 116, 120, 125, 127, 128, 137,
    140, 141, 142, 143, 144, 148, 151, 152, 153, 158, 161, 162, 163,
    164, 166, 170, 186, 194, 202, 209, 211, 224, 229, 230, 231, 232,
    233, 234, 236, 237, 238, 239, 243, 244, 246, 249, 261, 262, 263
]
AIRPORT_ZONES = [1, 132, 138]
yellow_str = ",".join(str(z) for z in YELLOW_ZONES)
airport_str = ",".join(str(z) for z in AIRPORT_ZONES)

# Sanity check: how many distinct PULocationIDs in the data
nz = con.execute(f"""
    SELECT COUNT(DISTINCT PULocationID) FROM '{SRC}'
""").fetchone()[0]
print(f"Distinct PULocationIDs in source: {nz}")

con.execute(f"""
    COPY (
        SELECT
            -- Original columns we keep for analysis
            hvfhs_license_num,
            CASE hvfhs_license_num
                WHEN 'HV0003' THEN 'Uber'
                WHEN 'HV0005' THEN 'Lyft'
            END AS platform,
            request_datetime,
            on_scene_datetime,
            pickup_datetime,
            dropoff_datetime,
            PULocationID,
            DOLocationID,
            trip_miles,
            trip_time,
            base_passenger_fare,
            tolls,
            bcf,
            sales_tax,
            congestion_surcharge,
            airport_fee,
            cbd_congestion_fee,
            tips,
            driver_pay,
            shared_request_flag,
            shared_match_flag,
            access_a_ride_flag,
            wav_request_flag,
            wav_match_flag,
            source_month,
            month_int,

            -- Period flags
            CASE
                WHEN pickup_datetime < TIMESTAMP '{TRANSITION_START}' THEN 'pre'
                WHEN pickup_datetime < TIMESTAMP '{POST_START}' THEN 'transition'
                ELSE 'post'
            END AS period,

            -- Days from June 6, 2025 rule effective date (for time-series plots)
            CAST(DATE_DIFF('day', TIMESTAMP '2025-06-06', pickup_datetime) AS INTEGER) AS days_from_rule,

            -- Congestion pricing flag (active from Jan 5, 2025; should be true for all 2025-2026 except first 4 days)
            CASE WHEN pickup_datetime >= TIMESTAMP '{CONGESTION_PRICING_START}' THEN TRUE ELSE FALSE END AS congestion_pricing_era,

            -- Trip touches CBD (operational definition: paid the cbd_congestion_fee)
            CASE WHEN cbd_congestion_fee > 0 THEN TRUE ELSE FALSE END AS cbd_trip,

            -- Sample restriction flags (consistent with paper 1)
            CASE WHEN shared_request_flag = 'N' AND shared_match_flag = 'N' THEN TRUE ELSE FALSE END AS non_shared,
            CASE
                WHEN PULocationID BETWEEN 1 AND 263
                 AND DOLocationID BETWEEN 1 AND 263
                 AND PULocationID != 264 AND PULocationID != 265
                 AND DOLocationID != 264 AND DOLocationID != 265
                THEN TRUE ELSE FALSE
            END AS in_city,

            -- Service zone classification
            CASE
                WHEN PULocationID IN ({airport_str}) THEN 'Airport'
                WHEN PULocationID IN ({yellow_str}) THEN 'Yellow Zone'
                ELSE 'Boro Zone'
            END AS service_zone,

            -- FIXED COUNTERFACTUAL MINIMA (paper 1 Mar-Dec 2024 rates throughout)
            -- min_pay_2024b: contemporaneous-utilisation regime (single 0.58)
            ROUND(
                ({RATE_MILE_2024B} * trip_miles + {RATE_MIN_2024B} * trip_time / 60.0) / {UTIL_CONTEMP},
                4
            ) AS min_pay_2024b,

            -- min_pay_retro: disaggregated retrospective regime (June 2025 utilisation)
            ROUND(
                {RATE_MILE_2024B} * trip_miles / {UTIL_DIST_RETRO}
                + {RATE_MIN_2024B} * (trip_time / 60.0) / {UTIL_TIME_RETRO},
                4
            ) AS min_pay_retro,

            -- Pay ratios (driver_pay / min_pay_*)
            ROUND(
                driver_pay / NULLIF(({RATE_MILE_2024B} * trip_miles + {RATE_MIN_2024B} * trip_time / 60.0) / {UTIL_CONTEMP}, 0),
                4
            ) AS pay_ratio_2024b,

            ROUND(
                driver_pay / NULLIF(
                    {RATE_MILE_2024B} * trip_miles / {UTIL_DIST_RETRO}
                    + {RATE_MIN_2024B} * (trip_time / 60.0) / {UTIL_TIME_RETRO},
                    0),
                4
            ) AS pay_ratio_retro,

            -- Take rate (kept for portfolio analysis)
            ROUND(
                (base_passenger_fare - driver_pay) / NULLIF(base_passenger_fare, 0),
                4
            ) AS take_rate,

            -- Unpaid time decomposition (Uber only; Lyft has null on_scene_datetime)
            CASE WHEN on_scene_datetime IS NOT NULL
                THEN CAST(DATE_DIFF('second', request_datetime, on_scene_datetime) AS INTEGER)
                ELSE NULL
            END AS search_lat_s,

            CASE WHEN on_scene_datetime IS NOT NULL
                THEN CAST(DATE_DIFF('second', on_scene_datetime, pickup_datetime) AS INTEGER)
                ELSE NULL
            END AS board_lat_s

        FROM '{SRC}'
        WHERE trip_miles > 0
          AND trip_time > 0
          AND driver_pay > 0
          AND base_passenger_fare > 0
    )
    TO '{OUT.as_posix()}'
    (FORMAT 'parquet', COMPRESSION 'zstd', ROW_GROUP_SIZE 100000)
""")

elapsed = time.time() - t0
print(f"\nDone in {elapsed:.0f}s. Output size: {OUT.stat().st_size / 1024 / 1024 / 1024:.2f} GB")

# Sanity checks
print("\n--- Trips by period ---")
result = con.execute(f"""
    SELECT period, COUNT(*) AS n,
           ROUND(AVG(driver_pay), 3) AS mean_pay,
           ROUND(AVG(min_pay_2024b), 3) AS mean_min_2024b,
           ROUND(AVG(min_pay_retro), 3) AS mean_min_retro,
           ROUND(AVG(pay_ratio_2024b), 4) AS mean_ratio_2024b,
           ROUND(AVG(pay_ratio_retro), 4) AS mean_ratio_retro
    FROM '{OUT}'
    WHERE non_shared AND in_city
    GROUP BY period
    ORDER BY MIN(pickup_datetime)
""").fetchall()
print(f"  {'Period':<12} {'N':>14} {'Pay':>8} {'Min24b':>8} {'MinRetro':>10} {'R24b':>8} {'RRetro':>8}")
for row in result:
    print(f"  {row[0]:<12} {row[1]:>14,} {row[2]:>8.2f} {row[3]:>8.2f} {row[4]:>10.2f} {row[5]:>8.4f} {row[6]:>8.4f}")

print("\n--- Service zone composition ---")
result = con.execute(f"""
    SELECT service_zone, COUNT(*) AS n
    FROM '{OUT}'
    WHERE non_shared AND in_city
    GROUP BY service_zone
    ORDER BY n DESC
""").fetchall()
for sz, n in result:
    print(f"  {sz:<14}: {n:>14,}")

print("\n--- Bunching shares by period (under 2024b counterfactual) ---")
result = con.execute(f"""
    SELECT
        period,
        platform,
        ROUND(100.0 * SUM(CASE WHEN pay_ratio_2024b BETWEEN 0.98 AND 1.02 THEN 1 ELSE 0 END) / COUNT(*), 2) AS bunching_pct,
        ROUND(AVG(pay_ratio_2024b), 4) AS mean_ratio
    FROM '{OUT}'
    WHERE non_shared AND in_city
    GROUP BY period, platform
    ORDER BY MIN(pickup_datetime), platform
""").fetchall()
print(f"  {'Period':<12} {'Platform':<8} {'Bunching %':>12} {'Mean ratio':>12}")
for row in result:
    print(f"  {row[0]:<12} {row[1]:<8} {row[2]:>12.2f} {row[3]:>12.4f}")
