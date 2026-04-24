"""
Diagnose the bunching collapse: check the actual pay ratio distribution
in the pre-period to see if there's a spike at ~0.97 (consistent with
a per-mile rate change from $0.789 to $0.762) instead of at 1.00.
"""
import duckdb
from pathlib import Path

PANEL = Path(r"C:\research\gig\data\panels\trips_2025_2026_welfare.parquet")
con = duckdb.connect(":memory:")
con.execute("PRAGMA threads=12")

# Pay ratio histogram in pre-period (Jan-May 2025), in tight bins around 1.0
print("=" * 60)
print("Pay ratio distribution: pre-period (Jan-May 2025)")
print("Bins of 0.01 width from 0.90 to 1.10")
print("=" * 60)

result = con.execute(f"""
    WITH binned AS (
        SELECT
            platform,
            CAST(FLOOR(pay_ratio_2024b * 100) / 100.0 AS DECIMAL(5,2)) AS bin
        FROM '{PANEL}'
        WHERE non_shared AND in_city
          AND period = 'pre'
          AND pay_ratio_2024b BETWEEN 0.90 AND 1.10
    )
    SELECT bin, platform, COUNT(*) AS n
    FROM binned
    GROUP BY bin, platform
    ORDER BY bin, platform
""").fetchall()

# Pivot to wide format for display
from collections import defaultdict
table = defaultdict(lambda: {'Lyft': 0, 'Uber': 0})
for bin_val, plat, n in result:
    table[float(bin_val)][plat] = n

print(f"  {'Bin':>6}  {'Lyft':>12}  {'Uber':>12}")
for bin_val in sorted(table.keys()):
    print(f"  {bin_val:>6.2f}  {table[bin_val]['Lyft']:>12,}  {table[bin_val]['Uber']:>12,}")

# Same for post-period for comparison
print("\n" + "=" * 60)
print("Pay ratio distribution: post-period (Jul 2025-Feb 2026)")
print("=" * 60)

result = con.execute(f"""
    WITH binned AS (
        SELECT
            platform,
            CAST(FLOOR(pay_ratio_2024b * 100) / 100.0 AS DECIMAL(5,2)) AS bin
        FROM '{PANEL}'
        WHERE non_shared AND in_city
          AND period = 'post'
          AND pay_ratio_2024b BETWEEN 0.90 AND 1.10
    )
    SELECT bin, platform, COUNT(*) AS n
    FROM binned
    GROUP BY bin, platform
    ORDER BY bin, platform
""").fetchall()

table2 = defaultdict(lambda: {'Lyft': 0, 'Uber': 0})
for bin_val, plat, n in result:
    table2[float(bin_val)][plat] = n

print(f"  {'Bin':>6}  {'Lyft':>12}  {'Uber':>12}")
for bin_val in sorted(table2.keys()):
    print(f"  {bin_val:>6.2f}  {table2[bin_val]['Lyft']:>12,}  {table2[bin_val]['Uber']:>12,}")

# Quick check: look at pay ratio distribution in 2024 panel for comparison
print("\n" + "=" * 60)
print("2024 reference (from paper 1 panel): pay_ratio_contemp for comparison")
print("=" * 60)

OLD = Path(r"C:\research\gig\data\panels\trips_2024_welfare.parquet")
# Check what columns exist there
cols = con.execute(f"DESCRIBE SELECT * FROM '{OLD}' LIMIT 0").fetchall()
ratio_cols = [c[0] for c in cols if 'ratio' in c[0].lower() or 'pay' in c[0].lower()]
print(f"  Available pay/ratio columns in 2024 panel: {ratio_cols[:10]}")

# Try with the most likely column name
try:
    result = con.execute(f"""
        WITH binned AS (
            SELECT
                CASE platform WHEN 'Uber' THEN 'Uber' WHEN 'Lyft' THEN 'Lyft' END AS platform,
                CAST(FLOOR(pay_ratio_contemp * 100) / 100.0 AS DECIMAL(5,2)) AS bin
            FROM '{OLD}'
            WHERE non_shared = 1 AND in_city = 1
              AND pay_ratio_contemp BETWEEN 0.90 AND 1.10
        )
        SELECT bin, platform, COUNT(*) AS n
        FROM binned
        GROUP BY bin, platform
        ORDER BY bin, platform
    """).fetchall()

    table3 = defaultdict(lambda: {'Lyft': 0, 'Uber': 0})
    for bin_val, plat, n in result:
        table3[float(bin_val)][plat] = n

    print(f"  {'Bin':>6}  {'Lyft':>12}  {'Uber':>12}")
    for bin_val in sorted(table3.keys()):
        print(f"  {bin_val:>6.2f}  {table3[bin_val]['Lyft']:>12,}  {table3[bin_val]['Uber']:>12,}")
except Exception as e:
    print(f"  Couldn't query 2024 panel: {e}")
