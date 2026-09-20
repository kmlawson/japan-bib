#!/usr/bin/env python3
"""Validate per-page JSONL batch files. Usage: validate.py [START END]; no args = status of all pages."""
import json, os, sys

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "batches")
KEYS = ["pdf_page", "printed_page", "col", "rare", "author", "title", "edition", "place",
        "publisher", "year", "year_start", "extent", "series", "holdings", "note"]
FIRST, LAST = 11, 553


def check(n):
    fn = os.path.join(D, f"p{n:03d}.jsonl")
    if not os.path.exists(fn):
        return None, [f"p{n:03d}: MISSING"]
    errs, recs = [], 0
    for i, line in enumerate(open(fn, encoding="utf-8"), 1):
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except Exception as e:
            errs.append(f"p{n:03d}:{i}: bad JSON ({e})")
            continue
        if r.get("empty"):
            continue
        recs += 1
        miss = [k for k in KEYS if k not in r]
        extra = [k for k in r if k not in KEYS]
        if miss or extra:
            errs.append(f"p{n:03d}:{i}: missing {miss} extra {extra}")
            continue
        if r["pdf_page"] != n:
            errs.append(f"p{n:03d}:{i}: pdf_page {r['pdf_page']} != {n}")
        if r["col"] not in ("L", "R"):
            errs.append(f"p{n:03d}:{i}: col {r['col']!r}")
        if not isinstance(r["holdings"], list):
            errs.append(f"p{n:03d}:{i}: holdings not a list")
        ys = r["year_start"]
        if ys is not None and not isinstance(ys, int):
            errs.append(f"p{n:03d}:{i}: year_start not int/null")
        elif isinstance(ys, int) and not (1700 <= ys <= 1955):
            errs.append(f"p{n:03d}:{i}: year_start {ys} outside 1850-1955 (year={r['year']!r})")
        if not r["title"].strip():
            errs.append(f"p{n:03d}:{i}: empty title")
    return recs, errs


if __name__ == "__main__":
    if len(sys.argv) == 3:
        a, b = int(sys.argv[1]), int(sys.argv[2])
        tot = 0
        for n in range(a, b + 1):
            recs, errs = check(n)
            for e in errs:
                print(e)
            if recs is not None:
                print(f"p{n:03d}: {recs} records")
                tot += recs
        print("total", tot)
    else:
        done, missing, tot, allerrs = 0, [], 0, []
        for n in range(FIRST, LAST + 1):
            recs, errs = check(n)
            if recs is None:
                missing.append(n)
            else:
                done += 1
                tot += recs
                allerrs += errs
        print(f"pages done {done}/{LAST - FIRST + 1}, records {tot}, errors {len(allerrs)}")
        for e in allerrs[:40]:
            print(e)
        # compress missing into ranges
        rng, s = [], None
        for n in missing:
            if s is None:
                s = p = n
            elif n == p + 1:
                p = n
            else:
                rng.append((s, p)); s = p = n
        if s is not None:
            rng.append((s, p))
        print("missing:", ", ".join(f"{a}-{b}" if a != b else str(a) for a, b in rng))
