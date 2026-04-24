"""
paper2_analysis.py - Paper 2 main analysis (clean rewrite).

Builds a unified 27-month panel and produces the headline numbers
and figure data for paper 2.

Yardstick: paper 1 Mar-Dec 2024 rates ($0.789/mile, $0.338/min, util 0.58).
This is a FIXED counterfactual; any change in pay_ratio_2024b across time
reflects platform behaviour, not floor changes.
"""
import duckdb
from pathlib import Path
import csv
import time

# ---- Config (use raw strings for Windows paths) ----
PANEL_2024 = r"C:\research\gig\data\panels\trips_2024_welfare.parquet"
PANEL_2526 = r"C:\research\gig\data\panels\trips_2025_2026_welfare.parquet"
UNIFIED    = r"C:\research\gig\data\panels\trips_unified_paper2.parquet"
OUTDIR     = Path(r"C:\research\gig\output\paper2")
OUTDIR.mkdir(parents=True, exist_ok=True)

# Yardstick rates
RATE_M = 0.789
RATE_T = 0.338
UTIL   = 0.58

# Yellow Zone (Manhattan below 96th + airports), from paper 1
YELLOW = "4,12,13,24,41,42,43,45,48,50,68,74,75,79,87,88,90,100,103,104,105,107,113,114,116,120,125,127,128,137,140,141,142,143,144,148,151,152,153,158,161,162,163,164,166,170,186,194,202,209,211,224,229,230,231,232,233,234,236,237,238,239,243,244,246,249,261,262,263"
AIRPORT = "1,132,138"

con = duckdb.connect(":memory:")
con.execute("PRAGMA threads=12")
con.execute("PRAGMA memory_limit='24GB'")
con.execute("PRAGMA temp_directory='C:/research/gig/data/duckdb_temp'")

print(f"Started: {time.strftime('%H:%M:%S')}")
t0 = time.time()

# ---- Step 1: Build unified panel ----
print("Building unified 27-month panel...")

unified_sql = f"""
COPY (
    -- 2024 portion
    SELECT
        platform,
        STRFTIME(pickup_datetime, '%Y-%m') AS source_month,
        pickup_datetime,
        pu_zone AS PULocationID,
        trip_miles,
        trip_time,
        driver_pay,
        base_passenger_fare,
        CASE
            WHEN pu_zone IN ({AIRPORT}) THEN 'Airport'
            WHEN pu_zone IN ({YELLOW}) THEN 'Yellow Zone'
            ELSE 'Boro Zone'
        END AS service_zone,
        ROUND(
            driver_pay / NULLIF(({RATE_M} * trip_miles + {RATE_T} * trip_time / 60.0) / {UTIL}, 0),
            4
        ) AS pay_ratio_2024b
    FROM '{PANEL_2024}'
    WHERE non_shared = 1 AND in_city = 1

    UNION ALL

    -- 2025-2026 portion (already computed)
    SELECT
        platform,
        source_month,
        pickup_datetime,
        PULocationID,
        trip_miles,
        trip_time,
        driver_pay,
        base_passenger_fare,
        service_zone,
        pay_ratio_2024b
    FROM '{PANEL_2526}'
    WHERE non_shared AND in_city
)
TO '{UNIFIED}'
(FORMAT 'parquet', COMPRESSION 'zstd', ROW_GROUP_SIZE 100000)
"""
con.execute(unified_sql)

n = con.execute(f"SELECT COUNT(*) FROM '{UNIFIED}'").fetchone()[0]
size_gb = Path(UNIFIED).stat().st_size / 1024**3
print(f"Unified panel: {n:,} trips, {size_gb:.2f} GB ({time.time()-t0:.0f}s)")

# ---- Step 2: Monthly modal-bin bunching (Figure 1 data) ----
print("\nComputing monthly bunching by modal-bin window...")

months = [r[0] for r in con.execute(
    f"SELECT DISTINCT source_month FROM '{UNIFIED}' ORDER BY source_month"
).fetchall()]
print(f"  Months in panel: {len(months)} ({months[0]} to {months[-1]})")

monthly_data = []
for ym in months:
    for plat in ['Lyft', 'Uber']:
        # Find modal bin in [0.90, 1.30]
        mode_q = con.execute(f"""
            WITH binned AS (
                SELECT CAST(FLOOR(pay_ratio_2024b * 100) / 100.0 AS DECIMAL(5,2)) AS bin
                FROM '{UNIFIED}'
                WHERE source_month = '{ym}' AND platform = '{plat}'
                  AND pay_ratio_2024b BETWEEN 0.90 AND 1.30
            )
            SELECT bin, COUNT(*) FROM binned GROUP BY bin ORDER BY 2 DESC LIMIT 1
        """).fetchone()
        if not mode_q:
            continue
        mode_bin = float(mode_q[0])
        win_lo, win_hi = mode_bin - 0.02, mode_bin + 0.02

        r = con.execute(f"""
            SELECT
                COUNT(*) AS n,
                SUM(CASE WHEN pay_ratio_2024b BETWEEN {win_lo} AND {win_hi} THEN 1 ELSE 0 END) AS nb,
                ROUND(AVG(driver_pay), 4) AS mean_pay,
                ROUND(AVG(pay_ratio_2024b), 4) AS mean_ratio,
                ROUND(AVG(trip_miles), 4) AS mean_miles,
                ROUND(AVG(trip_time / 60.0), 4) AS mean_min
            FROM '{UNIFIED}'
            WHERE source_month = '{ym}' AND platform = '{plat}'
        """).fetchone()
        n_t, n_b, mp, mr, mm, mt = r
        monthly_data.append({
            'month': ym, 'platform': plat,
            'n_trips': n_t, 'mode_bin': mode_bin,
            'bunching_pct': round(100.0 * n_b / n_t, 3) if n_t else 0,
            'mean_pay': mp, 'mean_ratio': mr,
            'mean_miles': mm, 'mean_min': mt
        })

with open(OUTDIR / "bunching_monthly.csv", 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(monthly_data[0].keys()))
    w.writeheader(); w.writerows(monthly_data)
print(f"  Saved {OUTDIR / 'bunching_monthly.csv'}: {len(monthly_data)} rows")

# Print monthly table
by_m = {}
for r in monthly_data:
    by_m.setdefault(r['month'], {})[r['platform']] = r
print(f"\n  {'Month':<8} {'Lyft mode':>10} {'Lyft pct':>10} {'Lyft pay':>10} {'Uber mode':>10} {'Uber pct':>10} {'Uber pay':>10}")
for ym in sorted(by_m.keys()):
    l = by_m[ym].get('Lyft', {})
    u = by_m[ym].get('Uber', {})
    print(f"  {ym:<8} {l.get('mode_bin', 0):>10.2f} {l.get('bunching_pct', 0):>9.1f}% ${l.get('mean_pay', 0):>8.2f} {u.get('mode_bin', 0):>10.2f} {u.get('bunching_pct', 0):>9.1f}% ${u.get('mean_pay', 0):>8.2f}")

# ---- Step 3: July vs August 2025 distribution (Figure 2 data) ----
print("\nJuly vs August 2025 distribution...")
dist = []
for ym in ['2025-07', '2025-08']:
    for plat in ['Lyft', 'Uber']:
        rows = con.execute(f"""
            WITH binned AS (
                SELECT CAST(FLOOR(pay_ratio_2024b * 100) / 100.0 AS DECIMAL(5,2)) AS bin
                FROM '{UNIFIED}'
                WHERE source_month = '{ym}' AND platform = '{plat}'
                  AND pay_ratio_2024b BETWEEN 0.85 AND 1.35
            )
            SELECT bin, COUNT(*) FROM binned GROUP BY bin ORDER BY bin
        """).fetchall()
        total = sum(n for _, n in rows)
        for b, n in rows:
            dist.append({
                'month': ym, 'platform': plat,
                'bin': float(b), 'n': n,
                'pct': round(100.0 * n / total, 4) if total else 0
            })

with open(OUTDIR / "ratio_dist_jul_aug.csv", 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(dist[0].keys()))
    w.writeheader(); w.writerows(dist)
print(f"  Saved {OUTDIR / 'ratio_dist_jul_aug.csv'}: {len(dist)} rows")

# ---- Step 4: Spatial sanity (zone-level July vs August) ----
print("\nZone-level July vs August transition...")
zone_data = []
for ym in ['2025-07', '2025-08']:
    for plat in ['Lyft', 'Uber']:
        for zone in ['Yellow Zone', 'Boro Zone']:
            mode_q = con.execute(f"""
                WITH binned AS (
                    SELECT CAST(FLOOR(pay_ratio_2024b * 100) / 100.0 AS DECIMAL(5,2)) AS bin
                    FROM '{UNIFIED}'
                    WHERE source_month = '{ym}' AND platform = '{plat}' AND service_zone = '{zone}'
                      AND pay_ratio_2024b BETWEEN 0.90 AND 1.30
                )
                SELECT bin FROM binned GROUP BY bin ORDER BY COUNT(*) DESC LIMIT 1
            """).fetchone()
            if not mode_q:
                continue
            mode_bin = float(mode_q[0])
            r = con.execute(f"""
                SELECT
                    COUNT(*) AS n,
                    SUM(CASE WHEN pay_ratio_2024b BETWEEN {mode_bin - 0.02} AND {mode_bin + 0.02} THEN 1 ELSE 0 END) AS nb
                FROM '{UNIFIED}'
                WHERE source_month = '{ym}' AND platform = '{plat}' AND service_zone = '{zone}'
            """).fetchone()
            zone_data.append({
                'month': ym, 'platform': plat, 'zone': zone,
                'n_trips': r[0], 'mode_bin': mode_bin,
                'bunching_pct': round(100.0 * r[1] / r[0], 3) if r[0] else 0
            })

with open(OUTDIR / "bunching_by_zone.csv", 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(zone_data[0].keys()))
    w.writeheader(); w.writerows(zone_data)
print(f"  Saved {OUTDIR / 'bunching_by_zone.csv'}: {len(zone_data)} rows")

print(f"\n  {'Plat':<5} {'Zone':<12} {'Jul %':>8} {'Aug %':>8} {'Drop':>8}")
for plat in ['Lyft', 'Uber']:
    for zone in ['Yellow Zone', 'Boro Zone']:
        jul = next((r['bunching_pct'] for r in zone_data
                    if r['month']=='2025-07' and r['platform']==plat and r['zone']==zone), None)
        aug = next((r['bunching_pct'] for r in zone_data
                    if r['month']=='2025-08' and r['platform']==plat and r['zone']==zone), None)
        if jul is not None and aug is not None:
            print(f"  {plat:<5} {zone:<12} {jul:>7.1f}% {aug:>7.1f}% {jul-aug:>7.1f}pp")

# ---- Step 5: Summary stats by period (Table 1 data) ----
print("\nPeriod summary stats...")
periods = [
    ('2024 (paper 1 baseline)',  "source_month LIKE '2024-%'"),
    ('Pre (Jan-Jul 2025)',        "source_month BETWEEN '2025-01' AND '2025-07'"),
    ('Post (Aug 2025-Feb 2026)',  "(source_month BETWEEN '2025-08' AND '2025-12') OR (source_month LIKE '2026-%')"),
]
summary = []
for label, where in periods:
    for plat in ['Lyft', 'Uber']:
        r = con.execute(f"""
            SELECT
                COUNT(*) AS n,
                ROUND(AVG(trip_miles), 3) AS mean_miles,
                ROUND(AVG(trip_time / 60.0), 3) AS mean_min,
                ROUND(AVG(driver_pay), 3) AS mean_pay,
                ROUND(AVG(base_passenger_fare), 3) AS mean_fare,
                ROUND(AVG(pay_ratio_2024b), 4) AS mean_ratio
            FROM '{UNIFIED}'
            WHERE platform = '{plat}' AND {where}
        """).fetchone()
        summary.append({
            'period': label, 'platform': plat,
            'n_trips': r[0], 'mean_miles': r[1], 'mean_min': r[2],
            'mean_pay': r[3], 'mean_fare': r[4], 'mean_ratio': r[5]
        })

with open(OUTDIR / "summary_stats.csv", 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(summary[0].keys()))
    w.writeheader(); w.writerows(summary)
print(f"  Saved {OUTDIR / 'summary_stats.csv'}: {len(summary)} rows")

print(f"\n  {'Period':<28} {'Plat':<5} {'N':>14} {'Pay':>8} {'Fare':>8} {'Ratio':>7}")
for r in summary:
    print(f"  {r['period']:<28} {r['platform']:<5} {r['n_trips']:>14,} ${r['mean_pay']:>6.2f} ${r['mean_fare']:>6.2f} {r['mean_ratio']:>7.4f}")

print(f"\nDone in {time.time() - t0:.0f}s. All output in {OUTDIR}")
