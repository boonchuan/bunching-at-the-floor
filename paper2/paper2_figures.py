"""
paper2_figures.py - Generate the three figures for paper 2.

Figures:
- Figure 1: Monthly bunching share, Jan 2024 - Feb 2026, with August 1 marked
- Figure 2: Pay-ratio distribution overlay, July 2025 vs August 2025
- Figure 3: Spatial sanity check (will be a sentence in the paper, but generate
            a small chart anyway in case useful)
"""
import csv
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path
from datetime import datetime

OUTDIR = Path(r"C:\research\gig\output\paper2")
FIGDIR = OUTDIR / "figures"
FIGDIR.mkdir(parents=True, exist_ok=True)

# Consistent style
plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': ['DejaVu Sans', 'Arial'],
    'font.size': 10,
    'axes.labelsize': 11,
    'axes.titlesize': 12,
    'figure.dpi': 100,
    'savefig.dpi': 200,
    'savefig.bbox': 'tight',
})

# ---- Load monthly data ----
with open(OUTDIR / "bunching_monthly.csv") as f:
    monthly = list(csv.DictReader(f))

# Convert types
for r in monthly:
    r['n_trips'] = int(r['n_trips'])
    r['mode_bin'] = float(r['mode_bin'])
    r['bunching_pct'] = float(r['bunching_pct'])
    r['mean_pay'] = float(r['mean_pay'])
    r['mean_ratio'] = float(r['mean_ratio'])
    r['date'] = datetime.strptime(r['month'] + '-15', '%Y-%m-%d')  # mid-month

# ============================================================================
# Figure 1: Monthly bunching share, Jan 2024 - Feb 2026
# ============================================================================
fig, ax = plt.subplots(figsize=(9, 5))

lyft_dates = [r['date'] for r in monthly if r['platform'] == 'Lyft']
lyft_pct = [r['bunching_pct'] for r in monthly if r['platform'] == 'Lyft']
uber_dates = [r['date'] for r in monthly if r['platform'] == 'Uber']
uber_pct = [r['bunching_pct'] for r in monthly if r['platform'] == 'Uber']

ax.plot(lyft_dates, lyft_pct, 'o-', color='#E91E63', linewidth=1.6, markersize=5,
        label='Lyft', alpha=0.9)
ax.plot(uber_dates, uber_pct, 's-', color='#000000', linewidth=1.6, markersize=5,
        label='Uber', alpha=0.85)

# Mark August 1, 2025 (rule effective date)
aug1 = datetime(2025, 8, 1)
ax.axvline(aug1, color='#888888', linestyle='--', linewidth=1.2, alpha=0.7)
ax.annotate('New rates effective\n1 August 2025',
            xy=(aug1, 78), xytext=(aug1, 82),
            ha='center', fontsize=9, color='#444444',
            arrowprops=dict(arrowstyle='->', color='#888888', lw=0.8))

# Mark the March 2025 CPI-W bump
mar1 = datetime(2025, 3, 1)
ax.axvline(mar1, color='#cccccc', linestyle=':', linewidth=1, alpha=0.6)
ax.text(mar1, 25, 'Mar 2025\nCPI-W', ha='center', fontsize=8,
        color='#888888', style='italic')

ax.set_xlabel('Month')
ax.set_ylabel('Bunching share at modal bin ±2% (%)')
ax.set_title('Bunching at the regulatory floor by month, January 2024 – February 2026\nNon-shared in-city trips, fixed 2024-rate counterfactual')
ax.set_ylim(20, 90)
ax.legend(loc='lower left', frameon=False)
ax.grid(True, alpha=0.3, linewidth=0.5)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)

# Format x-axis
import matplotlib.dates as mdates
ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
ax.xaxis.set_major_formatter(mdates.DateFormatter('%b\n%Y'))

plt.tight_layout()
plt.savefig(FIGDIR / "fig1_bunching_monthly.png", dpi=200)
plt.close()
print(f"Saved {FIGDIR / 'fig1_bunching_monthly.png'}")

# ============================================================================
# Figure 2: Pay-ratio distribution overlay, July 2025 vs August 2025
# ============================================================================
with open(OUTDIR / "ratio_dist_jul_aug.csv") as f:
    dist = list(csv.DictReader(f))
for r in dist:
    r['bin'] = float(r['bin'])
    r['pct'] = float(r['pct'])

fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), sharey=True)

for ax, plat, color in zip(axes, ['Lyft', 'Uber'], ['#E91E63', '#000000']):
    jul = [(r['bin'], r['pct']) for r in dist
           if r['month'] == '2025-07' and r['platform'] == plat]
    aug = [(r['bin'], r['pct']) for r in dist
           if r['month'] == '2025-08' and r['platform'] == plat]
    jul.sort(); aug.sort()

    j_bins, j_pcts = zip(*jul) if jul else ([], [])
    a_bins, a_pcts = zip(*aug) if aug else ([], [])

    width = 0.005
    ax.bar([b - width/2 for b in j_bins], j_pcts, width=width,
           color=color, alpha=0.4, label='July 2025 (pre-rule)', edgecolor='none')
    ax.bar([b + width/2 for b in a_bins], a_pcts, width=width,
           color=color, alpha=0.95, label='August 2025 (post-rule)', edgecolor='none')

    ax.set_xlim(0.92, 1.22)
    ax.set_xlabel('Pay ratio (driver pay ÷ fixed 2024-rate counterfactual)')
    if ax == axes[0]:
        ax.set_ylabel('Share of trips (%)')
    ax.set_title(plat)
    ax.legend(frameon=False, fontsize=9)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(True, alpha=0.3, axis='y', linewidth=0.5)

fig.suptitle('Pay-ratio distribution: July 2025 (pre-rule) vs August 2025 (post-rule)',
             y=1.00, fontsize=12)
plt.tight_layout()
plt.savefig(FIGDIR / "fig2_dist_jul_aug.png", dpi=200)
plt.close()
print(f"Saved {FIGDIR / 'fig2_dist_jul_aug.png'}")

# ============================================================================
# Figure 3: Mean driver pay over time (NEW - actually more compelling than zone chart)
# Shows that pay rose post-rule
# ============================================================================
fig, ax = plt.subplots(figsize=(9, 4.5))

lyft_pay = [r['mean_pay'] for r in monthly if r['platform'] == 'Lyft']
uber_pay = [r['mean_pay'] for r in monthly if r['platform'] == 'Uber']

ax.plot(lyft_dates, lyft_pay, 'o-', color='#E91E63', linewidth=1.6, markersize=5,
        label='Lyft', alpha=0.9)
ax.plot(uber_dates, uber_pay, 's-', color='#000000', linewidth=1.6, markersize=5,
        label='Uber', alpha=0.85)

ax.axvline(aug1, color='#888888', linestyle='--', linewidth=1.2, alpha=0.7)
ax.annotate('New rates effective\n1 August 2025',
            xy=(aug1, 21.0), xytext=(aug1, 21.5),
            ha='center', fontsize=9, color='#444444',
            arrowprops=dict(arrowstyle='->', color='#888888', lw=0.8))

ax.set_xlabel('Month')
ax.set_ylabel('Mean driver pay per trip (USD)')
ax.set_title('Mean realised driver pay by month, January 2024 – February 2026\nNon-shared in-city trips')
ax.set_ylim(15, 22)
ax.legend(loc='lower left', frameon=False)
ax.grid(True, alpha=0.3, linewidth=0.5)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
ax.xaxis.set_major_formatter(mdates.DateFormatter('%b\n%Y'))

plt.tight_layout()
plt.savefig(FIGDIR / "fig3_mean_pay_monthly.png", dpi=200)
plt.close()
print(f"Saved {FIGDIR / 'fig3_mean_pay_monthly.png'}")

print("\nAll figures generated.")
