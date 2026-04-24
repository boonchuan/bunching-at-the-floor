"""
Patch enrich_2025_2026.py to use proper date arithmetic.
DuckDB returns interval differences as INT32 microseconds; we need EPOCH casts.
"""
from pathlib import Path

p = Path(r"C:\research\gig\enrich_2025_2026.py")
text = p.read_text(encoding="utf-8")

# Fix 1: days_from_rule (overflow in microsecond multiplication)
text = text.replace(
    "CAST((pickup_datetime - TIMESTAMP '2025-06-06')/(1000000 * 60 * 60 * 24) AS INTEGER) AS days_from_rule,",
    "CAST(DATE_DIFF('day', TIMESTAMP '2025-06-06', pickup_datetime) AS INTEGER) AS days_from_rule,"
)

# Fix 2: search_lat_s
text = text.replace(
    "CASE WHEN on_scene_datetime IS NOT NULL\n                THEN CAST((on_scene_datetime - request_datetime) / 1000000 AS INTEGER)\n                ELSE NULL\n            END AS search_lat_s,",
    "CASE WHEN on_scene_datetime IS NOT NULL\n                THEN CAST(DATE_DIFF('second', request_datetime, on_scene_datetime) AS INTEGER)\n                ELSE NULL\n            END AS search_lat_s,"
)

# Fix 3: board_lat_s
text = text.replace(
    "CASE WHEN on_scene_datetime IS NOT NULL\n                THEN CAST((pickup_datetime - on_scene_datetime) / 1000000 AS INTEGER)\n                ELSE NULL\n            END AS board_lat_s",
    "CASE WHEN on_scene_datetime IS NOT NULL\n                THEN CAST(DATE_DIFF('second', on_scene_datetime, pickup_datetime) AS INTEGER)\n                ELSE NULL\n            END AS board_lat_s"
)

p.write_text(text, encoding="utf-8")
print("Patched. Verifying changes:")
for line in text.splitlines():
    if "DATE_DIFF" in line:
        print(f"  {line.strip()}")
