"""Generate the multi-scale timeline figure for the task-model paper.

Positioning claim: OSEC lives in the 1-30 second band, between fixation-level
reading research (too fine) and session-level search research (too coarse).
The figure makes this visually obvious by shading the OSEC band and showing
where every measurement in the paper sits on a log timescale.

Output: plot_timescale_map.png in the current directory. Rebuild with:
    cd ~/Documents/dev/attentional-foraging/notebooks-v2
    python make_timescale_figure.py
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# ── Measurement bands ──────────────────────────────────────────────────
# Each entry: (label, t_min_s, t_max_s, family, notebook_ref)
# Times in seconds. Use log scale.

BANDS = [
    # Perceptual / oculomotor (Rayner, Reichle territory)
    ("Saccade (motor execution)",      0.020, 0.080, "perceptual", ""),
    ("Fixation duration",               0.150, 0.400, "perceptual", "NB04, NB06"),
    ("Pupil micro-fluctuation",         0.200, 0.500, "physiological", ""),

    # Episode / reading unit (largely unnamed in prior lit)
    ("Reading episode (OSEC)",          0.400, 0.800, "task", "NB15"),

    # Phase level — OSEC contribution
    ("Orient phase",                    0.000, 0.050, "task", "NB06"),
    ("Survey phase (wide saccades)",    0.800, 1.300, "task", "NB13"),
    ("Evaluate phase (narrow saccades)",1.000, 15.000, "task", "NB13"),

    # Approach-retreat + pupillometric windows
    ("Cursor approach-retreat episode", 1.000, 5.000, "motor", "NB15, NB22"),
    ("LHIPA analysis window",           1.000, 2.000, "physiological", "NB05"),
    ("Butterworth LF/HF window",        2.000, 4.000, "physiological", "NB14"),

    # Trial level
    ("Regression loop",                 0.500, 10.000, "task", "NB07a-c"),
    ("Full trial (OSEC sequence)",      3.000, 30.000, "task", "NB01, NB21"),

    # Session / task (mostly foreclosed by AdSERP — dashed)
    ("Reformulation interval",          5.000, 120.000, "session", ""),
    ("Multi-query session",             30.000, 600.000, "session", ""),
    ("Task resolution",                 60.000, 1800.000, "session", ""),
]

# Family → color
COLORS = {
    "perceptual":    "#8b5cf6",  # violet
    "physiological": "#ef4444",  # red
    "task":          "#1f6feb",  # blue
    "motor":         "#059669",  # green
    "session":       "#6b7280",  # gray (AdSERP forecloses)
}

FAMILY_LABELS = {
    "perceptual":    "Perceptual / oculomotor",
    "physiological": "Physiological (pupil)",
    "task":          "Task (OSEC)",
    "motor":         "Motor (cursor)",
    "session":       "Session (foreclosed in AdSERP)",
}

# ── Figure ─────────────────────────────────────────────────────────────

fig, ax = plt.subplots(figsize=(13, 8))

n = len(BANDS)
y_positions = np.arange(n)[::-1]  # top-to-bottom

# Shade the OSEC band (1-30 s) behind everything
ax.axvspan(1.0, 30.0, color="#fef3c7", alpha=0.45, zorder=0,
           label="_nolegend_")
ax.text(5.4, n + 0.3, "OSEC band (1–30 s)",
        fontsize=11, color="#92400e", ha="center", weight="bold",
        style="italic")

# Vertical reference lines at canonical timescales
for t, label in [(0.1, "100 ms"), (1.0, "1 s"), (10.0, "10 s"), (60.0, "1 min"), (600.0, "10 min")]:
    ax.axvline(t, color="#cbd5e1", lw=0.8, zorder=0.5)
    ax.text(t, -1.5, label, fontsize=9, color="#64748b",
            ha="center", va="top")

# Draw each band
for i, (label, t_min, t_max, family, nb_ref) in enumerate(BANDS):
    y = y_positions[i]
    color = COLORS[family]

    # Clip to visible x range
    t_min_clip = max(t_min, 0.015)

    # Session bands dashed (foreclosed in AdSERP)
    is_foreclosed = (family == "session")

    ax.barh(y, t_max - t_min_clip, left=t_min_clip, height=0.65,
            color=color, alpha=0.85 if not is_foreclosed else 0.35,
            edgecolor=color, lw=1.5,
            linestyle="-" if not is_foreclosed else "--",
            zorder=2)

    # Label on left
    ax.text(0.013, y, label, fontsize=10.5,
            ha="right", va="center", color="#1e293b")

    # Notebook ref on right (if any)
    if nb_ref:
        ax.text(t_max * 1.12, y, nb_ref, fontsize=9,
                ha="left", va="center", color=color, style="italic")

# Axes
ax.set_xscale("log")
ax.set_xlim(0.005, 3600)
ax.set_ylim(-2.5, n + 1.2)
ax.set_yticks([])
ax.set_xlabel("Timescale (seconds, log scale)", fontsize=12)
ax.set_title("Measurement timescales in the task-model paper\n"
             "OSEC operates at the 1–30 s band, between fixation-level reading research "
             "and session-level search research",
             fontsize=13, pad=18)

# Despine
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.spines["left"].set_visible(False)
ax.tick_params(left=False)

# Family legend
handles = [mpatches.Patch(color=COLORS[f], label=FAMILY_LABELS[f])
           for f in ["perceptual", "physiological", "task", "motor", "session"]]
ax.legend(handles=handles, loc="lower right", fontsize=9.5,
          frameon=True, framealpha=0.9, ncol=2)

plt.tight_layout()
out_path = "plot_timescale_map.png"
plt.savefig(out_path, dpi=180, bbox_inches="tight", facecolor="white")
print(f"Saved: {out_path}")
