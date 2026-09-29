"""Existing poster palette and print defaults, frozen for reproducible exports.
Visual lineage: Muriel light matplotlib style; no runtime Muriel dependency.
"""
PARAMS = {'figure.figsize': (10, 6), 'figure.dpi': 120, 'savefig.dpi': 300, 'savefig.bbox': 'tight', 'savefig.transparent': False, 'font.family': 'serif', 'font.serif': ['Georgia', 'Times New Roman', 'DejaVu Serif'], 'font.size': 14, 'axes.titlesize': 16, 'axes.labelsize': 14, 'xtick.labelsize': 12, 'ytick.labelsize': 12, 'legend.fontsize': 12, 'figure.titlesize': 18, 'font.weight': 'regular', 'figure.facecolor': '#fafaf8', 'axes.facecolor': '#fafaf8', 'savefig.facecolor': '#fafaf8', 'axes.edgecolor': '#222222', 'axes.labelcolor': '#222222', 'xtick.color': '#222222', 'ytick.color': '#222222', 'text.color': '#222222', 'grid.color': '#dddddd', 'grid.linewidth': 0.6, 'grid.alpha': 1.0, 'axes.linewidth': 1.2, 'axes.grid': True, 'axes.grid.axis': 'y', 'axes.axisbelow': True, 'axes.spines.top': False, 'axes.spines.right': False, 'xtick.direction': 'out', 'ytick.direction': 'out', 'xtick.major.size': 5, 'ytick.major.size': 5, 'xtick.major.width': 1.2, 'ytick.major.width': 1.2, 'lines.linewidth': 2.0, 'lines.markersize': 7, 'patch.linewidth': 1.0, 'legend.frameon': True, 'legend.framealpha': 0.9, 'legend.edgecolor': '#d4a574', 'legend.facecolor': '#fdf8f2'}

def contrast_ratio(a, b):
    def luminance(color):
        rgb = [int(color[i:i+2], 16) / 255 for i in (1, 3, 5)]
        linear = [c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4 for c in rgb]
        return sum(c * w for c, w in zip(linear, (.2126, .7152, .0722)))
    lo, hi = sorted((luminance(a), luminance(b)))
    return (hi + .05) / (lo + .05)
