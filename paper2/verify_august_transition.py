"""
Verify the August 2025 transition: 
1. Wider bunching window to see if mass moved to nearby bins (not collapsed)
2. Check WAV vs non-WAV separately
3. Compare aggregate post-Aug bunching at proper window
"""
import duckdb
from pathlib import Path

PANEL = Path(r"C:\research\gig\data\panels\trips_2025_2026_welfare.parquet")
con = duckdb.connect(":memory:")
con.execute("PRAGMA threads=12")
con.execute("PRAGMA memory_limit='20GB'")

# Compare bunching at fine bins around the empirically-observed modes,
# for July (last month under old rates) vs August (first month under new rates)

print("=" * 60)
print("Pay ratio distribution: July 2025 (last month under old rates)")
print("Bins of 0.01 width from 0.95 to 1.20")
print("=" * 60)

result = con.execute(f"""
    WITH binned AS (
        SELECT
            platform,
            CAST(FLOOR(pay_ratio_2024b * 100) / 100.0 AS DECIMAL(5,2)) AS bin
        FROM '{PANEL}'
        WHERE non_shared AND in_city
          AND source_month = '2025-07'
          AND pay_ratio_2024b BETWEEN 0.95 AND 1.20
    )
    SELECT bin, platform, COUNT(*) AS n
    FROM binned
    GROUP BY bin, platform
    ORDER BY bin, platform
""").fetchall()

from collections import defaultdict
table = defaultdict(lambda: {'Lyft': 0, 'Uber': 0})
for bin_val, plat, n in result:
    table[float(bin_val)][plat] = n

# Compute total for percentage
total_lyft = sum(t['Lyft'] for t in table.values())
total_uber = sum(t['Uber'] for t in table.values())

print(f"  {'Bin':>6}  {'Lyft':>12}  {'%':>6}  {'Uber':>12}  {'%':>6}")
for bin_val in sorted(table.keys()):
    lyft_n = table[bin_val]['Lyft']
    uber_n = table[bin_val]['Uber']
    lyft_pct = 100.0 * lyft_n / total_lyft if total_lyft else 0
    uber_pct = 100.0 * uber_n / total_uber if total_uber else 0
    print(f"  {bin_val:>6.2f}  {lyft_n:>12,}  {lyft_pct:>5.1f}%  {uber_n:>12,}  {uber_pct:>5.1f}%")

print(f"\n  Total in 0.95-1.20 range: Lyft {total_lyft:,}, Uber {total_uber:,}")

# Same for August 2025
print("\n" + "=" * 60)
print("Pay ratio distribution: August 2025 (first month under new rates)")
print("=" * 60)

result = con.execute(f"""
    WITH binned AS (
        SELECT
            platform,
            CAST(FLOOR(pay_ratio_2024b * 100) / 100.0 AS DECIMAL(5,2)) AS bin
        FROM '{PANEL}'
        WHERE non_shared AND in_city
          AND source_month = '2025-08'
          AND pay_ratio_2024b BETWEEN 0.95 AND 1.20
    )
    SELECT bin, platform, COUNT(*) AS n
    FROM binned
    GROUP BY bin, platform
    ORDER BY bin, platform
""").fetchall()

table2 = defaultdict(lambda: {'Lyft': 0, 'Uber': 0})
for bin_val, plat, n in result:
    table2[float(bin_val)][plat] = n

total_lyft2 = sum(t['Lyft'] for t in table2.values())
total_uber2 = sum(t['Uber'] for t in table2.values())

print(f"  {'Bin':>6}  {'Lyft':>12}  {'%':>6}  {'Uber':>12}  {'%':>6}")
for bin_val in sorted(table2.keys()):
    lyft_n = table2[bin_val]['Lyft']
    uber_n = table2[bin_val]['Uber']
    lyft_pct = 100.0 * lyft_n / total_lyft2 if total_lyft2 else 0
    uber_pct = 100.0 * uber_n / total_uber2 if total_uber2 else 0
    print(f"  {bin_val:>6.2f}  {lyft_n:>12,}  {lyft_pct:>5.1f}%  {uber_n:>12,}  {uber_pct:>5.1f}%")

print(f"\n  Total in 0.95-1.20 range: Lyft {total_lyft2:,}, Uber {total_uber2:,}")

# Now check WAV vs non-WAV composition for August
print("\n" + "=" * 60)
print("WAV vs non-WAV trip share, August 2025")
print("=" * 60)
wav_check = con.execute(f"""
    SELECT 
        platform,
        wav_match_flag,
        COUNT(*) AS n,
        ROUND(AVG(driver_pay), 3) AS mean_pay,
        ROUND(AVG(pay_ratio_2024b), 4) AS mean_ratio
    FROM '{PANEL}'
    WHERE non_shared AND in_city
      AND source_month = '2025-08'
    GROUP BY platform, wav_match_flag
    ORDER BY platform, wav_match_flag
""").fetchall()
for row in wav_check:
    print(f"  {row[0]:<6} WAV={row[1]:<5} n={row[2]:>12,} pay=${row[3]} ratio={row[4]}")

# Bunching at a wider window: ±5% around the mode
print("\n" + "=" * 60)
print("Bunching at ±2% around the modal bin, by month")
print("(Modal bin per platform per month, then count trips within ±2% of mode)")
print("=" * 60)

months = [f"2025-{m:02d}" for m in [3, 4, 5, 6, 7, 8, 9, 10, 11, 12]] + [f"2026-{m:02d}" for m in [1, 2]]

print(f"  {'Month':<8} {'Lyft mode':>10} {'Lyft ±2%':>12} {'Uber mode':>10} {'Uber ±2%':>12}")
for ym in months:
    out = []
    for plat in ['Lyft', 'Uber']:
        mode = con.execute(f"""
            WITH binned AS (
                SELECT
                    CAST(FLOOR(pay_ratio_2024b * 100) / 100.0 AS DECIMAL(5,2)) AS bin
                FROM '{PANEL}'
                WHERE non_shared AND in_city
                  AND source_month = '{ym}'
                  AND platform = '{plat}'
                  AND pay_ratio_2024b BETWEEN 0.95 AND 1.20
            )
            SELECT bin, COUNT(*) AS n FROM binned 
            GROUP BY bin ORDER BY n DESC LIMIT 1
        """).fetchone()
        if mode:
            mode_low = float(mode[0])
            window_low = mode_low - 0.01
            window_high = mode_low + 0.03
            wnd = con.execute(f"""
                SELECT 
                    COUNT(*) AS n_in_window,
                    SUM(COUNT(*)) OVER () AS n_total
                FROM (
                    SELECT 1 FROM '{PANEL}'
                    WHERE non_shared AND in_city
                      AND source_month = '{ym}'
                      AND platform = '{plat}'
                ) t
            """).fetchone()
            tot = wnd[0]
            within = con.execute(f"""
                SELECT COUNT(*) FROM '{PANEL}'
                WHERE non_shared AND in_city
                  AND source_month = '{ym}'
                  AND platform = '{plat}'
                  AND pay_ratio_2024b BETWEEN {window_low} AND {window_high}
            """).fetchone()[0]
            pct = 100.0 * within / tot if tot else 0
            out.append((mode_low, pct))
        else:
            out.append((None, None))
    
    if out[0][0] and out[1][0]:
        print(f"  {ym:<8} {out[0][0]:>10.2f} {out[0][1]:>11.1f}% {out[1][0]:>10.2f} {out[1][1]:>11.1f}%")
