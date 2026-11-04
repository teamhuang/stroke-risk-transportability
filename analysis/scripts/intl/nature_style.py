# -*- coding: utf-8 -*-
"""Nature / npj Digital Medicine house style for all manuscript figures.

Conventions (locked here so every panel is consistent):
  * height is ALWAYS 5.0 cm; width is 5.0 cm for a single-panel figure and 6.5 cm for a multi-panel figure;
  * Arial throughout (falls back to Helvetica/DejaVu only if Arial is missing), axes/tick text 8 pt,
    panel letters 9 pt bold;
  * colour-blind-safe Okabe-Ito palette; thin (0.8 pt) spines, top+right spines removed, ticks inward;
  * NO explanatory note text is drawn on the canvas - legends may name a series, but conclusions live in the
    manuscript caption, not the image;
  * PNG at 300 dpi and a vector PDF with embedded (editable) TrueType text are written together.

Import at the top of a figure script (before creating any Figure):

    import sys; sys.path.insert(0, r"...intl")
    import nature_style as NS
    NS.configure()
    fig, axes = NS.grid(2, 2)              # 6.5 x 5.0 cm multi-panel
    ...                                     # draw, set titles to the bare facet name only
    NS.letters(fig, axes)                  # bold a b c d at each facet's top-left
    NS.finalise(fig, "incident_joint_fig1_calibration", outdir)

A single-panel figure uses `fig, ax = NS.panel()` -> 5.0 x 5.0 cm, no letters.
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

CM = 1.0 / 2.54            # one centimetre, in inches
H_CM = 5.0                 # every figure is exactly 5 cm tall
W_SIMPLE_CM = 5.0          # single-panel width
W_PANEL_CM = 6.5           # multi-panel width

# Okabe-Ito colour-blind-safe palette (restrained, journal-safe)
OKABE = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9", "#000000"]
BLUE, VERM, GRN, PUP, AMB, SKY = OKABE[:6]
GREY, BLACK = "#555555", "#000000"

_PANEL_FONT = "Arial"


def _resolve_font():
    names = {f.name for f in font_manager.fontManager.ttflist}
    for cand in ("Arial", "Helvetica", "Liberation Sans", "DejaVu Sans"):
        if cand in names:
            return cand
    return "DejaVu Sans"


def configure():
    """Set the global rcParams once, before any Figure is created."""
    global _PANEL_FONT
    _PANEL_FONT = _resolve_font()
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": [_PANEL_FONT, "DejaVu Sans"],
        "font.size": 8,
        "axes.titlesize": 8,
        "axes.labelsize": 8,
        "xtick.labelsize": 7.5,
        "ytick.labelsize": 7.5,
        "legend.fontsize": 6.5,
        "legend.frameon": False,
        "axes.linewidth": 0.8,
        "axes.edgecolor": "#222222",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "xtick.direction": "in",
        "ytick.direction": "in",
        "xtick.major.width": 0.7,
        "ytick.major.width": 0.7,
        "xtick.major.size": 2.5,
        "ytick.major.size": 2.5,
        "lines.linewidth": 1.1,
        "lines.markersize": 3.2,
        "patch.linewidth": 0.5,
        "figure.dpi": 120,
        "savefig.dpi": 300,
        "savefig.bbox": None,       # save the exact canvas so the physical size equals figsize (5 cm tall)
        "pdf.fonttype": 42,       # editable TrueType text in the vector PDF
        "ps.fonttype": 42,
        "axes.prop_cycle": plt.cycler(color=OKABE),
    })


def _size(npanel):
    w = W_SIMPLE_CM if npanel <= 1 else W_PANEL_CM
    return (w * CM, H_CM * CM)


def panel():
    """A single-panel figure: 5.0 x 5.0 cm."""
    fig, ax = plt.subplots(1, 1, figsize=_size(1))
    return fig, ax


def grid(nrows, ncols):
    """A multi-panel figure: 6.5 x 5.0 cm, panels laid out nrows x ncols."""
    fig, axes = plt.subplots(nrows, ncols, figsize=_size(nrows * ncols))
    return fig, axes


def figure(**kw):
    """Explicit single-figure creation; forces 5 cm height and snaps width to 5.0 / 6.5 cm."""
    n = kw.pop("npanel", 1)
    fig = plt.figure(figsize=_size(n))
    return fig


def letters(fig, axes, start="a", pad=(0.018, 0.012)):
    """Bold Arial panel letters just OUTSIDE each facet's top-left corner (clear of tick labels and titles)."""
    if axes is None:
        return
    try:
        flat = list(axes.flatten())
    except AttributeError:
        flat = [axes]
    import string
    for i, ax in enumerate([a for a in flat if a is not None]):
        lab = start[i] if isinstance(start, str) and len(start) > i else string.ascii_lowercase[i]
        bb = ax.get_position()
        fig.text(bb.x0 - pad[0], bb.y1 + pad[1], lab, transform=fig.transFigure,
                 ha="right", va="bottom",
                 fontsize=9, fontweight="bold", family=_PANEL_FONT, color="#000000")


def finalise(fig, base, outdir, close=True, multi=None):
    """Write <base>.png (300 dpi) and <base>.pdf at EXACTLY the target physical size.

    The canvas is snapped to 5.0 cm tall and 5.0 / 6.5 cm wide (auto-detected from the panel count unless
    `multi` is given), then saved WITHOUT a tight bounding box so the raster/vector dimensions equal the
    figure size rather than the cropped content. Content is fitted inside the canvas by the caller's
    tight_layout(rect=...)."""
    if multi is None:
        n = sum(1 for a in fig.axes if a.get_title() or a.get_xlabel() or a.get_ylabel())
        multi = n > 1
    w_cm = W_PANEL_CM if multi else W_SIMPLE_CM
    fig.set_size_inches(w_cm * CM, H_CM * CM, forward=True)
    os.makedirs(outdir, exist_ok=True)
    png = os.path.join(outdir, base + ".png")
    pdf = os.path.join(outdir, base + ".pdf")
    fig.savefig(png, dpi=300, bbox_inches=None)
    fig.savefig(pdf, bbox_inches=None)
    if close:
        plt.close(fig)
    return png, pdf
