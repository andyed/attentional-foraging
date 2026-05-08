#!/usr/bin/env python3
"""
Generate an animated GIF of a skier jumping off the AdSERP click-by-position curve.
The curve acts as a ski jump ramp — steep at position 0, flattening toward position 9.
"""

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrow
import matplotlib.patches as mpatches
from PIL import Image
import io

# Click-by-position curve (AdSERP data) — includes the last-position spike
positions = np.array([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
p_click_raw = np.array([0.38, 0.22, 0.13, 0.08, 0.06, 0.04, 0.03, 0.02, 0.02, 0.02, 0.06])
# Scale Y for visual drama
p_click = p_click_raw * 20

# Evaluation time per position (seconds) — drops to lowest at position 10
eval_time = np.array([4.1, 3.5, 3.1, 2.8, 2.6, 2.4, 2.3, 2.2, 2.1, 2.0, 1.4])

# Smooth the curve for the ramp — the data itself has the uptick at position 10
from scipy.interpolate import CubicSpline
t_fine = np.linspace(0, 10, 250)
cs = CubicSpline(positions, p_click)
ramp_y = cs(t_fine)

# Ramp coordinates: x goes right, y goes up (click probability)
# The lip is built into the data — position 10 spikes up
full_x = t_fine
full_y = np.maximum(ramp_y, 0)  # no negative values

# Skier path: slide down ramp, then parabolic flight off the lip
n_ramp_frames = 60
n_flight_frames = 40
n_land_frames = 10
total_frames = n_ramp_frames + n_flight_frames + n_land_frames

# Ramp phase: accelerating (ease-in cubic) — slow at top, fast at bottom
t_ease = np.linspace(0, 1, n_ramp_frames)
t_accel = t_ease ** 2.2  # quadratic ease-in
ramp_indices = (t_accel * (len(full_x) - 1)).astype(int)

# Flight phase: parabolic trajectory launching from the position 10 spike
launch_x = full_x[-1]
launch_y = full_y[-1]
launch_vx = 0.18  # horizontal velocity
launch_vy = 0.8   # upward launch
gravity = 0.06

flight_t = np.arange(n_flight_frames)
flight_x = launch_x + launch_vx * flight_t
flight_y = launch_y + launch_vy * flight_t - 0.5 * gravity * flight_t ** 2

# Landing: settle at ground
land_x = np.full(n_land_frames, flight_x[-1])
land_y = np.linspace(flight_y[-1], 0, n_land_frames)


def draw_skier(ax, x, y, angle=0, size=1.0):
    """Draw a simple stick-figure skier."""
    s = 0.25 * size
    # Body (line from feet to head)
    head_dx = -s * np.sin(np.radians(angle))
    head_dy = s * np.cos(np.radians(angle))
    # Torso
    ax.plot([x, x + head_dx * 2.5], [y, y + head_dy * 2.5],
            color='#222', linewidth=2.5, solid_capstyle='round', zorder=10)
    # Head
    head = plt.Circle((x + head_dx * 3, y + head_dy * 3), s * 0.7,
                       color='#ff6633', ec='#222', linewidth=1.5, zorder=11)
    ax.add_patch(head)
    # Skis (two parallel lines below feet)
    ski_len = s * 3
    ski_dx = ski_len * np.cos(np.radians(angle))
    ski_dy = ski_len * np.sin(np.radians(angle))
    ax.plot([x - ski_dx, x + ski_dx], [y - ski_dy - s * 0.3, y + ski_dy - s * 0.3],
            color='#2266cc', linewidth=3, solid_capstyle='round', zorder=9)
    # Poles
    pole_len = s * 2
    ax.plot([x - s * 0.5, x - s * 0.5 - pole_len * 0.5],
            [y + head_dy * 1.5, y - s * 0.5],
            color='#666', linewidth=1.5, zorder=9)


def make_frame(frame_idx):
    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=100)
    fig.patch.set_facecolor('#f8f6f0')
    ax.set_facecolor('#f8f6f0')

    # Draw the full ramp + lip (filled)
    ax.fill_between(full_x, 0, full_y, color='#e8e4d8', ec='none')
    ax.plot(full_x, full_y, color='#999', linewidth=2, zorder=5)

    # Position labels along the ramp
    for i in range(10):
        ax.text(i, -0.4, str(i), ha='center', va='top',
                fontsize=8, color='#888', fontfamily='monospace')
    # Position 10: the jump lip
    ax.text(10.5, -0.4, '10', ha='center', va='top',
            fontsize=8, color='#888', fontfamily='monospace')

    # Y-axis: click probability (original scale labels)
    for y_raw in [0.1, 0.2, 0.3, 0.4]:
        y_scaled = y_raw * 20
        ax.axhline(y_scaled, color='#ddd', linewidth=0.5, zorder=1)
        ax.text(-0.7, y_scaled, f'{y_raw:.0%}', ha='right', va='center',
                fontsize=7, color='#aaa')

    # Snow particles (decorative)
    if frame_idx > n_ramp_frames:
        np.random.seed(frame_idx)
        n_snow = min(20, (frame_idx - n_ramp_frames) * 2)
        snow_x = np.random.uniform(launch_x - 1, launch_x + 2, n_snow)
        snow_y = np.random.uniform(0, launch_y + 0.05, n_snow)
        ax.scatter(snow_x, snow_y, s=np.random.uniform(2, 8, n_snow),
                   c='#ccc', alpha=0.5, zorder=2)

    # Determine skier position
    if frame_idx < n_ramp_frames:
        # On ramp
        idx = ramp_indices[frame_idx]
        sx, sy = full_x[idx], full_y[idx]
        # Angle from ramp slope
        if idx > 0:
            dx = full_x[idx] - full_x[idx - 1]
            dy = full_y[idx] - full_y[idx - 1]
            angle = np.degrees(np.arctan2(dy, dx))
        else:
            angle = -30
    elif frame_idx < n_ramp_frames + n_flight_frames:
        # In flight
        fi = frame_idx - n_ramp_frames
        sx, sy = flight_x[fi], flight_y[fi]
        # Angle from velocity vector
        if fi > 0:
            dx = flight_x[fi] - flight_x[fi - 1]
            dy = flight_y[fi] - flight_y[fi - 1]
            angle = np.degrees(np.arctan2(dy, dx))
        else:
            angle = 15
    else:
        # Landing
        li = frame_idx - n_ramp_frames - n_flight_frames
        sx, sy = land_x[min(li, len(land_x) - 1)], land_y[min(li, len(land_y) - 1)]
        angle = -80 + li * 8  # rotating to vertical landing

    draw_skier(ax, sx, sy + 0.01, angle=angle)

    # Evaluation time overlay (right y-axis) — light line
    ax2 = ax.twinx()
    ax2.plot(positions, eval_time, color='#cc4444', alpha=0.35, linewidth=1.5,
             marker='o', markersize=3, zorder=2)
    ax2.set_ylabel('Eval time (s)', fontsize=8, color='#cc4444', alpha=0.5)
    ax2.set_ylim(0, 6)
    ax2.tick_params(axis='y', colors='#cc4444', labelsize=7)
    ax2.spines['right'].set_color('#cc4444')
    ax2.spines['right'].set_alpha(0.3)
    ax2.spines['top'].set_visible(False)
    ax2.spines['left'].set_visible(False)

    # Title and annotations
    ax.set_title('SERP Click by Position (AdSERP data*)', fontsize=13,
                 fontweight='bold', color='#333', pad=8)
    ax.text(5, 9.2, 'p(click) drops off a cliff but spikes at the last position', fontsize=8,
            color='#444', ha='center')
    ax.text(5, 8.5, 'duration is lowest at position 10 (right axis)', fontsize=8,
            color='#cc4444', ha='center')

    # Link and citation — positioned below the x-axis label, clear of all chart elements
    fig.text(0.95, 0.04, 'github.com/andyed/attentional-foraging', fontsize=7,
             color='#6a9fd8', ha='right', va='bottom')
    fig.text(0.95, 0.005, '*Latifzadeh, Gwizdka & Leiva (SIGIR 2025)', fontsize=6,
             color='#999', ha='right', va='bottom')

    # Labels
    ax.set_xlabel('SERP Result Position', fontsize=9, color='#666')
    ax.set_ylabel('p(click)', fontsize=9, color='#666')

    ax.set_xlim(-1.2, 18)
    ax.set_ylim(-1, 10.5)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#ccc')
    ax.spines['bottom'].set_color('#ccc')
    ax.tick_params(colors='#ccc', labelsize=0)

    # Render to PIL image
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', pad_inches=0.2)
    plt.close(fig)
    buf.seek(0)
    return Image.open(buf).convert('RGBA')


# Generate all frames
print(f'Generating {total_frames} frames...')
frames = []
for i in range(total_frames):
    frames.append(make_frame(i))
    if (i + 1) % 20 == 0:
        print(f'  {i + 1}/{total_frames}')

# Add a few still frames at the end for the landing
for _ in range(15):
    frames.append(frames[-1])

# Save GIF
out_path = 'plots-v1/ski-jump-click-position.gif'
frames[0].save(out_path, save_all=True, append_images=frames[1:],
               duration=50, loop=0, optimize=True)

print(f'✓ {out_path} ({len(frames)} frames)')
