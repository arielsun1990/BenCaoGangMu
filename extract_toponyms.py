#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract_toponyms.py
====================
End-to-end toponym extraction pipeline for the Bencao Gangmu corpus.

Implements the three-stage protocol described in Section 3.3 of the paper:

    Stage 1: Priority-ordered longest-match regex scanning across the corpus,
             prioritising multi-character entries over single-character entries.
    Stage 2: Disambiguation filtering for single-character toponyms that
             co-occur as prefixes of drug names or personal names. A match is
             dropped when the target character is immediately followed by any
             character in the manually compiled exclusion set
             (data/disambiguation_rules.csv).
    Stage 3: Positive-context validation. Matches surviving Stage 2 must have
             at least one positive-context keyword (data/positive_context_keywords.csv)
             within a ±200-character window; matches without one are flagged
             for manual review.

INPUTS
------
- corpus path        : Path to UTF-8 plain-text file of the Bencao Gangmu
                       (default expects ../data/bencao_corpus.txt; the source
                       text is also available from ctext.org).
- lexicon            : data/toponym_lexicon.csv
- exclusion rules    : data/disambiguation_rules.csv
- positive keywords  : data/positive_context_keywords.csv

OUTPUTS (written to ../data/derived/)
-------------------------------------
- all_matches.csv         : Every match surviving Stage 1 + Stage 2, with
                            character offset, window text, and Stage-3 status
                            (validated / flagged_for_review).
- toponym_frequencies.csv : Per-toponym validated counts.
- category_summary.csv    : Per-category counts (compares against paper Table 1).
- chapter_aggregation.csv : Per-chapter occurrence counts (for Fig. 4 / Table 3).
- run_log.txt             : Log of every stage with counts at each step.

USAGE
-----
    python extract_toponyms.py \\
        --corpus path/to/bencao_clean.txt \\
        --outdir path/to/output_directory

REPLICATION
-----------
With the supplied lexicon and rules, running this script on the cleaned
Bencao Gangmu corpus reproduces the validated occurrence counts reported in
Table 1 of the paper to within rounding (small ±1-5 deviations per category
are expected because the published numbers were rounded to the nearest unit
and one round of manual disambiguation post-processing was applied; see
run_log.txt for raw vs published deltas).
"""

import argparse
import csv
import logging
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

# ----------------------------------------------------------------------
# Constants — these reproduce the parameters reported in Section 3.3.
# ----------------------------------------------------------------------

DEFAULT_WINDOW = 200          # ±200-character context window (Section 3.3)
SHORT_WINDOW = 100            # smaller window for high-locality keywords (山, 江 etc.)
REVIEW_FRACTION_EXPECTED = 0.032  # 3.2% expected manual-review rate per paper


# ----------------------------------------------------------------------
# Loaders
# ----------------------------------------------------------------------

def load_lexicon(path):
    """Load the toponym lexicon. Returns list of dicts."""
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_exclusions(path):
    """Build a mapping: hanzi_toponym -> set of following characters that
    invalidate the match.
    Returns dict like {'蜀': {'椒','漆','葵','黍','稻'}, ...}.
    """
    exclusions = defaultdict(set)
    keep_rows = []  # rows where raw_match == 0 indicate compound is itself a valid toponym, no exclusion
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["raw_match"].strip() == "1":
                exclusions[row["toponym_hanzi"]].add(row["exclusion_char_hanzi"])
            else:
                keep_rows.append(row)
    return dict(exclusions), keep_rows


def load_positive_keywords(path):
    """Load positive-context keywords. Returns list of (hanzi, window_size)."""
    out = []
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out.append((row["keyword_hanzi"], int(row["window_size"])))
    return out


def load_corpus(path):
    """Read corpus text. Strips CRLF, BOM, and surrounding whitespace.
    Returns a single string (the cleaned full corpus).
    """
    with open(path, encoding="utf-8") as f:
        text = f.read()
    text = text.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")
    return text


# ----------------------------------------------------------------------
# Stage 1 — longest-match scanning
# ----------------------------------------------------------------------

def stage1_scan(corpus, lexicon):
    """Priority-ordered longest-match scan.

    Sorts lexicon entries by descending Chinese-character length so that
    multi-character toponyms (e.g. '嶺南') are matched before any of their
    component characters are considered as single-character toponyms.

    Returns: list of dicts with keys
        toponym_id, name_hanzi, category, start, end, window_text
    """
    # Sort by length, then by toponym_id for stability
    sorted_lex = sorted(
        lexicon,
        key=lambda r: (-len(r["name_hanzi"]), r["toponym_id"]),
    )

    matches = []
    # Track character offsets already covered by a longer match
    covered = [False] * len(corpus)

    for entry in sorted_lex:
        pattern = entry["name_hanzi"]
        if not pattern:
            continue
        # Use simple substring search; we walk through manually to record offsets
        start = 0
        plen = len(pattern)
        while True:
            idx = corpus.find(pattern, start)
            if idx < 0:
                break
            # Skip if any character in this span is already covered by a
            # longer match (longest-match wins).
            if any(covered[idx + k] for k in range(plen)):
                start = idx + 1
                continue
            # Mark covered
            for k in range(plen):
                covered[idx + k] = True

            window_lo = max(0, idx - DEFAULT_WINDOW)
            window_hi = min(len(corpus), idx + plen + DEFAULT_WINDOW)
            matches.append(
                {
                    "toponym_id": entry["toponym_id"],
                    "name_hanzi": entry["name_hanzi"],
                    "name_pinyin": entry["name_pinyin"],
                    "category": entry["category"],
                    "start": idx,
                    "end": idx + plen,
                    "window_text": corpus[window_lo:window_hi],
                }
            )
            start = idx + plen
    return matches


# ----------------------------------------------------------------------
# Stage 2 — disambiguation filter
# ----------------------------------------------------------------------

def stage2_disambiguate(matches, corpus, exclusions):
    """Drop single-character matches followed by an exclusion character.

    Only single-character toponyms (len(name_hanzi) == 1) are subject to this
    filter. Multi-character toponyms pass through unchanged.

    Returns: (kept_matches, dropped_matches).
    """
    kept = []
    dropped = []
    for m in matches:
        if len(m["name_hanzi"]) > 1:
            kept.append(m)
            continue
        char = m["name_hanzi"]
        if char not in exclusions:
            kept.append(m)
            continue
        # Look at the immediately following character
        next_idx = m["end"]
        if next_idx >= len(corpus):
            kept.append(m)
            continue
        next_char = corpus[next_idx]
        if next_char in exclusions[char]:
            m["drop_reason"] = f"followed by '{next_char}' in exclusion set for {char}"
            dropped.append(m)
        else:
            kept.append(m)
    return kept, dropped


# ----------------------------------------------------------------------
# Stage 3 — positive-context validation
# ----------------------------------------------------------------------

def stage3_validate(matches, corpus, positive_keywords):
    """Verify each match has at least one positive-context keyword within
    the appropriate window. Matches without one are flagged but NOT dropped
    (per paper Section 3.3: 'flagged for manual review').

    Returns: list of matches with a new field 'context_status' in
    {'validated','flagged_for_review'}.
    """
    out = []
    for m in matches:
        status = "flagged_for_review"
        for kw_hanzi, win in positive_keywords:
            lo = max(0, m["start"] - win)
            hi = min(len(corpus), m["end"] + win)
            if kw_hanzi in corpus[lo:hi]:
                status = "validated"
                break
        m["context_status"] = status
        out.append(m)
    return out


# ----------------------------------------------------------------------
# Aggregation
# ----------------------------------------------------------------------

def per_toponym_counts(matches):
    """Group validated matches by toponym_id."""
    c = Counter()
    for m in matches:
        if m.get("context_status") == "validated":
            c[m["toponym_id"]] += 1
    return c


def per_category_counts(matches, lexicon):
    """Group validated matches by category. Compares against published Table 1."""
    cat = Counter()
    for m in matches:
        if m.get("context_status") == "validated":
            cat[m["category"]] += 1
    return cat


def detect_chapters(corpus):
    """Heuristic chapter detection.

    The Bencao Gangmu uses 卷N / 卷之N to mark juan boundaries. This function
    returns a list of (chapter_label, start_offset, end_offset).

    If no markers are found, returns one synthetic 'whole_corpus' chapter.
    """
    juan_pat = re.compile(r"卷(?:之)?[一二三四五六七八九十百零〇\d]+")
    boundaries = [(m.start(), m.group()) for m in juan_pat.finditer(corpus)]
    if not boundaries:
        return [("whole_corpus", 0, len(corpus))]
    chapters = []
    for i, (start, label) in enumerate(boundaries):
        end = boundaries[i + 1][0] if i + 1 < len(boundaries) else len(corpus)
        chapters.append((label, start, end))
    return chapters


def per_chapter_aggregation(matches, chapters):
    """Aggregate validated occurrences per chapter and compute density."""
    rows = []
    for label, lo, hi in chapters:
        char_count = hi - lo
        # Top toponyms in this chapter
        topo_counter = Counter()
        for m in matches:
            if m.get("context_status") != "validated":
                continue
            if lo <= m["start"] < hi:
                topo_counter[(m["name_hanzi"], m["name_pinyin"], m["category"])] += 1
        total = sum(topo_counter.values())
        density_per_thousand = (total / char_count) * 1000 if char_count else 0
        top3 = topo_counter.most_common(3)
        rows.append(
            {
                "chapter_label": label,
                "char_count": char_count,
                "total_validated_occ": total,
                "density_per_1000_chars": round(density_per_thousand, 3),
                "top_toponyms": "; ".join(
                    f"{hz}({tn})" for ((hz, _, _), tn) in top3
                ),
            }
        )
    return rows


# ----------------------------------------------------------------------
# Writers
# ----------------------------------------------------------------------

def write_matches(path, matches):
    fields = [
        "toponym_id", "name_hanzi", "name_pinyin", "category",
        "start", "end", "context_status", "window_text",
    ]
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for m in matches:
            # Truncate window text and replace newlines for CSV cleanliness
            wt = m["window_text"].replace("\n", " ").replace("\r", " ")
            wt = re.sub(r"\s+", " ", wt).strip()
            w.writerow(
                {
                    "toponym_id": m["toponym_id"],
                    "name_hanzi": m["name_hanzi"],
                    "name_pinyin": m["name_pinyin"],
                    "category": m["category"],
                    "start": m["start"],
                    "end": m["end"],
                    "context_status": m.get("context_status", ""),
                    "window_text": wt[:400],   # cap for size
                }
            )


def write_topo_freq(path, counts, lexicon):
    by_id = {e["toponym_id"]: e for e in lexicon}
    rows = []
    for tid, n in counts.most_common():
        e = by_id[tid]
        rows.append(
            {
                "toponym_id": tid,
                "name_hanzi": e["name_hanzi"],
                "name_pinyin": e["name_pinyin"],
                "category": e["category"],
                "modern_equivalent": e["modern_equivalent"],
                "longitude_wgs84": e["longitude_wgs84"],
                "latitude_wgs84": e["latitude_wgs84"],
                "validated_occurrences": n,
                "occurrences_in_lexicon_validated_field": e["occurrences_validated"],
            }
        )
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        w.writeheader()
        w.writerows(rows)


def write_category_summary(path, cat_counts, lexicon):
    paper_table1 = {
        "region": (55, 2187),
        "prefecture": (29, 472),
        "city": (22, 289),
        "mountain": (24, 207),
        "water_body": (6, 210),
        "province": (13, 242),
        "foreign": (19, 382),
    }
    # Count distinct names per category in lexicon
    distinct = Counter(e["category"] for e in lexicon)
    rows = []
    for cat, (paper_n, paper_occ) in paper_table1.items():
        run_occ = cat_counts.get(cat, 0)
        rows.append(
            {
                "category": cat,
                "distinct_names_in_lexicon": distinct.get(cat, 0),
                "paper_table1_distinct_names": paper_n,
                "validated_occurrences_this_run": run_occ,
                "paper_table1_occurrences": paper_occ,
                "delta_occ_vs_paper": run_occ - paper_occ,
            }
        )
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def write_chapter_agg(path, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["chapter_label", "char_count", "total_validated_occ",
                        "density_per_1000_chars", "top_toponyms"],
        )
        w.writeheader()
        w.writerows(rows)


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--corpus", required=True,
                        help="Path to cleaned Bencao Gangmu UTF-8 text file.")
    parser.add_argument("--lexicon",
                        default=str(Path(__file__).parent.parent / "data" / "toponym_lexicon.csv"),
                        help="Path to toponym lexicon CSV.")
    parser.add_argument("--rules",
                        default=str(Path(__file__).parent.parent / "data" / "disambiguation_rules.csv"),
                        help="Path to disambiguation rules CSV.")
    parser.add_argument("--keywords",
                        default=str(Path(__file__).parent.parent / "data" / "positive_context_keywords.csv"),
                        help="Path to positive-context keywords CSV.")
    parser.add_argument("--outdir",
                        default=str(Path(__file__).parent.parent / "data" / "derived"),
                        help="Directory where derived outputs will be written.")
    args = parser.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    log_path = outdir / "run_log.txt"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8", mode="w"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    log = logging.getLogger("extract")

    log.info("=" * 70)
    log.info("Bencao Gangmu toponym extraction pipeline")
    log.info("=" * 70)
    log.info("Corpus: %s", args.corpus)
    log.info("Lexicon: %s", args.lexicon)
    log.info("Rules:   %s", args.rules)
    log.info("Keywords:%s", args.keywords)
    log.info("Outdir:  %s", outdir)

    corpus = load_corpus(args.corpus)
    log.info("Loaded corpus: %d characters", len(corpus))

    lexicon = load_lexicon(args.lexicon)
    log.info("Loaded lexicon: %d entries", len(lexicon))

    exclusions, _kept = load_exclusions(args.rules)
    log.info("Loaded exclusion rules for %d single-character toponyms",
             len(exclusions))

    positive = load_positive_keywords(args.keywords)
    log.info("Loaded %d positive-context keywords", len(positive))

    # Stage 1
    log.info("--- Stage 1: longest-match scan ---")
    stage1 = stage1_scan(corpus, lexicon)
    log.info("Stage 1 matches: %d", len(stage1))

    # Stage 2
    log.info("--- Stage 2: disambiguation filter ---")
    stage2, dropped = stage2_disambiguate(stage1, corpus, exclusions)
    log.info("Stage 2 matches kept: %d (dropped %d)", len(stage2), len(dropped))

    # Stage 3
    log.info("--- Stage 3: positive-context validation ---")
    stage3 = stage3_validate(stage2, corpus, positive)
    validated = sum(1 for m in stage3 if m["context_status"] == "validated")
    flagged = sum(1 for m in stage3 if m["context_status"] == "flagged_for_review")
    log.info("Stage 3: %d validated, %d flagged for review (review rate %.1f%%)",
             validated, flagged, 100 * flagged / max(1, len(stage3)))
    log.info("(Paper reports a flag rate of ~3.2%%; deviations indicate either "
             "lexicon coverage gaps or context-keyword tuning differences.)")

    # Write outputs
    log.info("--- Writing outputs ---")
    write_matches(outdir / "all_matches.csv", stage3)
    log.info("Wrote all_matches.csv")

    topo_counts = per_toponym_counts(stage3)
    write_topo_freq(outdir / "toponym_frequencies.csv", topo_counts, lexicon)
    log.info("Wrote toponym_frequencies.csv (%d distinct toponyms with >=1 match)",
             len(topo_counts))

    cat_counts = per_category_counts(stage3, lexicon)
    write_category_summary(outdir / "category_summary.csv", cat_counts, lexicon)
    log.info("Wrote category_summary.csv")

    chapters = detect_chapters(corpus)
    log.info("Detected %d chapters using 卷N / 卷之N markers", len(chapters))
    chap_rows = per_chapter_aggregation(stage3, chapters)
    write_chapter_agg(outdir / "chapter_aggregation.csv", chap_rows)
    log.info("Wrote chapter_aggregation.csv")

    log.info("--- Per-category occurrence delta vs paper Table 1 ---")
    paper_table1_occ = {
        "region": 2187, "prefecture": 472, "city": 289,
        "mountain": 207, "water_body": 210, "province": 242, "foreign": 382,
    }
    for cat, paper_n in paper_table1_occ.items():
        run_n = cat_counts.get(cat, 0)
        log.info("  %-12s : run=%5d  paper=%5d  delta=%+5d",
                 cat, run_n, paper_n, run_n - paper_n)
    log.info("Total validated: %d  (paper total: 3989)", validated)
    log.info("DONE.")


if __name__ == "__main__":
    main()
