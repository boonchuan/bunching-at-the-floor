"""
NYC HVFHS 2024 welfare enrichment.

Adds per-trip welfare columns to the base panel:
  - TLC theoretical minimum pay (time-varying rates within 2024)
  - Two utilisation regimes: contemporaneous (~58%) and retrospective (TLC 2025 values)
  - pay_ratio: actual / minimum
  - net_after_expenses: driver_pay - trip_miles * 0.789 (TLC's own 2024 expense factor)
  - Comparison to NYC $16/hr statutory minimum wage benchmark

Restricts to non-shared, in-city trips for main analysis.
Shared and out-of-city preserved in full panel for appendix robustness.

Rate regimes (2024):
  Jan 1 - Feb 29: $0.326/min, $0.759/mile  (prior to CPI-W adjustment)
  Mar 1 - Dec 31: $0.338/min, $0.789/mile  (post CPI-W adjustment)

Utilisation regimes:
  Contemporaneous: 58% (approximate industry reported, before TLC's 2025 finding)
  Retrospective:   time=53.3%, distance=68.5% (TLC 2025 clean baseline)

Sources:
  Parrott (Dec 2024), Revised TLC HV-FHV Minimum Pay Standard Expense Model
  TLC proposed amendment 12/26/2024 (published in NYC Rules, Jan 3 2025)
"""
import time
from pathlib import Path
import duckdb
import numpy as np
import polars as pl
import matplotlib.pyplot as plt

PANEL_DIR = Path(r"C:\research\gig\data\panels")
OUT_DIR = Path(r"C:\research\gig\output")
OUT_DIR.mkdir(parents=True, exist_ok=True)

TRIP_IN = PANEL_DIR / "trips_2024.parquet"
TRIP_OUT = PANEL_DIR / "trips_2024_welfare.parquet"

con = duckdb.connect(database=":memory:")
con.execute("PRAGMA threads=12")
con.execute("PRAGMA memory_limit='20GB'")

# 1. Build enriched trip panel
print("=" * 60)
print("Phase 1: Enrich trip panel with welfare fields")
print("=" * 60)

if TRIP_OUT.exists():
    print(f"  cached  {TRIP_OUT.name}")
else:
    t0 = time.time()
    con.execute(f"""
        COPY (
            SELECT
                *,
                -- Per-minute and per-mile rates by rate regime
                CASE
                    WHEN request_datetime < TIMESTAMP '2024-03-01' THEN 0.326
                    ELSE 0.338
                END AS rate_per_min,
                CASE
                    WHEN request_datetime < TIMESTAMP '2024-03-01' THEN 0.759
                    ELSE 0.789
                END AS rate_per_mile,

                -- Contemporaneous utilisation regime (industry-reported, ~58%)
                (trip_miles * (CASE WHEN request_datetime < TIMESTAMP '2024-03-01' THEN 0.759 ELSE 0.789 END) / 0.58
                 + (trip_time / 60.0) * (CASE WHEN request_datetime < TIMESTAMP '2024-03-01' THEN 0.326 ELSE 0.338 END) / 0.58
                ) AS min_pay_contemp,

                -- Retrospective utilisation regime (TLC 2025 clean baseline: 68.5% distance, 53.3% time)
                (trip_miles * (CASE WHEN request_datetime < TIMESTAMP '2024-03-01' THEN 0.759 ELSE 0.789 END) / 0.685
                 + (trip_time / 60.0) * (CASE WHEN request_datetime < TIMESTAMP '2024-03-01' THEN 0.326 ELSE 0.338 END) / 0.533
                ) AS min_pay_retro,

                -- Net of TLC's own 2024 expense factor ($0.789/mile non-WAV)
                (driver_pay - trip_miles * 0.789) AS net_after_expenses,

                -- Implied per-passenger-minute pay net of expenses (dollars per minute)
                (driver_pay - trip_miles * 0.789) / NULLIF(trip_time / 60.0, 0) AS net_per_min,

                -- Platform take rate (fraction of base_passenger_fare retained by platform)
                (base_passenger_fare - driver_pay) / NULLIF(base_passenger_fare, 0) AS take_rate,

                -- In-city flag: both pickup and dropoff in standard NYC zones (1-263)
                CASE WHEN pu_zone BETWEEN 1 AND 263 AND do_zone BETWEEN 1 AND 263 THEN 1 ELSE 0 END AS in_city,

                -- Non-shared flag (trip was not requested or matched as shared)
                CASE WHEN (shared_request_flag IS NULL OR shared_request_flag IN ('N', 'n'))
                      AND (shared_match_flag IS NULL OR shared_match_flag IN ('N', 'n'))
                     THEN 1 ELSE 0 END AS non_shared

            FROM '{TRIP_IN}'
        ) TO '{TRIP_OUT}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    print(f"  built   {TRIP_OUT.name} in {time.time()-t0:.1f}s")

n = con.execute(f"SELECT COUNT(*) FROM '{TRIP_OUT}'").fetchone()[0]
print(f"  rows    {n:,}")

# Filter masks for main analysis subset
filter_main = "non_shared = 1 AND in_city = 1 AND base_passenger_fare > 0 AND driver_pay > 0"
n_main = con.execute(f"SELECT COUNT(*) FROM '{TRIP_OUT}' WHERE {filter_main}").fetchone()[0]
print(f"  main    {n_main:,} ({100*n_main/n:.1f}% of total) non-shared in-city with positive fare/pay")

# 2. Summary statistics
print("\n" + "=" * 60)
print("Phase 2: Summary statistics (main analysis subset)")
print("=" * 60)

print("\nPay ratio: driver_pay / min_pay (contemporaneous utilisation = 0.58)")
stats = con.execute(f"""
    SELECT
        platform,
        COUNT(*) AS n,
        ROUND(AVG(driver_pay / NULLIF(min_pay_contemp, 0)), 4) AS mean_ratio,
        ROUND(quantile_cont(driver_pay / NULLIF(min_pay_contemp, 0), 0.1), 4) AS p10,
        ROUND(quantile_cont(driver_pay / NULLIF(min_pay_contemp, 0), 0.5), 4) AS p50,
        ROUND(quantile_cont(driver_pay / NULLIF(min_pay_contemp, 0), 0.9), 4) AS p90,
        ROUND(100.0 * SUM(CASE WHEN driver_pay / NULLIF(min_pay_contemp, 0) BETWEEN 0.98 AND 1.02 THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_at_min
    FROM '{TRIP_OUT}'
    WHERE {filter_main}
    GROUP BY platform
    ORDER BY platform
""").fetchall()
print(f"  {'platform':<8} {'n':>12} {'mean':>7} {'p10':>7} {'p50':>7} {'p90':>7} {'pct_at_min':>10}")
for row in stats:
    p, n_, mean, p10, p50, p90, pct = row
    print(f"  {p:<8} {n_:>12,} {mean:>7.4f} {p10:>7.4f} {p50:>7.4f} {p90:>7.4f} {pct:>9.2f}%")

print("\nPay ratio under retrospective utilisation (TLC 2025 values: time=53.3%, distance=68.5%)")
stats_retro = con.execute(f"""
    SELECT
        platform,
        COUNT(*) AS n,
        ROUND(AVG(driver_pay / NULLIF(min_pay_retro, 0)), 4) AS mean_ratio,
        ROUND(quantile_cont(driver_pay / NULLIF(min_pay_retro, 0), 0.1), 4) AS p10,
        ROUND(quantile_cont(driver_pay / NULLIF(min_pay_retro, 0), 0.5), 4) AS p50,
        ROUND(quantile_cont(driver_pay / NULLIF(min_pay_retro, 0), 0.9), 4) AS p90,
        ROUND(100.0 * SUM(CASE WHEN driver_pay / NULLIF(min_pay_retro, 0) BETWEEN 0.98 AND 1.02 THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_at_min
    FROM '{TRIP_OUT}'
    WHERE {filter_main}
    GROUP BY platform
    ORDER BY platform
""").fetchall()
print(f"  {'platform':<8} {'n':>12} {'mean':>7} {'p10':>7} {'p50':>7} {'p90':>7} {'pct_at_min':>10}")
for row in stats_retro:
    p, n_, mean, p10, p50, p90, pct = row
    print(f"  {p:<8} {n_:>12,} {mean:>7.4f} {p10:>7.4f} {p50:>7.4f} {p90:>7.4f} {pct:>9.2f}%")

print("\nPlatform take rate (base_passenger_fare - driver_pay) / base_passenger_fare")
tr = con.execute(f"""
    SELECT
        platform,
        ROUND(AVG(take_rate), 4) AS mean_take,
        ROUND(quantile_cont(take_rate, 0.1), 4) AS p10,
        ROUND(quantile_cont(take_rate, 0.5), 4) AS p50,
        ROUND(quantile_cont(take_rate, 0.9), 4) AS p90
    FROM '{TRIP_OUT}'
    WHERE {filter_main} AND take_rate BETWEEN -0.5 AND 1.0
    GROUP BY platform
    ORDER BY platform
""").fetchall()
print(f"  {'platform':<8} {'mean':>7} {'p10':>7} {'p50':>7} {'p90':>7}")
for row in tr:
    p, mean, p10, p50, p90 = row
    print(f"  {p:<8} {mean:>7.4f} {p10:>7.4f} {p50:>7.4f} {p90:>7.4f}")

print("\nNet pay per passenger-minute (after $0.789/mile expense factor)")
print("NYC statutory minimum wage 2024: $16.00/hr = $0.267/min")
np_stats = con.execute(f"""
    SELECT
        platform,
        ROUND(AVG(net_per_min), 4) AS mean_npm,
        ROUND(quantile_cont(net_per_min, 0.1), 4) AS p10,
        ROUND(quantile_cont(net_per_min, 0.5), 4) AS p50,
        ROUND(quantile_cont(net_per_min, 0.9), 4) AS p90,
        ROUND(100.0 * SUM(CASE WHEN net_per_min < 16.0/60.0 THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_below_min_wage
    FROM '{TRIP_OUT}'
    WHERE {filter_main} AND trip_time > 60 AND net_per_min BETWEEN -5 AND 5
    GROUP BY platform
    ORDER BY platform
""").fetchall()
print(f"  {'platform':<8} {'mean':>7} {'p10':>7} {'p50':>7} {'p90':>7} {'<$16/hr':>10}")
for row in np_stats:
    p, mean, p10, p50, p90, pct = row
    print(f"  {p:<8} {mean:>7.4f} {p10:>7.4f} {p50:>7.4f} {p90:>7.4f} {pct:>9.2f}%")

# 3. Zone-platform welfare aggregates
print("\n" + "=" * 60)
print("Phase 3: Zone-level welfare aggregates")
print("=" * 60)

zone_welfare = PANEL_DIR / "zone_welfare_2024.parquet"
if zone_welfare.exists():
    print(f"  cached  {zone_welfare.name}")
else:
    t0 = time.time()
    con.execute(f"""
        COPY (
            SELECT
                pu_zone,
                platform,
                COUNT(*) AS n_trips,
                AVG(driver_pay / NULLIF(min_pay_contemp, 0)) AS mean_ratio_contemp,
                AVG(driver_pay / NULLIF(min_pay_retro, 0)) AS mean_ratio_retro,
                AVG(take_rate) AS mean_take_rate,
                AVG(net_per_min) AS mean_net_per_min,
                AVG(driver_pay) AS mean_driver_pay,
                AVG(trip_miles) AS mean_miles,
                AVG(trip_time / 60.0) AS mean_minutes,
                100.0 * SUM(CASE WHEN driver_pay / NULLIF(min_pay_contemp, 0) BETWEEN 0.98 AND 1.02 THEN 1 ELSE 0 END) / COUNT(*) AS pct_at_min_contemp,
                100.0 * SUM(CASE WHEN net_per_min < 16.0/60.0 THEN 1 ELSE 0 END) / COUNT(*) AS pct_below_min_wage
            FROM '{TRIP_OUT}'
            WHERE {filter_main} AND trip_time > 60
            GROUP BY pu_zone, platform
        ) TO '{zone_welfare}' (FORMAT PARQUET)
    """)
    print(f"  built   {zone_welfare.name} in {time.time()-t0:.1f}s")

# 4. Plots
print("\n" + "=" * 60)
print("Phase 4: Diagnostic plots")
print("=" * 60)

# Plot 1: pay ratio distribution, by platform, contemporaneous utilisation
df1 = con.execute(f"""
    SELECT platform, driver_pay / NULLIF(min_pay_contemp, 0) AS ratio
    FROM '{TRIP_OUT}'
    WHERE {filter_main} AND min_pay_contemp > 0
      AND driver_pay / min_pay_contemp BETWEEN 0.5 AND 3.0
    USING SAMPLE 1000000 ROWS
""").pl()

fig, ax = plt.subplots(figsize=(9, 5.5))
bins = np.linspace(0.5, 3.0, 100)
for platform, color in [("Uber", "#1f77b4"), ("Lyft", "#ff7f0e")]:
    sub = df1.filter(pl.col("platform") == platform)["ratio"].to_numpy()
    ax.hist(sub, bins=bins, alpha=0.55, label=f"{platform} (n={len(sub):,})",
            color=color, edgecolor="none", density=True)
ax.axvline(1.0, color="red", linestyle="--", alpha=0.7, label="Minimum (ratio=1.0)")
ax.set_xlabel("driver_pay / TLC minimum pay (contemporaneous utilisation = 0.58)")
ax.set_ylabel("Density")
ax.set_title("Distribution of pay ratios, NYC HVFHS 2024\n(non-shared in-city trips)")
ax.legend()
ax.grid(True, alpha=0.3)
fig.savefig(OUT_DIR / "05_pay_ratio_distribution.png", dpi=120, bbox_inches="tight")
plt.close()
print("  plot 05 pay_ratio_distribution.png")

# Plot 2: bunching zoom near the minimum
df2 = con.execute(f"""
    SELECT platform, driver_pay / NULLIF(min_pay_contemp, 0) AS ratio
    FROM '{TRIP_OUT}'
    WHERE {filter_main} AND min_pay_contemp > 0
      AND driver_pay / min_pay_contemp BETWEEN 0.85 AND 1.25
    USING SAMPLE 1000000 ROWS
""").pl()

fig, ax = plt.subplots(figsize=(9, 5.5))
bins = np.linspace(0.85, 1.25, 80)
for platform, color in [("Uber", "#1f77b4"), ("Lyft", "#ff7f0e")]:
    sub = df2.filter(pl.col("platform") == platform)["ratio"].to_numpy()
    ax.hist(sub, bins=bins, alpha=0.55, label=f"{platform} (n={len(sub):,})",
            color=color, edgecolor="none", density=True)
ax.axvline(1.0, color="red", linestyle="--", alpha=0.7, label="Minimum (ratio=1.0)")
ax.set_xlabel("driver_pay / TLC minimum pay")
ax.set_ylabel("Density")
ax.set_title("Bunching near the TLC minimum pay floor\n(non-shared in-city, contemporaneous utilisation)")
ax.legend()
ax.grid(True, alpha=0.3)
fig.savefig(OUT_DIR / "06_bunching_zoom.png", dpi=120, bbox_inches="tight")
plt.close()
print("  plot 06 bunching_zoom.png")

# Plot 3: take rate by trip length decile
df3 = con.execute(f"""
    SELECT
        platform,
        NTILE(10) OVER (PARTITION BY platform ORDER BY trip_miles) AS miles_decile,
        AVG(take_rate) AS mean_take,
        AVG(trip_miles) AS mean_miles
    FROM '{TRIP_OUT}'
    WHERE {filter_main} AND take_rate BETWEEN 0 AND 0.8 AND trip_miles BETWEEN 0.1 AND 40
    GROUP BY platform, miles_decile
    ORDER BY platform, miles_decile
""").pl()

fig, ax = plt.subplots(figsize=(9, 5.5))
for platform, marker, color in [("Uber", "o", "#1f77b4"), ("Lyft", "s", "#ff7f0e")]:
    sub = df3.filter(pl.col("platform") == platform)
    ax.plot(sub["mean_miles"], sub["mean_take"], marker=marker, color=color, label=platform, markersize=8)
ax.set_xlabel("Mean trip miles (by decile)")
ax.set_ylabel("Mean platform take rate")
ax.set_title("Platform take rate by trip length, NYC HVFHS 2024")
ax.legend()
ax.grid(True, alpha=0.3)
fig.savefig(OUT_DIR / "07_take_rate_by_miles.png", dpi=120, bbox_inches="tight")
plt.close()
print("  plot 07 take_rate_by_miles.png")

# Plot 4: share below $16/hr minimum wage equivalent by hour-of-day
df4 = con.execute(f"""
    SELECT
        platform,
        hr,
        100.0 * SUM(CASE WHEN net_per_min < 16.0/60.0 THEN 1 ELSE 0 END) / COUNT(*) AS pct_below
    FROM '{TRIP_OUT}'
    WHERE {filter_main} AND trip_time > 60 AND net_per_min BETWEEN -5 AND 5
    GROUP BY platform, hr
    ORDER BY platform, hr
""").pl()

fig, ax = plt.subplots(figsize=(9, 5.5))
for platform, marker, color in [("Uber", "o", "#1f77b4"), ("Lyft", "s", "#ff7f0e")]:
    sub = df4.filter(pl.col("platform") == platform)
    ax.plot(sub["hr"], sub["pct_below"], marker=marker, color=color, label=platform, markersize=6)
ax.set_xlabel("Hour of day (UTC of request)")
ax.set_ylabel("% of trips with net_per_min < $16/hr equivalent")
ax.set_title("Share of trips paying below NYC statutory minimum wage equivalent\nafter TLC expense deduction ($0.789/mile)")
ax.legend()
ax.grid(True, alpha=0.3)
fig.savefig(OUT_DIR / "08_pct_below_min_wage.png", dpi=120, bbox_inches="tight")
plt.close()
print("  plot 08 pct_below_min_wage.png")

# Plot 5: pay ratio by zone type (load zone lookup if possible; else by zone ID bucket)
# Simplified: split zones into Manhattan (1-164 approx) vs outer boroughs (rest)
df5 = con.execute(f"""
    SELECT
        platform,
        CASE
            WHEN pu_zone IN (4,12,13,24,41,42,43,45,48,50,68,74,75,79,87,88,90,100,103,104,105,107,113,114,116,120,125,127,128,137,140,141,142,143,144,148,151,152,153,158,161,162,163,164,166,170,186,194,202,209,211,224,229,230,231,232,233,234,236,237,238,239,243,244,246,249,261,262,263) THEN 'Manhattan'
            ELSE 'Outer'
        END AS zone_group,
        AVG(driver_pay / NULLIF(min_pay_contemp, 0)) AS mean_ratio,
        100.0 * SUM(CASE WHEN driver_pay / NULLIF(min_pay_contemp, 0) BETWEEN 0.98 AND 1.02 THEN 1 ELSE 0 END) / COUNT(*) AS pct_at_min
    FROM '{TRIP_OUT}'
    WHERE {filter_main} AND min_pay_contemp > 0
    GROUP BY platform, zone_group
    ORDER BY platform, zone_group
""").pl()

print("\n  Pay ratio and bunching by zone group:")
for row in df5.iter_rows(named=True):
    print(f"    {row['platform']:<8} {row['zone_group']:<10} mean_ratio={row['mean_ratio']:.4f}  pct_at_min={row['pct_at_min']:.2f}%")

fig, ax = plt.subplots(figsize=(8, 5))
x = np.arange(2)
width = 0.35
manh = df5.filter(pl.col("zone_group") == "Manhattan").sort("platform")
outr = df5.filter(pl.col("zone_group") == "Outer").sort("platform")
ax.bar(x - width/2, manh["pct_at_min"], width, label="Manhattan", color="#2ca02c")
ax.bar(x + width/2, outr["pct_at_min"], width, label="Outer boroughs", color="#d62728")
ax.set_xticks(x)
ax.set_xticklabels(manh["platform"])
ax.set_ylabel("% of trips at TLC minimum (ratio 0.98-1.02)")
ax.set_title("Bunching at TLC minimum pay by zone group, NYC HVFHS 2024")
ax.legend()
ax.grid(True, alpha=0.3, axis="y")
fig.savefig(OUT_DIR / "09_bunching_by_zone.png", dpi=120, bbox_inches="tight")
plt.close()
print("  plot 09 bunching_by_zone.png")

print("\n" + "=" * 60)
print("Enrichment complete.")
print("=" * 60)
for f in PANEL_DIR.glob("*.parquet"):
    sz = f.stat().st_size / 1024 / 1024
    print(f"  {f.name:<40} {sz:>7.1f} MB")
print(f"\nPlots written to {OUT_DIR}")
