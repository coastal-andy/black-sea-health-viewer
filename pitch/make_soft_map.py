"""Slide figure of the soft-edged pressure map, from the same surface the viewer draws (viewer.softzones).

Usage (repo root): PYTHONPATH=src .venv/bin/python pitch/make_soft_map.py
Writes pitch/assets/pressure_soft_map.png: a) summer, b) winter, c) summer from Constanța to Vama Veche.
Colour = number of overlapping sectors (0-5), ramp and opacities from data/zones/overlap_style.json; thin lines
where the count reaches 1, 2 and 3. No weights.
"""
from pathlib import Path

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from scipy.ndimage import gaussian_filter  # noqa: E402

from viewer import softzones as SZ  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache" / "pressure_zones"
OUT = ROOT / "pitch" / "assets" / "pressure_soft_map.png"
LAND, SEA, INK, MUTED = "#E3E3E3", "#FFFFFF", "#1F1F1F", "#595959"


def sea_polygon():
    import shapely
    from pyproj import Transformer
    from shapely.ops import transform
    geom = shapely.from_wkb((CACHE / "sea_polygon_utm35n.wkb").read_bytes())
    tr = Transformer.from_crs(32635, 4326, always_xy=True).transform
    return transform(tr, geom)


def rgba(total):
    xs, cols, alps = SZ.overlap_ramp()
    v = np.clip(total, 0, 5)
    out = np.zeros(v.shape + (4,), np.float32)
    for i in range(3):
        out[..., i] = np.interp(v, xs, cols[:, i])
    out[..., 3] = np.interp(v, xs, alps)
    out[v < 0.03, 3] = 0
    return out


def draw(ax, total, sea, extent_view, scalebar_km):
    lons, lats = SZ._grid()
    ext = [lons[0], lons[-1], lats[-1], lats[0]]
    ax.set_facecolor(LAND)
    polys = getattr(sea, "geoms", [sea])
    for p in polys:
        x, y = p.exterior.xy
        ax.fill(x, y, color=SEA, lw=0, zorder=1)
    ax.imshow(rgba(total), extent=ext, origin="upper", interpolation="bilinear", zorder=2)
    kmy, kmx = SZ._km_per_px()
    sm = gaussian_filter(total, sigma=(0.5 / kmy, 0.5 / kmx))
    lw = {0.5: 0.4, 1.5: 0.7, 2.5: 1.0}
    ax.contour(lons, lats, sm, levels=[0.5, 1.5, 2.5], colors=INK, linewidths=[lw[k] for k in lw],
               alpha=0.55, zorder=3)
    for p in polys:
        x, y = p.exterior.xy
        ax.plot(x, y, color="#9A9A9A", lw=0.5, zorder=4)
    x0, x1, y0, y1 = extent_view
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_aspect(1 / np.cos(np.radians((y0 + y1) / 2)))
    ax.tick_params(labelsize=8, colors=MUTED)
    for s in ax.spines.values():
        s.set_color("#BBBBBB")
    # scale bar, bottom right
    dlon = scalebar_km / (111.32 * np.cos(np.radians((y0 + y1) / 2)))
    bx, by = x1 - (x1 - x0) * 0.08 - dlon, y0 + (y1 - y0) * 0.06
    ax.plot([bx, bx + dlon], [by, by], color=INK, lw=2, zorder=5)
    ax.text(bx + dlon / 2, by + (y1 - y0) * 0.015, f"{scalebar_km} km", ha="center", va="bottom", fontsize=8,
            color=INK, zorder=5)


def main():
    sea = sea_polygon()
    summer = SZ.sector_surfaces("summer", ())["total"]
    winter = SZ.sector_surfaces("winter", ())["total"]
    full = (28.50, 30.59, 43.65, 45.30)
    zoom = (28.50, 28.90, 43.72, 44.28)
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 6.2), gridspec_kw={"width_ratios": [1, 1, 0.62]})
    for ax, tot, ext, km, lab in [(axes[0], summer, full, 20, "a  Summer (1 Jun - 15 Sep)"),
                                  (axes[1], winter, full, 20, "b  Winter (tourism off)"),
                                  (axes[2], summer, zoom, 5, "c  Constanța - Vama Veche")]:
        draw(ax, tot, sea, ext, km)
        ax.set_title(lab, loc="left", fontsize=11, color=INK, fontweight="bold")
    axes[0].add_patch(plt.Rectangle((zoom[0], zoom[2]), zoom[1] - zoom[0], zoom[3] - zoom[2], fill=False,
                                    ec=MUTED, lw=0.8, zorder=6))
    _, cols, alps = SZ.overlap_ramp()
    handles = [Patch(facecolor=(*cols[k], alps[k]), edgecolor="none", label=f"{k} sector{'s' if k > 1 else ''}")
               for k in range(1, 6)]
    fig.legend(handles=handles, loc="lower center", ncol=5, frameon=False, fontsize=10,
               title="Overlapping sectors (soft edges: zone limits are approximate)", title_fontsize=10)
    fig.subplots_adjust(left=0.04, right=0.99, top=0.93, bottom=0.17, wspace=0.12)
    fig.savefig(OUT, dpi=200, facecolor="white")
    print("saved", OUT)


if __name__ == "__main__":
    main()
