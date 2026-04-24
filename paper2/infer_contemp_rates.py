"""
Back out the implied contemporaneous floor formula from the data itself.

Approach: For each month, find trips that look like they paid at the floor
(narrow bunching mode), then regress driver_pay on trip_miles + trip_minutes.
The coefficients ARE the implicit applied per-mile and per-minute rates.

This bypasses all the rate-document confusion.
"""
import duckdb
from pathlib import Path

PANEL = Path(r"C:\research\gig\data\panels\trips_2025_2026_welfare.parquet")
con = duckdb.connect(":memory:")
con.execute("PRAGMA threads=12")
con.execute("PRAGMA memory_limit='20GB'")

# For each month + platform, identify the modal pay-ratio bin (the bunching mode)
# Then compute the average driver_pay coefficients for trips in that mode.
# That gives us the applied per-mile and per-minute rates.

print("=" * 80)
print("Inferring contemporaneous applied rates from bunching mode by month + platform")
print("=" * 80)

months = [f"2025-{m:02d}" for m in range(1, 13)] + [f"2026-{m:02d}" for m in range(1, 3)]

print(f"\n  {'Month':<8} {'Plat':<5} {'Mode bin':>9} {'N at mode':>11} {'$/mi (impl)':>13} {'$/min (impl)':>14}")
print("  " + "-" * 70)

for ym in months:
    for plat in ['Lyft', 'Uber']:
        # Find the modal bin
        modal = con.execute(f"""
            WITH binned AS (
                SELECT
                    CAST(FLOOR(pay_ratio_2024b * 100) / 100.0 AS DECIMAL(5,2)) AS bin,
                    COUNT(*) AS n
                FROM '{PANEL}'
                WHERE non_shared AND in_city
                  AND source_month = '{ym}'
                  AND platform = '{plat}'
                  AND pay_ratio_2024b BETWEEN 0.95 AND 1.20
                GROUP BY bin
            )
            SELECT bin, n FROM binned ORDER BY n DESC LIMIT 1
        """).fetchone()

        if not modal:
            continue
        mode_bin, mode_n = modal
        mode_low = float(mode_bin)
        mode_high = mode_low + 0.01

        # Among trips in the modal bin, fit pay = a*miles + b*minutes via OLS.
        # DuckDB regr_* functions are univariate. We do bivariate by hand using
        # the moment formulas but it's easier to just compute the system directly.
        # Use approach: take the median pay/(miles + minutes/X) for several X values.
        # Simpler: extract the actual rate from sufficient statistics.

        coefs = con.execute(f"""
            WITH at_mode AS (
                SELECT driver_pay AS p, trip_miles AS m, trip_time / 60.0 AS t
                FROM '{PANEL}'
                WHERE non_shared AND in_city
                  AND source_month = '{ym}'
                  AND platform = '{plat}'
                  AND pay_ratio_2024b >= {mode_low} AND pay_ratio_2024b < {mode_high}
                  AND trip_miles BETWEEN 0.5 AND 25
                  AND trip_time BETWEEN 60 AND 5400
            ),
            sums AS (
                SELECT
                    COUNT(*) AS n,
                    SUM(m) AS sm, SUM(t) AS st,
                    SUM(m*m) AS smm, SUM(t*t) AS stt, SUM(m*t) AS smt,
                    SUM(p*m) AS spm, SUM(p*t) AS spt
                FROM at_mode
            )
            SELECT
                n,
                -- Solve [smm smt; smt stt] [a; b] = [spm; spt]
                -- Determinant
                (smm * stt - smt * smt) AS det,
                (spm * stt - spt * smt) AS num_a,
                (smm * spt - smt * spm) AS num_b
            FROM sums
        """).fetchone()

        n, det, num_a, num_b = coefs
        if det and abs(det) > 0:
            a = num_a / det  # implied $/mile
            b = num_b / det  # implied $/min
            print(f"  {ym:<8} {plat:<5} {mode_bin:>9} {mode_n:>11,} {a:>13.4f} {b:>14.4f}")
        else:
            print(f"  {ym:<8} {plat:<5} {mode_bin:>9} {mode_n:>11,} {'N/A':>13} {'N/A':>14}")
