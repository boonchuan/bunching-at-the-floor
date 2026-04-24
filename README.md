# Bunching at the Floor: Minimum Pay Compliance in NYC Ride-Hail, 2024

Replication materials for *Bunching at the Floor: Minimum Pay Compliance in NYC Ride-Hail, 2024* (Lim, 2026).

## What this repository contains

All scripts, aggregates, and metadata required to reproduce every figure and table in the paper, starting from the public NYC TLC High-Volume For-Hire Services (HVFHS) trip record dataset.

## Data source

This project does not archive the raw HVFHS parquet files, which total 5.5 GB compressed for 2024 and are already hosted on AWS by the NYC Taxi and Limousine Commission. The analysis scripts download them directly from:

- Trip records: https://d37ci6vzurychx.cloudfront.net/trip-data/fhvhv_tripdata_YYYY-MM.parquet
- Zone lookup: https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv
- TLC documentation: https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page

## System requirements

- Operating system: Windows, Linux, or macOS
- RAM: 16 GB minimum, 32 GB recommended
- Storage: 80 GB free (raw data + intermediate panels)
- Python 3.10 or newer

## Setup

```bash
python -m venv venv
# On Windows:
.\venv\Scripts\Activate.ps1
# On Linux/macOS:
source venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## How to reproduce

Run the scripts in order. Each is idempotent and will skip work that is already done.

```bash
# 1. Initial data audit (January 2024 only, ~5 min, 1.5 GB)
python audit_jan2024.py

# 2. Full 2024 download and panel build (~15 min, 5.5 GB)
python build_panels_2024.py

# 3. Welfare enrichment: add pay ratios, minima, take rates (~5 min)
python enrich_welfare.py

# 4. Main paper analysis: borough and service zone aggregates, figures (~5 min)
python paper_analysis.py

# 5. Appendix B analysis: excluded categories comparison (~2 min)
python appendix_b.py

# 6. Verification queries for v2 revisions (optional, ~2 min)
python verify_v2.py
```

Total end-to-end runtime: about 30 minutes on consumer hardware.

## Output locations

- Raw data: `data/hvfhs/`
- Intermediate panels: `data/panels/`
- Figures and tables: `output/`

## Files

| File | Description |
|------|-------------|
| `audit_jan2024.py` | Initial schema and field-nullness audit |
| `build_panels_2024.py` | Full-year download and trip-level panel construction |
| `enrich_welfare.py` | Adds pay ratio, minima under two regimes, take rates |
| `paper_analysis.py` | Borough and service zone aggregates, main figures |
| `appendix_b.py` | Comparison of excluded vs included trips |
| `verify_v2.py` | Verification queries for v2 paper revisions |
| `patch_plots.py` | Re-runs three specific plots |
| `fetch_zone_lookup.py` | Downloads TLC taxi zone lookup |
| `taxi_zone_lookup.csv` | Cached TLC zone classification |
| `requirements.txt` | Python dependencies |

## Key findings reproduced by these scripts

Running the scripts in order reproduces:

- Table 1: Analytical sample descriptives
- Table 2: Bunching shares under contemporaneous and retrospective utilisation
- Table 3: Service zone breakdown
- Table 4: Bunching bandwidth robustness
- Table 5: Rate regime robustness
- Figures 1-3 (JPAM version) / Figures 1-4 (SSRN version)
- Appendix tables A1 (borough-level) and B1 (excluded categories)

## Data dictionary

The HVFHS schema is documented by the NYC TLC at https://www.nyc.gov/assets/tlc/downloads/pdf/data_dictionary_trip_records_hvfhs.pdf. Key fields used in this analysis:

- `hvfhs_license_num`: Platform identifier (HV0003=Uber, HV0005=Lyft)
- `request_datetime`: When rider requested the trip
- `on_scene_datetime`: When driver arrived at pickup (Uber only)
- `pickup_datetime`: When passenger boarded
- `dropoff_datetime`: When trip ended
- `PULocationID` / `DOLocationID`: Pickup/dropoff taxi zones (1-263)
- `trip_miles`: Passenger miles
- `trip_time`: Passenger seconds
- `base_passenger_fare`: Rider base fare before tolls/taxes
- `driver_pay`: Driver earnings for the trip
- `shared_request_flag` / `shared_match_flag`: Shared-ride indicators

## AI tools used

The Python scripts in this repository were drafted with assistance from Anthropic's Claude and subsequently reviewed, tested, and modified by the author. All scripts have been executed end-to-end by the author on consumer hardware, and all numerical results in the paper derive from those executions.

## License

- Code: MIT License (see LICENSE)
- Data: The raw HVFHS data is provided by the NYC Taxi and Limousine Commission under NYC Open Data terms. Refer to the TLC's own terms for data reuse.

## Citation

If you use these replication materials, please cite:

> Lim, B. C. (2026). Bunching at the Floor: Minimum Pay Compliance in NYC Ride-Hail, 2024. Journal of Policy Analysis and Management. [Article DOI upon publication]
>
> Lim, B. C. (2026). Replication Package for "Bunching at the Floor: Minimum Pay Compliance in NYC Ride-Hail, 2024" [Data set]. Zenodo. https://doi.org/10.5281/zenodo.19719420

## Contact

Issues and questions: please open a GitHub issue on this repository.
