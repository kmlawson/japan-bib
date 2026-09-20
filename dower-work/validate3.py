#!/usr/bin/env python3
"""Validate the Dower page files. Usage: validate3.py [START END]; no args = overall status."""
import json, os, sys

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pages")
KEYS = ["pdf_page", "printed_page", "entry_no", "type", "author", "title", "container", "edition",
        "publisher", "year", "year_start", "section", "annotation", "note"]
FIRST, LAST = 2, 163


def load(n):
    fn = os.path.join(D, f"p{n:03d}.jsonl")
    if not os.path.exists(fn):
        return None, None, [f"p{n:03d}: MISSING"]
    head, rows, errs = None, [], []
    for i, line in enumerate(open(fn, encoding="utf-8"), 1):
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except Exception as e:
            errs.append(f"p{n:03d}:{i}: bad JSON ({e})")
            continue
        if i == 1 and "entries_on_page" in r:
            head = r
            continue
        miss = [k for k in KEYS if k not in r]
        extra = [k for k in r if k not in KEYS]
        if miss or extra:
            errs.append(f"p{n:03d}:{i}: missing {miss} extra {extra}")
            continue
        if r["pdf_page"] != n:
            errs.append(f"p{n:03d}:{i}: pdf_page {r['pdf_page']}")
        if r["printed_page"] != n + 251:
            errs.append(f"p{n:03d}:{i}: printed_page {r['printed_page']} (expected {n + 251})")
        if r["type"] not in ("book", "article", "chapter", "periodical"):
            errs.append(f"p{n:03d}:{i}: type {r['type']!r}")
        ys = r["year_start"]
        if ys is not None and not (isinstance(ys, int) and 1850 <= ys <= 1960):
            errs.append(f"p{n:03d}:{i}: year_start {ys!r} (year={r['year']!r})")
        if not r["title"].strip():
            errs.append(f"p{n:03d}:{i}: empty title")
        rows.append(r)
    if head is None:
        errs.append(f"p{n:03d}: no summary line")
    elif head.get("in_range") != len(rows):
        errs.append(f"p{n:03d}: summary says in_range {head.get('in_range')} but {len(rows)} records")
    return head, rows, errs


if __name__ == "__main__":
    a, b = (int(sys.argv[1]), int(sys.argv[2])) if len(sys.argv) == 3 else (FIRST, LAST)
    missing, allerrs, recs, seen, sects = [], [], 0, 0, set()
    for n in range(a, b + 1):
        head, rows, errs = load(n)
        if head is None and rows is None:
            missing.append(n)
            continue
        allerrs += [e for e in errs if "MISSING" not in e]
        recs += len(rows)
        seen += (head or {}).get("entries_on_page", 0)
        sects.update(r["section"] for r in rows)
        if len(sys.argv) == 3:
            print(f"p{n:03d} (printed {n + 251}): {(head or {}).get('entries_on_page', '?')} entries, {len(rows)} in range")
    print(f"pages done {b - a + 1 - len(missing)}/{b - a + 1}, entries seen {seen}, in range {recs}, errors {len(allerrs)}")
    for e in allerrs[:40]:
        print(e)
    if missing:
        print("missing pages:", missing[:40], "..." if len(missing) > 40 else "")
