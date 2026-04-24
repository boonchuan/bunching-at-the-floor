"""
Verification queries for paper v2 revisions.
1. Correct Table 1 values for the analytical sample
2. Unpaid time: both mean-of-ratios and ratio-of-means
3. Bunching bandwidth robustness
"""
import duckdb
from pathlib import Path

PANEL_DIR = Path(r"C:\research\gig\data\panels")
TRIP = PANEL_DIR / "trips_2024_welfare.parquet"

con = duckdb.connect(database=":memory:")
con.execute("PRAGMA threads=12")
con.execute("PRAGMA memory_limit='20GB'")

filter_main = "non_shared = 1 AND in_city = 1 AND base_passenger_fare > 0 AND driver_pay > 0"

# 1. Table 1: precise analytical sample descriptives
print("=" * 60)
print("1. Table 1 descriptives (corrected)")
print("=" * 60)

q1 = con.execute(f"""
    SELECT platform, COUNT(*) AS n,
        ROUND(AVG(trip_miles), 3) AS mean_miles,
        ROUND(AVG(trip_time / 60.0), 3) AS mean_min,
        ROUND(AVG(driver_pay), 3) AS mean_pay,
        ROUND(AVG(base_passenger_fare), 3) AS mean_fare
    FROM '{TRIP}'
    WHERE {filter_main}
    GROUP BY platform
    ORDER BY platform
""").fetchall()

for row in q1:
    print(row)

# 2. Unpaid time: mean-of-ratios AND ratio-of-means
print("\n" + "=" * 60)
print("2. Unpaid time decomposition (Uber subsample)")
print("=" * 60)

q2 = con.execute(f"""
    SELECT
        COUNT(*) AS n,
        ROUND(AVG(trip_time / 60.0), 3) AS mean_paid_min,
        ROUND(AVG(search_lat_s / 60.0), 3) AS mean_search_min,
        ROUND(AVG(board_lat_s / 60.0), 3) AS mean_board_min,
        ROUND(AVG((search_lat_s + board_lat_s) * 1.0 / (search_lat_s + board_lat_s + trip_time)), 4) AS mean_of_ratios,
        ROUND(SUM(search_lat_s + board_lat_s) * 1.0 / SUM(search_lat_s + board_lat_s + trip_time), 4) AS ratio_of_means,
        ROUND(quantile_cont((search_lat_s + board_lat_s) * 1.0 / (search_lat_s + board_lat_s + trip_time), 0.5), 4) AS p50_ratio
    FROM '{TRIP}'
    WHERE {filter_main}
      AND platform = 'Uber'
      AND search_lat_s BETWEEN 30 AND 3600
      AND board_lat_s BETWEEN 0 AND 1800
      AND trip_time BETWEEN 60 AND 7200
""").fetchall()

for row in q2:
    print(row)

# 3. Bunching bandwidth robustness
print("\n" + "=" * 60)
print("3. Bunching bandwidth robustness")
print("=" * 60)

q3 = con.execute(f"""
    SELECT
        platform,
        ROUND(100.0 * SUM(CASE WHEN driver_pay/min_pay_contemp BETWEEN 0.99 AND 1.01 THEN 1 ELSE 0 END)/COUNT(*), 2) AS pct_pm1,
        ROUND(100.0 * SUM(CASE WHEN driver_pay/min_pay_contemp BETWEEN 0.98 AND 1.02 THEN 1 ELSE 0 END)/COUNT(*), 2) AS pct_pm2,
        ROUND(100.0 * SUM(CASE WHEN driver_pay/min_pay_contemp BETWEEN 0.97 AND 1.03 THEN 1 ELSE 0 END)/COUNT(*), 2) AS pct_pm3,
        ROUND(100.0 * SUM(CASE WHEN driver_pay/min_pay_contemp BETWEEN 0.95 AND 1.05 THEN 1 ELSE 0 END)/COUNT(*), 2) AS pct_pm5
    FROM '{TRIP}'
    WHERE {filter_main} AND min_pay_contemp > 0
    GROUP BY platform
    ORDER BY platform
""").fetchall()

print(f"  {'platform':<8} {'±1%':>6} {'±2%':>6} {'±3%':>6} {'±5%':>6}")
for row in q3:
    p, pm1, pm2, pm3, pm5 = row
    print(f"  {p:<8} {pm1:>6.2f} {pm2:>6.2f} {pm3:>6.2f} {pm5:>6.2f}")
