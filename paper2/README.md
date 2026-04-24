# Paper 2 replication: After the Floor Moved

This subdirectory contains the analysis scripts, CSV outputs, and reproduction instructions for:

Lim, B. C. (2026). After the Floor Moved: NYC Ride-Hail Driver Pay Behaviour Following the Minimum Pay Rule Change of August 2025.

This is the second paper in a two-paper series. The pre-rule baseline (2024 data, single regulatory regime) is the subject of the companion paper in the repository root; paper 2 extends the analysis to the post-rule period (January 2024 through February 2026).

## What this code does

1. Downloads 14 months of TLC HVFHS parquet files (Jan 2025 through Feb 2026).
2. Audits schema consistency with 2024 panel.
3. Builds a 284-million-trip combined 2025-2026 panel.
4. Enriches with a fixed-counterfactual minimum using paper 1 March-December 2024 rates (0.789/mile, 0.338/min, utilisation 0.58). Fixed yardstick isolates platform pay behaviour from moving regulatory floor.
5. Stacks 2024 + 2025-2026 into a unified 482M-trip, 26-month panel.
6. Produces monthly bunching series, July-vs-August distribution comparison, spatial sanity check, and summary statistics.
7. Generates Figures 1, 2, 3 and Table 1.

## Requirements

Python 3.10+. DuckDB 0.10+. Polars. Matplotlib. Requests. PyArrow.

Disk: approximately 45 GB free. RAM: 32 GB recommended. Full pipeline runs in ~25 minutes on consumer hardware.

Install: pip install duckdb polars matplotlib requests pyarrow

## End-to-end reproduction

From the paper2/ directory, run in order:

    python download_2025_2026.py
    python audit_2025_schema.py
    python build_panel_2025_2026.py
    python enrich_2025_2026.py
    python paper2_analysis.py
    python paper2_figures.py
    python paper2_fig3_zone.py

Optional diagnostics (used during development):

    python infer_contemp_rates.py
    python verify_august_transition.py

If enrich_2025_2026.py fails with a DuckDB INT32 overflow on first run, apply the patch and rerun:

    python patch_overflow.py
    python enrich_2025_2026.py

## Output files

- output/bunching_monthly.csv: 52 rows for Figure 1 and Table 1
- output/ratio_dist_jul_aug.csv: 178 rows for Figure 2
- output/bunching_by_zone.csv: 8 rows for Figure 3
- output/summary_stats.csv: 6 rows for Table 1

## Data source

NYC TLC HVFHS trip records, distributed monthly from AWS:
https://d37ci6vzurychx.cloudfront.net/trip-data/fhvhv_tripdata_YYYY-MM.parquet

Zone lookup:
https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv

The 2024 enriched panel (trips_2024_welfare.parquet) is assumed to exist from running the paper 1 pipeline (see repository root README).

## Methodological notes

Why a fixed counterfactual? The TLC minimum-pay formula changed four times during the analytical window. Using contemporaneous floors would mechanically produce a bunching collapse each time the floor moves, confounding floor changes with platform behaviour changes. The fixed-counterfactual approach uses paper 1 rates as a stable yardstick throughout.

Why August 1, 2025? The June 6, 2025 promulgation is the adoption date. The effective date for new pay rates per the rule text is August 1, 2025. The data confirms this: bunching transitions sharply at August 2025, not at June 2025.

Why non-shared in-city trips only? Consistent with paper 1 sample definition.

## License

CC-BY-4.0, matching the repository root.

## Contact

Lim Boon Chuan
Independent Researcher, Singapore
boonchuan@singapore.to
ORCID: 0009-0005-8477-9393
