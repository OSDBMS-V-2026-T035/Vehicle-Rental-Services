import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, FancyBboxPatch

fig, ax = plt.subplots(figsize=(12, 8), dpi=180)

# Measured chassis envelope: 280 x 220 mm.
ax.add_patch(FancyBboxPatch((-140, -110), 280, 220, boxstyle='round,pad=0,rounding_size=10',
                            facecolor='#e9edf2', edgecolor='#222b35', linewidth=2))

# Two long rectangular openings.
for y in (40, -40):
    ax.add_patch(Rectangle((-60, y-6), 120, 12, facecolor='#4c78a8', alpha=.9,
                           edgecolor='#163a5f', linewidth=1.5))

# Four elongated side slots.
for x in (-118, 118):
    for y in (-35, 35):
        ax.add_patch(FancyBboxPatch((x-3.5, y-12), 7, 24,
                                    boxstyle='round,pad=0,rounding_size=3.5',
                                    facecolor='#f28e2b', edgecolor='#8a4b08', linewidth=1.3))

# Sixteen round mounting holes, measured centers.
round_holes = [
    (-125,-95), (-125,95), (125,-95), (125,95),
    (-85,-75), (-85,75), (85,-75), (85,75),
    (-45,-55), (-45,55), (45,-55), (45,55),
    (-18,-92), (-18,92), (18,-92), (18,92),
]
for x,y in round_holes:
    ax.add_patch(Circle((x,y), 2.25, facecolor='#d62728', edgecolor='#7d1111', linewidth=1.0))

# Four open edge notches (schematic measured locations; shown in green).
for x,y,w,h in [(-140,0,14,8),(126,0,14,8),(0,102,8,8),(0,-110,8,8)]:
    ax.add_patch(Rectangle((x,y-h/2), w, h, facecolor='#59a14f', edgecolor='#245b22', linewidth=1.2))

# Labels.
ax.annotate('16 × Ø4.5 mm\npayload mounting holes', xy=(-85,75), xytext=(-188,145),
            arrowprops=dict(arrowstyle='->', lw=1.5, color='#7d1111'), color='#7d1111',
            fontsize=11, ha='left', va='center', bbox=dict(fc='white', ec='#d62728', alpha=.9))
ax.annotate('4 × 7×24 mm\nadjustment slots', xy=(118,35), xytext=(150,73),
            arrowprops=dict(arrowstyle='->', lw=1.5, color='#8a4b08'), color='#8a4b08',
            fontsize=11, ha='left', va='center', bbox=dict(fc='white', ec='#f28e2b', alpha=.9))
ax.annotate('2 × 120×12 mm\naccess / relief openings', xy=(0,40), xytext=(-35,145),
            arrowprops=dict(arrowstyle='->', lw=1.5, color='#163a5f'), color='#163a5f',
            fontsize=11, ha='center', va='center', bbox=dict(fc='white', ec='#4c78a8', alpha=.9))
ax.annotate('4 edge notches\nclearance / cable / bumper', xy=(-135,0), xytext=(-205,-8),
            arrowprops=dict(arrowstyle='->', lw=1.5, color='#245b22'), color='#245b22',
            fontsize=11, ha='left', va='center', bbox=dict(fc='white', ec='#59a14f', alpha=.9))

ax.text(0, -137, 'Measured chassis footprint: 280 × 220 mm | Top-view schematic based on supplied STL',
        ha='center', va='top', fontsize=11, color='#333')
ax.set_xlim(-215, 215); ax.set_ylim(-155, 165); ax.set_aspect('equal')
ax.set_xlabel('X (mm)'); ax.set_ylabel('Y (mm)')
ax.set_title('ModuMove AMR Chassis — Hole/Opening Identification', fontsize=16, weight='bold')
ax.grid(True, alpha=.18)
fig.tight_layout()
fig.savefig('chassis_annotated.png', bbox_inches='tight')
