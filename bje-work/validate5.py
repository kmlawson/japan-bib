#!/usr/bin/env python3
"""Check the page files transcribed from Wenckstern/Nachod, Bibliography of the Japanese Empire 1906-1926.

    validate5.py [START END]      (PDF page numbers; the scan runs 1-243, printed page = PDF + 149)
"""
import glob, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PAGES = os.path.join(HERE, "pages")
BOOK_KEYS = {"pdf_page", "entry_no", "author", "title", "place", "publisher", "year", "year_num",
             "extent", "edition", "series", "language", "section", "note"}
SKIPS = {"article", "russian", "out of range"}


def check(a=1, b=243):
    errs, seen, books, skipped, entries = [], {}, 0, 0, 0
    lettered_nos = {}          # entry numbers printed with a letter ("3606a", "1583bis"), kept as strings
    for fn in sorted(glob.glob(os.path.join(PAGES, "p*.jsonl"))):
        page = int(os.path.basename(fn)[1:-6])
        if not (a <= page <= b):
            continue
        lines = [l for l in open(fn, encoding="utf-8") if l.strip()]
        if not lines:
            errs.append(f"{fn}: empty")
            continue
        head = json.loads(lines[0])
        if "entries_on_page" not in head:
            errs.append(f"{fn}: first line is not a page summary")
            continue
        nos, n_book, n_skip = [], 0, 0
        for i, line in enumerate(lines[1:], 1):
            try:
                r = json.loads(line)
            except Exception as e:
                errs.append(f"{fn} line {i + 1}: bad JSON ({e})")
                continue
            entries += 1
            if r.get("pdf_page") != page:
                errs.append(f"{fn} entry {r.get('entry_no')}: pdf_page {r.get('pdf_page')} != {page}")
            nos.append(r.get("entry_no"))
            if "skip" in r:
                n_skip += 1
                if r["skip"] not in SKIPS:
                    errs.append(f"{fn} entry {r.get('entry_no')}: skip {r['skip']!r}")
                if set(r) - {"pdf_page", "entry_no", "skip", "note"}:
                    errs.append(f"{fn} entry {r.get('entry_no')}: a skipped entry carries "
                                f"{sorted(set(r) - {'pdf_page', 'entry_no', 'skip', 'note'})}")
                continue
            n_book += 1
            missing = BOOK_KEYS - set(r)
            if missing:
                errs.append(f"{fn} entry {r.get('entry_no')}: missing {sorted(missing)}")
            if set(r) - BOOK_KEYS:
                errs.append(f"{fn} entry {r.get('entry_no')}: unexpected {sorted(set(r) - BOOK_KEYS)}")
            if not (r.get("title") or "").strip():
                errs.append(f"{fn} entry {r.get('entry_no')}: no title")
            y = r.get("year_num")
            if y is not None and (not isinstance(y, int) or not (1850 <= y <= 1930)):
                errs.append(f"{fn} entry {r.get('entry_no')}: year_num {y!r}")
            if y is None and (r.get("year") or "").strip():
                errs.append(f"{fn} entry {r.get('entry_no')}: year {r['year']!r} but no year_num")
        books += n_book
        skipped += n_skip
        if head.get("entries_on_page") != len(nos):
            errs.append(f"{fn}: summary says {head.get('entries_on_page')} entries, file has {len(nos)}")
        ns = [n for n in nos if isinstance(n, int)]
        if ns != sorted(ns):
            errs.append(f"{fn}: entry numbers are not in printed order ({ns[:8]}...)")
        if len(set(ns)) != len(ns):
            errs.append(f"{fn}: repeated entry numbers")
        seen[page] = ns
        lettered_nos[page] = [n for n in nos if isinstance(n, str)]
    missing_pages = [p for p in range(a, b + 1) if p not in seen]
    # the numbering should run on unbroken from one page to the next
    pages = sorted(seen)
    for p, q in zip(pages, pages[1:]):
        if q != p + 1 or not (seen[p] and seen[q]) or seen[q][0] == seen[p][-1] + 1:
            continue
        # the book numbers some entries 3606a ... 3606k, with no plain 3606: a gap the letters fill
        lettered = {int(m) for page in (p, q) for n in lettered_nos.get(page, [])
                    for m in [re.match(r"\d+", str(n)).group(0)] if m}
        if any(seen[p][-1] < x <= seen[q][0] for x in lettered):
            continue
        errs.append(f"p{p:03d} ends at {seen[p][-1]} but p{q:03d} starts at {seen[q][0]}")
    print(f"pages done {len(seen)}/{b - a + 1}, entries {entries}, books {books}, skipped {skipped}, "
          f"errors {len(errs)}")
    if missing_pages:
        print("missing pages:", missing_pages if len(missing_pages) < 40 else
              f"{len(missing_pages)} (from {missing_pages[0]} to {missing_pages[-1]})")
    for e in errs[:40]:
        print(" ", e)
    return errs


if __name__ == "__main__":
    a = int(sys.argv[1]) if len(sys.argv) > 2 else 1
    b = int(sys.argv[2]) if len(sys.argv) > 2 else 243
    check(a, b)
