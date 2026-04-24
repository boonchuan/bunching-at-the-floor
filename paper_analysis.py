"""
Finalise analysis for 'Bunching at the Floor' paper.

Adds:
 - Borough-level bunching using TLC taxi_zone_lookup.csv
 - Service zone split (Yellow Zone / Boro Zone / Airports)
 - Uber-only unpaid-time decomposition (search + boarding)
 - Rate-regime robustness (pre-March vs post-March 2024)

All aggregates are saved as parquet for re-use in draft figures.
"""
import time
from pathlib import Path
import duckdb
import numpy as np
import polars as pl
import matplotlib.pyplot as plt

PANEL_DIR = Path(r"C:\research\gig\data\panels")
DATA_DIR = Path(r"C:\research\gig\data")
OUT_DIR = Path(r"C:\research\gig\output")
OUT_DIR.mkdir(parents=True, exist_ok=True)

TRIP = PANEL_DIR / "trips_2024_welfare.parquet"
ZONE = DATA_DIR / "taxi_zone_lookup.csv"

con = duckdb.connect(database=":memory:")
con.execute("PRAGMA threads=12")
con.execute("PRAGMA memory_limit='20GB'")

# Register the zone lookup as a view
con.execute(f"""
    CREATE VIEW zones AS
    SELECT LocationID AS zone_id, Borough, Zone AS zone_name, service_zone
    FROM read_csv('{ZONE}', header=true)
""")

filter_main = "non_shared = 1 AND in_city = 1 AND base_passenger_fare > 0 AND driver_pay > 0"

# ========================================================================
# 1. Borough-level bunching
# ========================================================================
print("=" * 60)
print("1. Borough-level bunching")
print("=" * 60)

borough_tbl = con.execute(f"""
    SELECT
        z.Borough,
        t.platform,
        COUNT(*) AS n_trips,
        ROUND(AVG(t.driver_pay / NULLIF(t.min_pay_contemp, 0)), 4) AS mean_ratio_contemp,
        ROUND(AVG(t.driver_pay / NULLIF(t.min_pay_retro, 0)), 4) AS mean_ratio_retro,
        ROUND(100.0 * SUM(CASE WHEN t.driver_pay / NULLIF(t.min_pay_contemp, 0) BETWEEN 0.98 AND 1.02 THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_at_min_contemp,
        ROUND(100.0 * SUM(CASE WHEN t.driver_pay / NULLIF(t.min_pay_retro, 0) BETWEEN 0.98 AND 1.02 THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_at_min_retro,
        ROUND(AVG(t.driver_pay), 2) AS mean_driver_pay,
        ROUND(AVG(t.trip_miles), 2) AS mean_miles
    FROM '{TRIP}' t
    JOIN zones z ON t.pu_zone = z.zone_id
    WHERE {filter_main} AND z.Borough NOT IN ('Unknown', 'N/A', 'EWR')
    GROUP BY z.Borough, t.platform
    ORDER BY z.Borough, t.platform
""").pl()

print(borough_tbl)
borough_tbl.write_parquet(PANEL_DIR / "borough_bunching_2024.parquet")

# Plot: borough x platform bunching
fig, ax = plt.subplots(figsize=(10, 5.5))
boroughs = ["Manhattan", "Brooklyn", "Queens", "Bronx", "Staten Island"]
x = np.arange(len(boroughs))
width = 0.35

uber_vals = [borough_tbl.filter((pl.col("Borough") == b) & (pl.col("platform") == "Uber"))["pct_at_min_contemp"][0] for b in boroughs]
lyft_vals = [borough_tbl.filter((pl.col("Borough") == b) & (pl.col("platform") == "Lyft"))["pct_at_min_contemp"][0] for b in boroughs]

ax.bar(x - width/2, uber_vals, width, label="Uber", color="#1f77b4")
ax.bar(x + width/2, lyft_vals, width, label="Lyft", color="#ff7f0e")
ax.set_xticks(x)
ax.set_xticklabels(boroughs)
ax.set_ylabel("% of trips at TLC minimum (ratio 0.98-1.02)")
ax.set_title("Bunching at TLC minimum pay by pickup borough\nNYC HVFHS 2024, contemporaneous utilisation (0.58)")
ax.legend()
ax.grid(True, alpha=0.3, axis="y")
for i, (u, l) in enumerate(zip(uber_vals, lyft_vals)):
    ax.text(i - width/2, u + 0.5, f"{u:.1f}", ha="center", fontsize=9)
    ax.text(i + width/2, l + 0.5, f"{l:.1f}", ha="center", fontsize=9)
fig.savefig(OUT_DIR / "10_bunching_by_borough.png", dpi=120, bbox_inches="tight")
plt.close()
print(f"  saved plot 10_bunching_by_borough.png")

# ========================================================================
# 2. Service zone breakdown (Yellow Zone / Boro Zone)
# ========================================================================
print("\n" + "=" * 60)
print("2. Service zone breakdown")
print("=" * 60)

sz_tbl = con.execute(f"""
    SELECT
        z.service_zone,
        t.platform,
        COUNT(*) AS n_trips,
        ROUND(AVG(t.driver_pay / NULLIF(t.min_pay_contemp, 0)), 4) AS mean_ratio,
        ROUND(100.0 * SUM(CASE WHEN t.driver_pay / NULLIF(t.min_pay_contemp, 0) BETWEEN 0.98 AND 1.02 THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_at_min,
        ROUND(AVG(t.driver_pay), 2) AS mean_driver_pay,
        ROUND(AVG(t.trip_miles), 2) AS mean_miles,
        ROUND(AVG(t.trip_time / 60.0), 1) AS mean_minutes
    FROM '{TRIP}' t
    JOIN zones z ON t.pu_zone = z.zone_id
    WHERE {filter_main} AND z.service_zone IN ('Yellow Zone', 'Boro Zone', 'Airports')
    GROUP BY z.service_zone, t.platform
    ORDER BY z.service_zone, t.platform
""").pl()

print(sz_tbl)
sz_tbl.write_parquet(PANEL_DIR / "service_zone_bunching_2024.parquet")

# ========================================================================
# 3. Rate regime robustness
# ========================================================================
print("\n" + "=" * 60)
print("3. Rate regime robustness (Jan-Feb vs Mar-Dec 2024)")
print("=" * 60)

regime_tbl = con.execute(f"""
    SELECT
        CASE WHEN request_datetime < TIMESTAMP '2024-03-01' THEN 'Jan-Feb (old rates)' ELSE 'Mar-Dec (new rates)' END AS regime,
        platform,
        COUNT(*) AS n_trips,
        ROUND(AVG(driver_pay / NULLIF(min_pay_contemp, 0)), 4) AS mean_ratio,
        ROUND(100.0 * SUM(CASE WHEN driver_pay / NULLIF(min_pay_contemp, 0) BETWEEN 0.98 AND 1.02 THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_at_min
    FROM '{TRIP}'
    WHERE {filter_main}
    GROUP BY regime, platform
    ORDER BY regime, platform
""").pl()

print(regime_tbl)
regime_tbl.write_parquet(PANEL_DIR / "regime_robustness_2024.parquet")

# ========================================================================
# 4. Uber-only unpaid time decomposition
# ========================================================================
print("\n" + "=" * 60)
print("4. Unpaid time decomposition (Uber subsample with on_scene_datetime)")
print("=" * 60)

decomp_tbl = con.execute(f"""
    SELECT
        COUNT(*) AS n_trips,
        -- Paid time: on-trip (pickup to dropoff) in minutes
        ROUND(AVG(trip_time / 60.0), 2) AS mean_paid_min,
        ROUND(quantile_cont(trip_time / 60.0, 0.5), 2) AS p50_paid_min,
        -- Unpaid approach: request to on_scene in minutes
        ROUND(AVG(search_lat_s / 60.0), 2) AS mean_search_min,
        ROUND(quantile_cont(search_lat_s / 60.0, 0.5), 2) AS p50_search_min,
        -- Unpaid boarding: on_scene to pickup in minutes
        ROUND(AVG(board_lat_s / 60.0), 2) AS mean_board_min,
        ROUND(quantile_cont(board_lat_s / 60.0, 0.5), 2) AS p50_board_min,
        -- Total unpaid share
        ROUND(AVG((search_lat_s + board_lat_s) / NULLIF((search_lat_s + board_lat_s + trip_time), 0)), 4) AS mean_unpaid_share
    FROM '{TRIP}'
    WHERE {filter_main}
      AND platform = 'Uber'
      AND search_lat_s BETWEEN 30 AND 3600
      AND board_lat_s BETWEEN 0 AND 1800
      AND trip_time BETWEEN 60 AND 7200
""").pl()

print(decomp_tbl)

# Plot: stacked distribution of paid vs unpaid time
print("\n  Building decomposition plot...")
decomp_hourly = con.execute(f"""
    SELECT
        hr,
        AVG(search_lat_s / 60.0) AS mean_search_min,
        AVG(board_lat_s / 60.0) AS mean_board_min,
        AVG(trip_time / 60.0) AS mean_paid_min,
        COUNT(*) AS n_trips
    FROM '{TRIP}'
    WHERE {filter_main}
      AND platform = 'Uber'
      AND search_lat_s BETWEEN 30 AND 3600
      AND board_lat_s BETWEEN 0 AND 1800
      AND trip_time BETWEEN 60 AND 7200
    GROUP BY hr
    ORDER BY hr
""").pl()

fig, ax = plt.subplots(figsize=(10, 5.5))
hrs = decomp_hourly["hr"].to_numpy()
search = decomp_hourly["mean_search_min"].to_numpy()
board = decomp_hourly["mean_board_min"].to_numpy()
paid = decomp_hourly["mean_paid_min"].to_numpy()

ax.bar(hrs, search, label="Unpaid approach (request → on-scene)", color="#d62728")
ax.bar(hrs, board, bottom=search, label="Unpaid boarding (on-scene → pickup)", color="#ff7f0e")
ax.bar(hrs, paid, bottom=search + board, label="Paid trip time (pickup → dropoff)", color="#2ca02c")
ax.set_xlabel("Hour of day (UTC of request)")
ax.set_ylabel("Minutes per trip")
ax.set_title("Time composition per trip by hour of day, Uber NYC HVFHS 2024\n(trips retained: non-shared, in-city, with on_scene_datetime)")
ax.legend(loc="upper right")
ax.grid(True, alpha=0.3, axis="y")
fig.savefig(OUT_DIR / "11_time_composition.png", dpi=120, bbox_inches="tight")
plt.close()
print(f"  saved plot 11_time_composition.png")

# Distribution of unpaid share
unpaid_dist = con.execute(f"""
    SELECT (search_lat_s + board_lat_s) * 1.0 / NULLIF(search_lat_s + board_lat_s + trip_time, 0) AS unpaid_share
    FROM '{TRIP}'
    WHERE {filter_main}
      AND platform = 'Uber'
      AND search_lat_s BETWEEN 30 AND 3600
      AND board_lat_s BETWEEN 0 AND 1800
      AND trip_time BETWEEN 60 AND 7200
    USING SAMPLE 1000000 ROWS
""").pl()

fig, ax = plt.subplots(figsize=(9, 5.5))
ax.hist(unpaid_dist["unpaid_share"].to_numpy(), bins=60, edgecolor="none", color="#d62728", alpha=0.8)
ax.axvline(unpaid_dist["unpaid_share"].mean(), color="black", linestyle="--",
           label=f"Mean = {unpaid_dist['unpaid_share'].mean():.3f}")
ax.axvline(unpaid_dist["unpaid_share"].median(), color="black", linestyle=":",
           label=f"Median = {unpaid_dist['unpaid_share'].median():.3f}")
ax.set_xlabel("Unpaid time share = (search + boarding) / (search + boarding + trip_time)")
ax.set_ylabel("Trip count (sample of 1M)")
ax.set_title("Distribution of unpaid-time share per trip, Uber NYC HVFHS 2024")
ax.legend()
ax.grid(True, alpha=0.3)
fig.savefig(OUT_DIR / "12_unpaid_share_distribution.png", dpi=120, bbox_inches="tight")
plt.close()
print(f"  saved plot 12_unpaid_share_distribution.png")

# ========================================================================
# 5. Summary table for the paper
# ========================================================================
print("\n" + "=" * 60)
print("5. Headline numbers for paper abstract")
print("=" * 60)

summary = con.execute(f"""
    SELECT
        platform,
        COUNT(*) AS n_trips,
        ROUND(AVG(driver_pay / NULLIF(min_pay_contemp, 0)), 4) AS mean_ratio_contemp,
        ROUND(100.0 * SUM(CASE WHEN driver_pay / NULLIF(min_pay_contemp, 0) BETWEEN 0.98 AND 1.02 THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_at_min_contemp,
        ROUND(100.0 * SUM(CASE WHEN driver_pay / NULLIF(min_pay_retro, 0) BETWEEN 0.98 AND 1.02 THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_at_min_retro,
        ROUND(AVG(take_rate), 4) AS mean_take_rate,
        ROUND(AVG(driver_pay), 2) AS mean_driver_pay_usd,
        ROUND(AVG(base_passenger_fare), 2) AS mean_passenger_fare_usd
    FROM '{TRIP}'
    WHERE {filter_main}
    GROUP BY platform
    ORDER BY platform
""").pl()

print(summary)
summary.write_parquet(PANEL_DIR / "summary_2024.parquet")

print("\n" + "=" * 60)
print("Analysis complete. Paper-ready aggregates in:")
print(f"  {PANEL_DIR}")
print("Paper-ready plots in:")
print(f"  {OUT_DIR}")
print("=" * 60)
