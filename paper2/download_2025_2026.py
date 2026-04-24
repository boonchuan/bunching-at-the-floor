"""
Download 2025 + early 2026 HVFHS files for paper 2.
Adds 14 monthly files to the existing C:\research\gig\data\hvfhs\ directory.
"""
import requests
from pathlib import Path
from tqdm import tqdm

DEST = Path(r"C:\research\gig\data\hvfhs")
DEST.mkdir(parents=True, exist_ok=True)

BASE_URL = "https://d37ci6vzurychx.cloudfront.net/trip-data/fhvhv_tripdata_{ym}.parquet"

# 2025 full year + Jan-Feb 2026
months = []
for y, m_start, m_end in [(2025, 1, 12), (2026, 1, 2)]:
    for m in range(m_start, m_end + 1):
        months.append(f"{y}-{m:02d}")

print(f"Will download {len(months)} files: {months[0]} through {months[-1]}")

for ym in months:
    url = BASE_URL.format(ym=ym)
    out = DEST / f"fhvhv_tripdata_{ym}.parquet"

    if out.exists() and out.stat().st_size > 100_000_000:
        print(f"  [SKIP] {out.name} already exists ({out.stat().st_size / 1024 / 1024:.0f} MB)")
        continue

    print(f"  [GET]  {url}")
    try:
        r = requests.get(url, stream=True, timeout=60)
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        with open(out, "wb") as f:
            with tqdm(total=total, unit="B", unit_scale=True, desc=ym) as pbar:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    f.write(chunk)
                    pbar.update(len(chunk))
        print(f"  [OK]   {out.name} ({out.stat().st_size / 1024 / 1024:.0f} MB)")
    except Exception as e:
        print(f"  [FAIL] {ym}: {e}")
        if out.exists() and out.stat().st_size < 100_000_000:
            out.unlink()

print("\nDone. File inventory:")
for f in sorted(DEST.glob("fhvhv_tripdata_*.parquet")):
    print(f"  {f.name}  {f.stat().st_size / 1024 / 1024:.0f} MB")
