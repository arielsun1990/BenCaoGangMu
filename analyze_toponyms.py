#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
analyze_toponyms.py
====================
Reproduces the descriptive statistics, distributional analyses and historical
stratification analysis reported in Section 4 of the paper. Inputs the
validated toponym dataset (data/toponym_lexicon.csv) and writes the figure-
and table-supporting data files used to produce Figs 1, 2, 3, 5, 6 and
Table 3 of the manuscript.

Pareto / power-law fitting uses a maximum-likelihood estimator with bootstrap
confidence interval (Clauset, Shalizi & Newman 2009 protocol, simplified to
the continuous-MLE form for ranked occurrences).

USAGE
-----
    python analyze_toponyms.py [--lexicon ...] [--outdir ...]

OUTPUTS (written to ../data/derived/)
-------------------------------------
- top40_frequencies.csv         : Fig. 1 supporting data
- category_donut.csv            : Fig. 2(a) supporting data
- domestic_kde_input.csv        : Fig. 3 supporting data (points for KDE)
- foreign_frequencies.csv       : Fig. 5(a) supporting data
- dynasty_stratification.csv    : Fig. 6 supporting data
- power_law_fit.csv             : Pareto exponent and bootstrap CI
- yangtze_concentration.csv     : Section 4.2 spatial-share table
- top10_share.csv               : Section 4.1 top-10 share
"""

import argparse
import csv
import math
import random
from collections import Counter, defaultdict
from pathlib import Path


# ----------------------------------------------------------------------
# I/O
# ----------------------------------------------------------------------

def load_lexicon(path):
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["occurrences_validated"] = int(r["occurrences_validated"])
        try:
            r["longitude_wgs84"] = float(r["longitude_wgs84"])
            r["latitude_wgs84"] = float(r["latitude_wgs84"])
        except (ValueError, TypeError):
            r["longitude_wgs84"] = None
            r["latitude_wgs84"] = None
    return rows


def write_csv(path, rows, fields):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


# ----------------------------------------------------------------------
# Section 4.1 — Overall structure
# ----------------------------------------------------------------------

def top40_table(lex):
    """Fig 1: top 40 toponyms by frequency."""
    sorted_lex = sorted(lex, key=lambda r: -r["occurrences_validated"])[:40]
    return [
        {
            "rank": i + 1,
            "name_pinyin": r["name_pinyin"],
            "name_hanzi": r["name_hanzi"],
            "category": r["category"],
            "modern_equivalent": r["modern_equivalent"],
            "occurrences": r["occurrences_validated"],
        }
        for i, r in enumerate(sorted_lex)
    ]


def category_donut(lex):
    """Fig 2(a): proportional shares per category."""
    counts = Counter()
    distinct = Counter()
    for r in lex:
        counts[r["category"]] += r["occurrences_validated"]
        distinct[r["category"]] += 1
    total = sum(counts.values())
    rows = []
    for cat in ["region", "prefecture", "foreign", "city", "province",
                "water_body", "mountain"]:
        n = counts[cat]
        rows.append(
            {
                "category": cat,
                "occurrences": n,
                "share_percent": round(100 * n / total, 2),
                "distinct_names": distinct[cat],
            }
        )
    rows.append({"category": "TOTAL", "occurrences": total,
                 "share_percent": 100.0, "distinct_names": sum(distinct.values())})
    return rows


def top10_share(lex):
    """Section 4.1: top-10 share."""
    sorted_lex = sorted(lex, key=lambda r: -r["occurrences_validated"])
    top10 = sorted_lex[:10]
    total = sum(r["occurrences_validated"] for r in lex)
    top10_sum = sum(r["occurrences_validated"] for r in top10)
    rows = []
    for i, r in enumerate(top10):
        rows.append(
            {
                "rank": i + 1,
                "name_pinyin": r["name_pinyin"],
                "name_hanzi": r["name_hanzi"],
                "category": r["category"],
                "occurrences": r["occurrences_validated"],
                "cumulative_share_percent": round(
                    100 * sum(
                        x["occurrences_validated"] for x in sorted_lex[: i + 1]
                    ) / total, 2),
            }
        )
    rows.append(
        {
            "rank": "TOP10_TOTAL",
            "name_pinyin": "",
            "name_hanzi": "",
            "category": "",
            "occurrences": top10_sum,
            "cumulative_share_percent": round(100 * top10_sum / total, 2),
        }
    )
    return rows


# ----------------------------------------------------------------------
# Power-law / Pareto fit (Clauset-Shalizi-Newman MLE, simplified)
# ----------------------------------------------------------------------

def pareto_mle(values, x_min=None):
    """Continuous-MLE Pareto exponent.

    For a Pareto distribution with x >= x_min, alpha_hat = 1 + n / sum(ln(x_i / x_min))
    """
    xs = [v for v in values if v > 0]
    if x_min is None:
        x_min = min(xs)
    xs = [v for v in xs if v >= x_min]
    n = len(xs)
    s = sum(math.log(v / x_min) for v in xs)
    if s == 0:
        return float("nan"), n
    alpha = 1 + n / s
    return alpha, n


def bootstrap_ci(values, x_min, B=1000, alpha_level=0.05, seed=42):
    rng = random.Random(seed)
    xs = [v for v in values if v >= x_min]
    estimates = []
    for _ in range(B):
        sample = [rng.choice(xs) for _ in range(len(xs))]
        a, _ = pareto_mle(sample, x_min)
        if not math.isnan(a):
            estimates.append(a)
    estimates.sort()
    lo = estimates[int(alpha_level / 2 * len(estimates))]
    hi = estimates[int((1 - alpha_level / 2) * len(estimates))]
    return lo, hi


def power_law_table(lex):
    vals = [r["occurrences_validated"] for r in lex if r["occurrences_validated"] > 0]
    x_min = 10  # conservative tail threshold (paper uses bottom-50 cutoff at ~10)
    alpha, n = pareto_mle(vals, x_min)
    lo, hi = bootstrap_ci(vals, x_min, B=1000)
    return [
        {
            "x_min_threshold": x_min,
            "n_in_tail": n,
            "alpha_hat": round(alpha, 3),
            "ci_lo_95": round(lo, 3),
            "ci_hi_95": round(hi, 3),
            "paper_reported_alpha": 1.71,
            "paper_reported_ci": "1.54-1.89",
        }
    ]


# ----------------------------------------------------------------------
# Section 4.2 — Yangtze concentration
# ----------------------------------------------------------------------

def yangtze_concentration(lex):
    """Compute share by macro-zone (Section 4.2). Domestic only."""
    # Define macro-zone polygons by bounding box / category fields (approximate)
    zones = {
        "Sichuan Basin": [
            "Shu", "Bashu", "Ba", "Yizhou", "Chengdu_pref", "Liang",
            "Sichuan", "Emeishan", "Qingchengshan", "Heming",
        ],
        "Lower Yangtze (Jiangsu/Zhejiang)": [
            "Wu", "Yue", "Jiangnan", "Jiangdong", "Yang", "Yangzhou_pref",
            "Yangzhou_city", "Hangzhou_pref", "Hangzhou_city", "Linan_city",
            "Suzhou_pref", "Suzhou_city", "Zhejiang", "Mingzhou",
            "Mingzhou_city", "Nanjing", "Jinling", "Jiankang", "Jianye",
            "Maoshan", "Tiantai", "Yandang", "Linhai", "Taihu", "Putuo",
            "Nanzhili",
        ],
        "Middle Yangtze (Hubei/Hunan)": [
            "Chu", "Jing", "Jingzhou", "Huguang", "Hubei", "Hunan",
            "Wudangshan", "Hengshan_S", "Dongtinghu", "Yongzhou_south",
        ],
        "Northern China (>=35°N)": [
            "Hedong", "Hebei", "Zhongzhou", "Zhongyuan", "Hexi", "Huihe",
            "Tuyuhun", "Xixia", "Liao", "Liaodong", "Yan_state", "Zhao",
            "Wei", "Han_state", "Qi", "Qin", "Song_state", "Zheng", "Lu",
            "Yan_yan", "Ji", "Yu", "Pingyuan", "Guanzhong", "Sai", "Xisai",
            "Saibei", "Yanzhou", "Qingzhou", "Xuzhou", "Jizhou", "Yuzhou",
            "Liangzhou", "Bingzhou", "Youzhou", "Sizhou", "Yongzhou",
            "Hanzhong", "Shangzhou", "Shenzhou", "Bozhou", "Bianzhou",
            "Luozhou", "Pingzhou", "Changan", "Luoyang", "Hanzhongcity",
            "Kaifeng", "Ye", "Pingyang", "Taiyuan", "Xuanfu", "Datong",
            "Beijing", "Liaoyang", "Taishan", "Huashan", "Songshan",
            "Hengshan_N", "Wutai", "Lushishan", "Wangwushan", "Tiantanshan",
            "Maershan", "Taibai", "Shaanxi", "Henan", "Shandong", "Shanxi",
            "Beizhili", "Beihai",
        ],
        # Everything else (south coastal Lingnan/Fujian, SW highlands, etc.)
    }
    # Domestic = not 'foreign'
    domestic_total = sum(
        r["occurrences_validated"] for r in lex if r["category"] != "foreign"
    )
    rows = []
    zone_total = 0
    for zone, pinyin_list in zones.items():
        zone_set = set(pinyin_list)
        n = sum(
            r["occurrences_validated"]
            for r in lex
            if r["category"] != "foreign" and r["name_pinyin"] in zone_set
        )
        zone_total += n
        rows.append(
            {
                "zone": zone,
                "occurrences": n,
                "share_of_domestic_percent": round(100 * n / domestic_total, 2),
            }
        )
    other = domestic_total - zone_total
    rows.append(
        {
            "zone": "Other (Lingnan / Fujian / SW / Min / Yunnan etc.)",
            "occurrences": other,
            "share_of_domestic_percent": round(100 * other / domestic_total, 2),
        }
    )
    rows.append(
        {
            "zone": "DOMESTIC_TOTAL",
            "occurrences": domestic_total,
            "share_of_domestic_percent": 100.0,
        }
    )
    return rows


# ----------------------------------------------------------------------
# Section 4.3 — Foreign toponyms
# ----------------------------------------------------------------------

def foreign_frequencies(lex):
    foreign = sorted(
        [r for r in lex if r["category"] == "foreign"],
        key=lambda r: -r["occurrences_validated"],
    )
    rows = []
    for i, r in enumerate(foreign):
        rows.append(
            {
                "rank": i + 1,
                "name_pinyin": r["name_pinyin"],
                "name_hanzi": r["name_hanzi"],
                "modern_equivalent": r["modern_equivalent"],
                "longitude_wgs84": r["longitude_wgs84"],
                "latitude_wgs84": r["latitude_wgs84"],
                "occurrences": r["occurrences_validated"],
                "dynasty_first_attestation": r["dynasty_first_attestation"],
            }
        )
    return rows


# ----------------------------------------------------------------------
# Section 4.4 — Dynasty stratification
# ----------------------------------------------------------------------

def dynasty_stratification(lex):
    """Cross-tab of dynasty x category."""
    dynasties = ["Pre-Qin", "Han", "Tang-Song", "Ming", "General"]
    cats = ["region", "prefecture", "city", "mountain", "water_body",
            "province", "foreign"]
    grid = {d: {c: 0 for c in cats} for d in dynasties}
    for r in lex:
        d = r["dynasty_first_attestation"]
        if d not in grid:
            grid["General"][r["category"]] += r["occurrences_validated"]
        else:
            grid[d][r["category"]] += r["occurrences_validated"]
    total = sum(r["occurrences_validated"] for r in lex)
    rows = []
    for d in dynasties:
        row_total = sum(grid[d].values())
        rec = {"dynasty": d}
        for c in cats:
            rec[c] = grid[d][c]
        rec["dynasty_total"] = row_total
        rec["share_of_grand_total_percent"] = round(100 * row_total / total, 2)
        rows.append(rec)
    return rows, cats


# ----------------------------------------------------------------------
# Domestic KDE input — points × occurrences
# ----------------------------------------------------------------------

def domestic_kde_input(lex):
    return [
        {
            "name_pinyin": r["name_pinyin"],
            "name_hanzi": r["name_hanzi"],
            "category": r["category"],
            "longitude_wgs84": r["longitude_wgs84"],
            "latitude_wgs84": r["latitude_wgs84"],
            "occurrences": r["occurrences_validated"],
        }
        for r in lex
        if r["category"] != "foreign"
        and r["longitude_wgs84"] is not None
        and r["latitude_wgs84"] is not None
    ]


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--lexicon",
                        default=str(Path(__file__).parent.parent / "data" / "toponym_lexicon.csv"))
    parser.add_argument("--outdir",
                        default=str(Path(__file__).parent.parent / "data" / "derived"))
    args = parser.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    lex = load_lexicon(args.lexicon)
    print(f"Loaded {len(lex)} toponym entries from {args.lexicon}")

    rows = top40_table(lex)
    write_csv(outdir / "top40_frequencies.csv", rows,
              ["rank", "name_pinyin", "name_hanzi", "category",
               "modern_equivalent", "occurrences"])
    print(f"  Top 40: wrote {len(rows)} rows -> top40_frequencies.csv")

    rows = category_donut(lex)
    write_csv(outdir / "category_donut.csv", rows,
              ["category", "occurrences", "share_percent", "distinct_names"])
    print(f"  Category donut: wrote {len(rows)} rows -> category_donut.csv")

    rows = top10_share(lex)
    write_csv(outdir / "top10_share.csv", rows,
              ["rank", "name_pinyin", "name_hanzi", "category",
               "occurrences", "cumulative_share_percent"])
    print(f"  Top10 share: wrote {len(rows)} rows -> top10_share.csv")

    rows = power_law_table(lex)
    write_csv(outdir / "power_law_fit.csv", rows,
              ["x_min_threshold", "n_in_tail", "alpha_hat",
               "ci_lo_95", "ci_hi_95",
               "paper_reported_alpha", "paper_reported_ci"])
    print(f"  Power-law fit: alpha={rows[0]['alpha_hat']} CI=[{rows[0]['ci_lo_95']},{rows[0]['ci_hi_95']}] -> power_law_fit.csv")

    rows = yangtze_concentration(lex)
    write_csv(outdir / "yangtze_concentration.csv", rows,
              ["zone", "occurrences", "share_of_domestic_percent"])
    print(f"  Yangtze concentration: wrote {len(rows)} zones -> yangtze_concentration.csv")

    rows = foreign_frequencies(lex)
    write_csv(outdir / "foreign_frequencies.csv", rows,
              ["rank", "name_pinyin", "name_hanzi", "modern_equivalent",
               "longitude_wgs84", "latitude_wgs84", "occurrences",
               "dynasty_first_attestation"])
    print(f"  Foreign frequencies: wrote {len(rows)} rows -> foreign_frequencies.csv")

    rows = domestic_kde_input(lex)
    write_csv(outdir / "domestic_kde_input.csv", rows,
              ["name_pinyin", "name_hanzi", "category",
               "longitude_wgs84", "latitude_wgs84", "occurrences"])
    print(f"  Domestic KDE: wrote {len(rows)} georeferenced rows -> domestic_kde_input.csv")

    dyn_rows, cats = dynasty_stratification(lex)
    fields = ["dynasty"] + cats + ["dynasty_total", "share_of_grand_total_percent"]
    write_csv(outdir / "dynasty_stratification.csv", dyn_rows, fields)
    print(f"  Dynasty stratification: wrote {len(dyn_rows)} rows -> dynasty_stratification.csv")

    print("\nAll outputs written to:", outdir)


if __name__ == "__main__":
    main()
