"""
Patch: regenerate plot 07 (take rate by trip length decile) and plots 08-09
which never ran due to the NTILE error.
"""
import time
from pathlib import Path
import duckdb
import numpy as np
import polars as pl
import matplotlib.pyplot as plt

PANEL_DIR = Path(r"C:\research\gig\data\panels")
OUT_DIR = Path(r"C:\research\gig\output")
TRIP_OUT = PANEL_DIR / "trips_2024_welfare.parquet"

con = duckdb.connect(database=":memory:")
con.execute("PRAGMA threads=12")
con.execute("PRAGMA memory_limit='20GB'")

filter_main = "non_shared = 1 AND in_city = 1 AND base_passenger_fare > 0 AND driver_pay > 0"

# Plot 7 fixed: compute NTILE in subquery, then aggregate
print("Plot 7: take rate by trip length decile")
df3 = con.execute(f"""
    SELECT
        platform,
        miles_decile,
        AVG(take_rate) AS mean_take,
        AVG(trip_miles) AS mean_miles
    FROM (
        SELECT
            platform,
            take_rate,
            trip_miles,
            NTILE(10) OVER (PARTITION BY platform ORDER BY trip_miles) AS miles_decile
        FROM '{TRIP_OUT}'
        WHERE {filter_main} AND take_rate BETWEEN 0 AND 0.8 AND trip_miles BETWEEN 0.1 AND 40
    )
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
print("  saved")

# Plot 8
print("Plot 8: share below $16/hr equivalent by hour")
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
print("  saved")

# Plot 9: bunching by zone type
print("Plot 9: bunching by zone group")
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
print("  saved")
