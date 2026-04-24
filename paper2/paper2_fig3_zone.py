"""
Replace Figure 3 with the spatial sanity chart.
Shows July vs August 2025 modal-bin bunching by zone, both platforms.
"""
import csv
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

OUTDIR = Path(r"C:\research\gig\output\paper2")
FIGDIR = OUTDIR / "figures"

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

with open(OUTDIR / "bunching_by_zone.csv") as f:
    zone = list(csv.DictReader(f))
for r in zone:
    r['bunching_pct'] = float(r['bunching_pct'])

# Build matrix: rows = (platform, zone), cols = (Jul, Aug)
data = {}
for r in zone:
    data[(r['platform'], r['zone'])] = data.get((r['platform'], r['zone']), {})
    data[(r['platform'], r['zone'])][r['month']] = r['bunching_pct']

categories = [
    ('Lyft', 'Yellow Zone'),
    ('Lyft', 'Boro Zone'),
    ('Uber', 'Yellow Zone'),
    ('Uber', 'Boro Zone'),
]

fig, ax = plt.subplots(figsize=(9, 5))

x = np.arange(len(categories))
width = 0.36

jul_vals = [data[(p, z)]['2025-07'] for p, z in categories]
aug_vals = [data[(p, z)]['2025-08'] for p, z in categories]

# Use platform-coloured pairs
colors_jul = ['#F8BBD0', '#F8BBD0', '#CCCCCC', '#CCCCCC']
colors_aug = ['#E91E63', '#E91E63', '#000000', '#000000']

bars1 = ax.bar(x - width/2, jul_vals, width, color=colors_jul,
               edgecolor='none', label='July 2025 (pre-rule)')
bars2 = ax.bar(x + width/2, aug_vals, width, color=colors_aug,
               edgecolor='none', label='August 2025 (post-rule)')

# Add value labels on top of bars
for bars in [bars1, bars2]:
    for bar in bars:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, h + 1, f'{h:.1f}',
                ha='center', va='bottom', fontsize=9, color='#333333')

# Add drop arrows between Jul and Aug
for i, (jv, av) in enumerate(zip(jul_vals, aug_vals)):
    drop = jv - av
    ax.annotate(f'−{drop:.1f}pp',
                xy=(i, (jv + av) / 2),
                ha='center', fontsize=8.5, color='#666666',
                style='italic')

ax.set_xticks(x)
ax.set_xticklabels([f'{p}\n{z}' for p, z in categories], fontsize=10)
ax.set_ylabel('Bunching share at modal bin ±2% (%)')
ax.set_title('Bunching transition by service zone, July 2025 vs August 2025\nNon-shared in-city trips')
ax.set_ylim(0, 90)
ax.legend(frameon=False, loc='upper right', fontsize=9.5)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.grid(True, alpha=0.3, axis='y', linewidth=0.5)

plt.tight_layout()
plt.savefig(FIGDIR / "fig3_bunching_by_zone.png", dpi=200)
plt.close()
print(f"Saved {FIGDIR / 'fig3_bunching_by_zone.png'}")
print("(Old fig3_mean_pay_monthly.png kept on disk; ignore.)")
