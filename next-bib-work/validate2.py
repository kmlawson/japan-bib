#!/usr/bin/env python3
"""Validate Borton per-page JSONL files. Usage: validate2.py [START END]; no args = overall status."""
import json, os, re, sys

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "borton")
KEYS = ["pdf_page", "entry_no", "type", "author", "title", "container", "edition", "place", "publisher",
        "year", "year_start", "extent", "section", "annotation", "note"]
FIRST, LAST, LAST_ENTRY = 1, 222, 1781
SUFFIXED = set()  # letter-suffixed entries (159a): recorded under the base number, note starts "printed as 159a"


def load(n):
    fn = os.path.join(D, f"p{n:03d}.jsonl")
    if not os.path.exists(fn):
        return None, [f"p{n:03d}: MISSING"]
    rows, errs = [], []
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
        if r.get("pdf_page") != n:
            errs.append(f"p{n:03d}:{i}: pdf_page {r.get('pdf_page')} != {n}")
        if not isinstance(r.get("entry_no"), int):
            errs.append(f"p{n:03d}:{i}: entry_no missing/not int")
            continue
        if "skipped" not in r:
            miss = [k for k in KEYS if k not in r]
            extra = [k for k in r if k not in KEYS]
            if miss or extra:
                errs.append(f"p{n:03d}:{i}: missing {miss} extra {extra}")
                continue
            if r["type"] not in ("book", "article", "chapter", "periodical"):
                errs.append(f"p{n:03d}:{i}: type {r['type']!r}")
            ys = r["year_start"]
            if ys is not None and not (isinstance(ys, int) and 1700 <= ys <= 1960):
                errs.append(f"p{n:03d}:{i}: year_start {ys!r} (year={r['year']!r})")
            if not r["title"].strip():
                errs.append(f"p{n:03d}:{i}: empty title")
        if re.match(r'printed (as|entry number is)( entry)? "?\d+a', r.get("note", "") or "", re.I):
            SUFFIXED.add((r["entry_no"], "a"))
        rows.append(r)
    return rows, errs


def ranges(nums):
    out, s = [], None
    for n in nums:
        if s is None:
            s = p = n
        elif n == p + 1:
            p = n
        else:
            out.append((s, p)); s = p = n
    if s is not None:
        out.append((s, p))
    return ", ".join(f"{a}-{b}" if a != b else str(a) for a, b in out)


if __name__ == "__main__":
    a, b = (int(sys.argv[1]), int(sys.argv[2])) if len(sys.argv) == 3 else (FIRST, LAST)
    allerrs, missing, nums, full, stubs = [], [], [], 0, 0
    for n in range(a, b + 1):
        rows, errs = load(n)
        allerrs += [e for e in errs if "MISSING" not in e]
        if rows is None:
            missing.append(n)
            continue
        prev = None
        for r in rows:
            nums.append(r["entry_no"])
            if "skipped" in r:
                stubs += 1
            else:
                full += 1
        if len(sys.argv) == 3:
            print(f"p{n:03d}: {len(rows)} entries" + (f" ({rows[0]['entry_no']}-{rows[-1]['entry_no']})" if rows else ""))
    # numbering: within the pages present, entry numbers must be strictly consecutive across adjacent pages
    for x, y in zip(nums, nums[1:]):
        if y == x and (x, "a") in SUFFIXED:
            continue
        if y != x + 1 and not missing:
            allerrs.append(f"entry numbering jumps {x} -> {y}")
    if missing:  # check consecutiveness only inside each page run
        for n in range(a, b + 1):
            rows, _ = load(n)
            if rows:
                es = [r["entry_no"] for r in rows]
                for x, y in zip(es, es[1:]):
                    if y == x and (x, "a") in SUFFIXED:
                        continue
                    if y != x + 1:
                        allerrs.append(f"p{n:03d}: entry numbering jumps {x} -> {y}")
    print(f"pages done {b - a + 1 - len(missing)}/{b - a + 1}, full records {full}, stubs {stubs}, errors {len(allerrs)}")
    for e in allerrs[:40]:
        print(e)
    print("missing pages:", ranges(missing))
    if not missing and (a, b) == (FIRST, LAST) and nums:
        print("entries", nums[0], "-", nums[-1], "(expected 1 -", LAST_ENTRY, ")")
