"""Write paper2/README.md to disk. Run once, then delete this script."""
from pathlib import Path

CONTENT = r"""# Paper 2 replication: After the Floor Moved

This subdirectory contains the analysis scripts, CSV outputs, and reproduction instructions for:

**Lim, B. C. (2026). After the Floor Moved: NYC Ride-Hail Driver Pay Behaviour Following the Minimum Pay Rule Change of August 2025.**

This is the second paper in a two-paper series. The pre-rule baseline (2024 data, single regulatory regime) is the subject of the companion paper in the repository root; paper 2 extends the analysis to the post-rule period (January 2024 through February 2026, four regulatory regimes plus the January 2025 congestion-pricing program).

---

## What this code does

1. Downloads 14 months of TLC HVFHS parquet files (January 2025 through February 2026) from the AWS-hosted TLC distribution.
2. Audits schema changes and builds a combined 14-month panel (284 million trips).
3. Enriches the panel with a fixed-counterfactual minimum based on paper 1's March-December 2024 rate schedule ($0.789/mile, $0.338/min, single utilisation 0.58). This is the methodological key: a fixed yardstick isolates platform pay behaviour from the moving regulatory floor.
4. Stacks the 2024 and 2025-2026 panels into a single 482-million-trip, 26-month unified panel.
5. Produces the three headline analyses:
    - Monthly bunching time series (modal-bin +/- 2 percent window, platform-level, 26 months).
    - July 2025 vs August 2025 distribution comparison (raw pay-ratio bins 0.85-1.35).
    - Spatial sanity check (July vs August transition by service zone, ruling out congestion-pricing confound).
6. Generates Figures 1, 2, and 3 and Table 1 from the resulting CSVs.

Two verification scripts (`infer_contemp_rates.py`, `verify_august_transition.py`) are diagnostic - they recover the contemporaneous rate schedule from the data and verify the August 2025 transition before the main analysis. Running them is optional but they were used during development and are included for full transparency.

---

## Hardware and software requirements

- Python 3.10+
- DuckDB 0.10+
- Polars
- Matplotlib
- Disk: approximately 45 GB free (source parquets ~6 GB + enriched panels ~25 GB + intermediate files + outputs).
- RAM: 32 GB recommended. 16 GB will work with reduced DuckDB memory limits but slower.
- CPU: any modern multi-core machine. Full pipeline runs in ~25 minutes on a consumer desktop (Ryzen 5 7500F, 32 GB RAM) from a cold start.

Install dependencies:

    pip install duckdb polars matplotlib requests pyarrow

---

## End-to-end reproduction

Run the scripts in this order from the `paper2/` directory:

    # 1. Download 2025-2026 TLC files (14 parquets, ~6 GB total, ~10 minutes on a fast connection)
    python download_2025_2026.py

    # 2. Audit schema (confirms column consistency with 2024; should report 0 deltas)
    python audit_2025_schema.py

    # 3. Build the 2025-2026 combined panel (~5 minutes)
    python build_panel_2025_2026.py

    # 4. Enrich with fixed-counterfactual minima (~3 minutes)
    python enrich_2025_2026.py
    # If DuckDB raises an INT32 overflow on the first run, apply the patch:
    python patch_overflow.py
    python enrich_2025_2026.py

    # 5. (Optional) Diagnostic: recover contemporaneous rates from the data
    python infer_contemp_rates.py

    # 6. (Optional) Verify the August 2025 transition
    python verify_august_transition.py

    # 7. Main analysis: stack 2024 + 2025-2026 panels and produce four CSVs (~2 minutes)
    python paper2_analysis.py

    # 8. Generate Figures 1 and 2 (and an initial Fig 3 variant)
    python paper2_figures.py

    # 9. Generate the final Figure 3 (zone bar chart; replaces Fig 3 from step 8)
    python paper2_fig3_zone.py

Expected output: 4 CSVs in `output/`, 3 PNG figures in `output/figures/`.

---

## What is in `output/`

These CSVs are the pre-computed outputs used to produce the paper. Reviewers who want to check our numbers without re-running the full pipeline can work directly from these files.

| File | Contents | Used for |
|---|---|---|
| `bunching_monthly.csv` | 52 rows (26 months x 2 platforms): modal bin, bunching %, mean pay, mean ratio, trip count | Figure 1 and Table 1 |
| `ratio_dist_jul_aug.csv` | 178 rows: pay-ratio bin distribution for July and August 2025, both platforms | Figure 2 |
| `bunching_by_zone.csv` | 8 rows: July vs August modal-bin bunching, 2 platforms x 2 zones | Figure 3 |
| `summary_stats.csv` | 6 rows: period-level summary for Table 1 | Table 1 |

---

## Data source

All input data comes from the publicly available NYC Taxi and Limousine Commission High-Volume For-Hire Services trip record dataset. File URLs follow the pattern:

    https://d37ci6vzurychx.cloudfront.net/trip-data/fhvhv_tripdata_YYYY-MM.parquet

The zone lookup file used to classify Yellow Zone vs Boro Zone vs Airport is:

    https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv

The 2024 unified enriched panel (`trips_2024_welfare.parquet`) is assumed to already exist from running the paper 1 pipeline. If not, see the repository root README.

---

## Key methodological notes

**Why a fixed counterfactual?** The TLC minimum-pay formula changed four times during the analytical window (once in 2024, twice in 2025, once at the very end of the window for 2026). Any analysis that uses the contemporaneous floor as the comparison point would mechanically produce a "bunching collapse" each time the floor moves, confounding floor-schedule changes with actual changes in platform pay behaviour. The fixed-counterfactual approach uses paper 1's March-December 2024 rates as a stable yardstick throughout; any movement in the pay-ratio distribution then reflects platform behaviour. This is the central methodological choice of the paper and is documented in Section 2.

**Why August 1, 2025 rather than June 6, 2025?** The June 6 rule of promulgation is the adoption date. The effective date for the new pay rates per the rule text is August 1, 2025. The data confirms this: bunching transitions sharply at August 2025, not at June 2025.

**Why non-shared in-city trips only?** Consistent with paper 1's sample definition. Shared trips and trips that begin or end outside NYC have different pay formulas and would complicate the analysis without material gain.

---

## License

All code and CSV outputs in this directory are released under CC-BY-4.0, matching the repository root license.

---

## Contact

Lim Boon Chuan
Independent Researcher, Singapore
boonchuan@singapore.to
ORCID: 0009-0005-8477-9393
"""

target = Path("paper2") / "README.md"
target.parent.mkdir(exist_ok=True)
target.write_text(CONTENT, encoding="utf-8")
print(f"Wrote {target.resolve()} ({len(CONTENT)} bytes)")
