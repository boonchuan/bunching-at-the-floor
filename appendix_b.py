"""
Appendix B: distributional comparison of excluded trips
(shared trips and out-of-city trips) vs analytical sample.
"""
import duckdb
from pathlib import Path

PANEL_DIR = Path(r"C:\research\gig\data\panels")
TRIP = PANEL_DIR / "trips_2024_welfare.parquet"

con = duckdb.connect(database=":memory:")
con.execute("PRAGMA threads=12")
con.execute("PRAGMA memory_limit='20GB'")

print("=" * 60)
print("Appendix B: comparison of excluded vs included trips")
print("=" * 60)

# Categorise trips
comparison = con.execute(f"""
    SELECT
        CASE
            WHEN non_shared = 1 AND in_city = 1 AND base_passenger_fare > 0 AND driver_pay > 0 THEN 'Included (main)'
            WHEN non_shared = 0 THEN 'Excluded: shared'
            WHEN in_city = 0 THEN 'Excluded: out-of-city'
            ELSE 'Excluded: other'
        END AS category,
        platform,
        COUNT(*) AS n_trips,
        ROUND(AVG(trip_miles), 2) AS mean_miles,
        ROUND(AVG(trip_time / 60.0), 1) AS mean_minutes,
        ROUND(AVG(driver_pay), 2) AS mean_driver_pay,
        ROUND(AVG(base_passenger_fare), 2) AS mean_passenger_fare
    FROM '{TRIP}'
    WHERE driver_pay > 0 AND base_passenger_fare > 0
    GROUP BY category, platform
    ORDER BY category, platform
""").pl()

print(comparison)

# Bunching share for excluded trips where computable
print("\n" + "=" * 60)
print("Bunching share comparison (where computable)")
print("=" * 60)

bunching = con.execute(f"""
    SELECT
        CASE
            WHEN non_shared = 1 AND in_city = 1 THEN 'Included (main)'
            WHEN non_shared = 0 AND in_city = 1 THEN 'Shared, in-city'
            WHEN non_shared = 1 AND in_city = 0 THEN 'Non-shared, out-of-city'
            ELSE 'Shared, out-of-city'
        END AS category,
        platform,
        COUNT(*) AS n_trips,
        ROUND(AVG(driver_pay / NULLIF(min_pay_contemp, 0)), 4) AS mean_ratio,
        ROUND(100.0 * SUM(CASE WHEN driver_pay / NULLIF(min_pay_contemp, 0) BETWEEN 0.98 AND 1.02 THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_at_min
    FROM '{TRIP}'
    WHERE driver_pay > 0 AND base_passenger_fare > 0 AND min_pay_contemp > 0
    GROUP BY category, platform
    ORDER BY category, platform
""").pl()

print(bunching)
