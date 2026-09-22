#!/usr/bin/env python3
"""Check the page files transcribed from Wenckstern, A Bibliography of the Japanese Empire, vol. II (1907).

The entries are not numbered in the book, so each page file numbers them `seq` 1..n from the top of the
page, and the check is that the numbering is unbroken and agrees with the page summary.

    validate7.py [START END]      (PDF page numbers; the parts read are 21-461, 509-536, 537-558)
"""
import glob, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PAGES = os.path.join(HERE, "pages")
RANGES = [(21, 461), (509, 536), (537, 558)]
BOOK_KEYS = {"pdf_page", "seq", "author", "title", "place", "publisher", "year", "year_num",
             "extent", "edition", "series", "language", "section", "note"}
SKIPS = {"article", "russian", "out of range"}


def printed(page):
    if page >= 537:
        return page - 536
    if page >= 509:
        return page - 508
    return page - 20


def wanted_pages(a, b):
    return [p for lo, hi in RANGES for p in range(lo, hi + 1) if a <= p <= b]


def check(a=1, b=999):
    errs, seen, books, skipped, entries = [], {}, 0, 0, 0
    for fn in sorted(glob.glob(os.path.join(PAGES, "p*.jsonl"))):
        page = int(os.path.basename(fn)[1:-6])
        if not (a <= page <= b):
            continue
        lines = [l for l in open(fn, encoding="utf-8") if l.strip()]
        if not lines:
            errs.append(f"{fn}: empty")
            continue
        try:
            head = json.loads(lines[0])
        except Exception as e:
            errs.append(f"{fn}: first line is not JSON ({e})")
            continue
        if "entries_on_page" not in head:
            errs.append(f"{fn}: first line is not a page summary")
            continue
        if head.get("printed_page") != printed(page):
            errs.append(f"{fn}: printed_page {head.get('printed_page')} (expected {printed(page)})")
        seqs, n_book, n_skip = [], 0, 0
        for i, line in enumerate(lines[1:], 1):
            try:
                r = json.loads(line)
            except Exception as e:
                errs.append(f"{fn} line {i + 1}: bad JSON ({e})")
                continue
            entries += 1
            if r.get("pdf_page") != page:
                errs.append(f"{fn} seq {r.get('seq')}: pdf_page {r.get('pdf_page')} != {page}")
            seqs.append(r.get("seq"))
            if "skip" in r:
                n_skip += 1
                if r["skip"] not in SKIPS:
                    errs.append(f"{fn} seq {r.get('seq')}: skip {r['skip']!r}")
                if set(r) - {"pdf_page", "seq", "skip", "note"}:
                    errs.append(f"{fn} seq {r.get('seq')}: a skipped entry carries "
                                f"{sorted(set(r) - {'pdf_page', 'seq', 'skip', 'note'})}")
                continue
            n_book += 1
            missing = BOOK_KEYS - set(r)
            if missing:
                errs.append(f"{fn} seq {r.get('seq')}: missing {sorted(missing)}")
            if set(r) - BOOK_KEYS:
                errs.append(f"{fn} seq {r.get('seq')}: unexpected {sorted(set(r) - BOOK_KEYS)}")
            if not (r.get("title") or "").strip():
                errs.append(f"{fn} seq {r.get('seq')}: no title")
            y = r.get("year_num")
            if y is not None and (not isinstance(y, int) or not (1850 <= y <= 1910)):
                errs.append(f"{fn} seq {r.get('seq')}: year_num {y!r}")
            if y is None and (r.get("year") or "").strip() and "no date" not in r["year"].lower() \
                    and "n.d." not in r["year"].lower() and not re.search(r"\d\d\.\.", r["year"]):
                errs.append(f"{fn} seq {r.get('seq')}: year {r['year']!r} but no year_num")
        books += n_book
        skipped += n_skip
        if head.get("entries_on_page") != len(seqs):
            errs.append(f"{fn}: summary says {head.get('entries_on_page')} entries, file has {len(seqs)}")
        if head.get("books") != n_book or head.get("skipped") != n_skip:
            errs.append(f"{fn}: summary says {head.get('books')} books / {head.get('skipped')} skipped, "
                        f"file has {n_book} / {n_skip}")
        if seqs != list(range(1, len(seqs) + 1)):
            errs.append(f"{fn}: seq is not 1..{len(seqs)} in order ({seqs[:8]}...)")
        seen[page] = seqs
    want = wanted_pages(a, b)
    missing_pages = [p for p in want if p not in seen]
    print(f"pages done {len([p for p in seen if p in want])}/{len(want)}, entries {entries}, "
          f"books {books}, skipped {skipped}, errors {len(errs)}")
    if missing_pages:
        print("missing pages:", missing_pages if len(missing_pages) < 40 else
              f"{len(missing_pages)} (from {missing_pages[0]} to {missing_pages[-1]})")
    for e in errs[:40]:
        print(" ", e)
    return errs


if __name__ == "__main__":
    a = int(sys.argv[1]) if len(sys.argv) > 2 else 1
    b = int(sys.argv[2]) if len(sys.argv) > 2 else 999
    check(a, b)
