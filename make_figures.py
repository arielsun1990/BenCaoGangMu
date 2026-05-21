#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_figures.py
================
Reproduces Figures 1–6 of the paper using matplotlib. All figures save as
both PNG (300 dpi) and SVG to ../data/derived/figures/.

Inputs: the derived CSVs produced by analyze_toponyms.py.

The figures use a colour-blind-safe palette (Wong 2011). Chinese characters
are rendered through any CJK font installed on the system; if none is found,
the script falls back to Pinyin labels with a warning.

USAGE
-----
    python make_figures.py [--indir ...] [--outdir ...]
"""

import argparse
import csv
import os
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm


# ----------------------------------------------------------------------
# Palette (Wong 2011, colour-blind safe)
# ----------------------------------------------------------------------
PALETTE = {
    "region":     "#0072B2",  # blue
    "prefecture": "#E69F00",  # orange
    "city":       "#009E73",  # bluish green
    "mountain":   "#56B4E9",  # sky blue
    "water_body": "#F0E442",  # yellow
    "province":   "#D55E00",  # vermillion
    "foreign":    "#CC79A7",  # reddish purple
}

DYNASTY_COLOURS = {
    "Pre-Qin":   "#0072B2",
    "Han":       "#E69F00",
    "Tang-Song": "#009E73",
    "Ming":      "#D55E00",
    "General":   "#999999",
}


# ----------------------------------------------------------------------
# Font configuration
# ----------------------------------------------------------------------

def configure_cjk_font():
    """Try to locate a CJK font on the system. Returns the font name or None."""
    candidates = [
        "Noto Sans CJK SC", "Noto Sans CJK TC", "Noto Sans CJK",
        "Source Han Sans CN", "Source Han Sans TC",
        "WenQuanYi Zen Hei", "PingFang SC", "Heiti SC",
        "Microsoft YaHei", "SimHei", "Arial Unicode MS",
    ]
    available = {f.name for f in fm.fontManager.ttflist}
    for c in candidates:
        if c in available:
            plt.rcParams["font.sans-serif"] = [c, "DejaVu Sans"]
            plt.rcParams["axes.unicode_minus"] = False
            return c
    warnings.warn("No CJK font found; figures will render Chinese as squares. "
                  "Install e.g. fonts-noto-cjk to fix.")
    return None


# ----------------------------------------------------------------------
# Loaders
# ----------------------------------------------------------------------

def load_csv(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ----------------------------------------------------------------------
# Figures
# ----------------------------------------------------------------------

def fig1_top40(indir, outdir, cjk):
    rows = load_csv(indir / "top40_frequencies.csv")
    rows = list(reversed(rows))  # plot from bottom up so #1 is at top
    names = [
        f"{r['name_hanzi']} ({r['modern_equivalent']})" if cjk
        else f"{r['name_pinyin']} ({r['modern_equivalent']})"
        for r in rows
    ]
    occ = [int(r["occurrences"]) for r in rows]
    cats = [r["category"] for r in rows]
    colors = [PALETTE.get(c, "#999999") for c in cats]

    fig, ax = plt.subplots(figsize=(8, 12))
    ax.barh(range(len(rows)), occ, color=colors, edgecolor="white", linewidth=0.5)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels(names, fontsize=8)
    ax.set_xlabel("Validated occurrences", fontsize=10)
    ax.set_title("Top 40 toponyms in the Bencao Gangmu", fontsize=12)
    # Add count labels to right of bars
    for i, n in enumerate(occ):
        ax.text(n + 5, i, str(n), va="center", fontsize=7)
    # Legend
    handles = [plt.Rectangle((0, 0), 1, 1, color=PALETTE[c]) for c in PALETTE]
    ax.legend(handles, list(PALETTE.keys()), loc="lower right", fontsize=8,
              title="Category")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    plt.tight_layout()
    plt.savefig(outdir / "fig1_top40.png", dpi=300)
    plt.savefig(outdir / "fig1_top40.svg")
    plt.close()


def fig2_category(indir, outdir, cjk):
    rows = [r for r in load_csv(indir / "category_donut.csv")
            if r["category"] != "TOTAL"]
    cats = [r["category"] for r in rows]
    occ = [int(r["occurrences"]) for r in rows]
    colors = [PALETTE[c] for c in cats]

    fig, ax = plt.subplots(figsize=(8, 8))
    wedges, _texts, autotexts = ax.pie(
        occ, labels=cats, colors=colors, autopct="%1.1f%%",
        pctdistance=0.78, labeldistance=1.08, wedgeprops=dict(width=0.4, edgecolor="white"),
        textprops={"fontsize": 10},
    )
    for at in autotexts:
        at.set_fontsize(9)
        at.set_color("white")
        at.set_weight("bold")
    ax.set_title(f"Category-level distribution of toponym occurrences\n(n = {sum(occ)})",
                 fontsize=12)
    plt.tight_layout()
    plt.savefig(outdir / "fig2_category_donut.png", dpi=300)
    plt.savefig(outdir / "fig2_category_donut.svg")
    plt.close()


def fig3_map(indir, outdir, cjk):
    rows = load_csv(indir / "domestic_kde_input.csv")
    foreign = load_csv(indir / "foreign_frequencies.csv")

    fig, ax = plt.subplots(figsize=(12, 8))

    # Approximate China bounding box
    ax.set_xlim(70, 145)
    ax.set_ylim(15, 55)

    # Plot domestic
    for r in rows:
        try:
            x = float(r["longitude_wgs84"])
            y = float(r["latitude_wgs84"])
            n = int(r["occurrences"])
        except (ValueError, TypeError):
            continue
        cat = r["category"]
        ax.scatter(x, y, s=max(20, n * 1.5), color=PALETTE.get(cat, "#999"),
                   alpha=0.5, edgecolor="black", linewidth=0.3)

    # Plot foreign (those falling in extended Asia bounding box)
    for r in foreign:
        try:
            x = float(r["longitude_wgs84"])
            y = float(r["latitude_wgs84"])
            n = int(r["occurrences"])
        except (ValueError, TypeError):
            continue
        if 70 <= x <= 145 and 15 <= y <= 55:
            ax.scatter(x, y, s=max(20, n * 1.5), color=PALETTE["foreign"],
                       alpha=0.6, edgecolor="black", linewidth=0.3)

    ax.set_xlabel("Longitude (°E)")
    ax.set_ylabel("Latitude (°N)")
    ax.set_title("Spatial distribution of Bencao Gangmu toponyms\n"
                 "(bubble area proportional to occurrence frequency)",
                 fontsize=12)
    ax.grid(alpha=0.3)

    # Legend
    handles = [plt.Line2D([0], [0], marker="o", color="w",
                           markerfacecolor=PALETTE[c], markersize=10,
                           label=c) for c in PALETTE]
    ax.legend(handles=handles, loc="upper right", fontsize=8, title="Category")
    plt.tight_layout()
    plt.savefig(outdir / "fig3_map.png", dpi=300)
    plt.savefig(outdir / "fig3_map.svg")
    plt.close()


def fig5_foreign(indir, outdir, cjk):
    rows = load_csv(indir / "foreign_frequencies.csv")
    rows = list(reversed(rows))  # plot smallest at bottom, largest at top
    labels = [
        f"{r['name_hanzi']} ({r['modern_equivalent']})" if cjk
        else f"{r['name_pinyin']} ({r['modern_equivalent']})"
        for r in rows
    ]
    occ = [int(r["occurrences"]) for r in rows]

    fig, ax = plt.subplots(figsize=(8, 8))
    ax.barh(range(len(rows)), occ, color=PALETTE["foreign"],
            edgecolor="white", linewidth=0.5)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_xlabel("Validated occurrences", fontsize=10)
    ax.set_title("Foreign toponyms in the Bencao Gangmu", fontsize=12)
    for i, n in enumerate(occ):
        ax.text(n + 0.5, i, str(n), va="center", fontsize=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    plt.tight_layout()
    plt.savefig(outdir / "fig5_foreign.png", dpi=300)
    plt.savefig(outdir / "fig5_foreign.svg")
    plt.close()


def fig6_dynasty(indir, outdir, cjk):
    rows = load_csv(indir / "dynasty_stratification.csv")
    dynasties = [r["dynasty"] for r in rows]
    cats = ["region", "prefecture", "city", "mountain",
            "water_body", "province", "foreign"]

    fig, ax = plt.subplots(figsize=(10, 6))
    bottoms = [0] * len(dynasties)
    for c in cats:
        vals = [int(r[c]) for r in rows]
        ax.bar(dynasties, vals, bottom=bottoms,
               color=PALETTE[c], edgecolor="white", label=c, linewidth=0.5)
        bottoms = [b + v for b, v in zip(bottoms, vals)]

    ax.set_ylabel("Validated occurrences", fontsize=10)
    ax.set_xlabel("Dynasty of first attestation", fontsize=10)
    ax.set_title("Historical stratification of toponyms in the Bencao Gangmu",
                 fontsize=12)
    ax.legend(loc="upper right", fontsize=9)
    # Total labels on top
    for x, total in zip(dynasties, bottoms):
        ax.text(x, total + 30, str(int(total)), ha="center", fontsize=9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    plt.tight_layout()
    plt.savefig(outdir / "fig6_dynasty.png", dpi=300)
    plt.savefig(outdir / "fig6_dynasty.svg")
    plt.close()


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--indir",
                        default=str(Path(__file__).parent.parent / "data" / "derived"))
    parser.add_argument("--outdir",
                        default=str(Path(__file__).parent.parent / "data" / "derived" / "figures"))
    args = parser.parse_args()

    indir = Path(args.indir)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    cjk = configure_cjk_font()
    print(f"CJK font: {cjk!r}")

    fig1_top40(indir, outdir, cjk)
    print("Wrote fig1_top40.{png,svg}")
    fig2_category(indir, outdir, cjk)
    print("Wrote fig2_category_donut.{png,svg}")
    fig3_map(indir, outdir, cjk)
    print("Wrote fig3_map.{png,svg}")
    fig5_foreign(indir, outdir, cjk)
    print("Wrote fig5_foreign.{png,svg}")
    fig6_dynasty(indir, outdir, cjk)
    print("Wrote fig6_dynasty.{png,svg}")
    print(f"\nAll figures saved to: {outdir}")


if __name__ == "__main__":
    main()
