"""
Schema audit: compare 2024 vs 2025 vs 2026 HVFHS schemas.
Identifies new columns, removed columns, and type changes.
"""
import duckdb
from pathlib import Path

DATA = Path(r"C:\research\gig\data\hvfhs")
con = duckdb.connect(":memory:")

samples = {
    "2024-01": DATA / "fhvhv_tripdata_2024-01.parquet",
    "2024-12": DATA / "fhvhv_tripdata_2024-12.parquet",
    "2025-01": DATA / "fhvhv_tripdata_2025-01.parquet",
    "2025-06": DATA / "fhvhv_tripdata_2025-06.parquet",
    "2025-12": DATA / "fhvhv_tripdata_2025-12.parquet",
    "2026-01": DATA / "fhvhv_tripdata_2026-01.parquet",
    "2026-02": DATA / "fhvhv_tripdata_2026-02.parquet",
}

schemas = {}
for label, path in samples.items():
    if not path.exists():
        print(f"MISSING: {path}")
        continue
    cols = con.execute(f"DESCRIBE SELECT * FROM '{path}' LIMIT 0").fetchall()
    schemas[label] = {c[0]: c[1] for c in cols}

# Build union of all columns
all_cols = sorted(set().union(*[set(s.keys()) for s in schemas.values()]))

# Print presence matrix
print(f"\n{'Column':<32} " + " ".join(f"{lbl:>8}" for lbl in schemas.keys()))
print("-" * (32 + 9 * len(schemas)))
for col in all_cols:
    presence = " ".join(
        f"{'YES' if col in s else '-':>8}"
        for s in schemas.values()
    )
    print(f"{col:<32} {presence}")

# Spot type changes
print("\n--- Type differences across versions ---")
type_diffs = []
for col in all_cols:
    types = {lbl: s.get(col) for lbl, s in schemas.items() if col in s}
    if len(set(types.values())) > 1:
        type_diffs.append((col, types))

if type_diffs:
    for col, types in type_diffs:
        print(f"  {col}:")
        for lbl, t in types.items():
            print(f"    {lbl}: {t}")
else:
    print("  No type differences detected. Good.")

# Quick row count check on most recent files
print("\n--- Row counts ---")
for label in ["2025-06", "2025-07", "2026-01", "2026-02"]:
    path = samples.get(label)
    if path and path.exists():
        n = con.execute(f"SELECT COUNT(*) FROM '{path}'").fetchone()[0]
        print(f"  {label}: {n:,} trips")

# Check whether June 2025 contains the rule-change boundary cleanly
print("\n--- June 2025 daily volume (to verify date span) ---")
daily = con.execute(f"""
    SELECT
        CAST(pickup_datetime AS DATE) AS dt,
        COUNT(*) AS n
    FROM '{samples["2025-06"]}'
    WHERE pickup_datetime BETWEEN '2025-06-01' AND '2025-06-30'
    GROUP BY 1
    ORDER BY 1
""").fetchall()
for dt, n in daily:
    marker = " <-- rule effective" if str(dt) == "2025-06-06" else ""
    print(f"  {dt}: {n:>10,}{marker}")
