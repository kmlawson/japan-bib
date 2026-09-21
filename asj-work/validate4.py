#!/usr/bin/env python3
"""Check the page files transcribed from the Asiatic Society of Japan catalogue.

    validate4.py [START END]      (PDF page numbers; the section runs 5-34)
"""
import glob, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PAGES = os.path.join(HERE, "pages")
KEYS = {"pdf_page", "entry_no", "author", "title", "place", "year", "year_num", "volumes",
        "kind", "japan", "japan_why", "note"}
KINDS = {"book", "periodical", "manuscript", "map"}


def check(a=5, b=34):
    errs, seen, n_entries, n_japan = [], set(), 0, 0
    for fn in sorted(glob.glob(os.path.join(PAGES, "p*.jsonl"))):
        page = int(os.path.basename(fn)[1:-6])
        if not (a <= page <= b):
            continue
        seen.add(page)
        lines = [l for l in open(fn, encoding="utf-8") if l.strip()]
        if not lines:
            errs.append(f"{fn}: empty")
            continue
        head = json.loads(lines[0])
        if "entries_on_page" not in head:
            errs.append(f"{fn}: first line is not a page summary")
            continue
        nos = []
        for i, line in enumerate(lines[1:], 1):
            try:
                r = json.loads(line)
            except Exception as e:
                errs.append(f"{fn} line {i + 1}: bad JSON ({e})")
                continue
            n_entries += 1
            missing = KEYS - set(r)
            if missing:
                errs.append(f"{fn} entry {r.get('entry_no')}: missing {sorted(missing)}")
            if set(r) - KEYS:
                errs.append(f"{fn} entry {r.get('entry_no')}: unexpected {sorted(set(r) - KEYS)}")
            if r.get("pdf_page") != page:
                errs.append(f"{fn} entry {r.get('entry_no')}: pdf_page {r.get('pdf_page')} != {page}")
            if r.get("kind") not in KINDS:
                errs.append(f"{fn} entry {r.get('entry_no')}: kind {r.get('kind')!r}")
            if r.get("japan") not in (True, False, "uncertain"):
                errs.append(f"{fn} entry {r.get('entry_no')}: japan {r.get('japan')!r}")
            y, yn = r.get("year"), r.get("year_num")
            if yn is not None and (not isinstance(yn, int) or not (1400 <= yn <= 1900)):
                errs.append(f"{fn} entry {r.get('entry_no')}: year_num {yn!r}")
            if yn is not None and y and str(yn) not in str(y):
                errs.append(f"{fn} entry {r.get('entry_no')}: year {y!r} does not contain {yn}")
            if not (r.get("title") or "").strip() and "cross-reference" not in (r.get("note") or "").lower():
                errs.append(f"{fn} entry {r.get('entry_no')}: no title")   # "SMITH (J.) v. Jones." is fine
            if r.get("japan") is True:
                n_japan += 1
            nos.append(r.get("entry_no"))
        if nos and nos != list(range(1, len(nos) + 1)):
            errs.append(f"{fn}: entry numbers are {nos[:6]}... not 1..{len(nos)}")
        if head.get("entries_on_page") != len(nos):
            errs.append(f"{fn}: summary says {head.get('entries_on_page')} entries, file has {len(nos)}")
    missing_pages = [p for p in range(a, b + 1) if p not in seen]
    print(f"pages done {len(seen)}/{b - a + 1}, entries {n_entries}, marked Japan-related {n_japan}, "
          f"errors {len(errs)}")
    if missing_pages:
        print("missing pages:", missing_pages)
    for e in errs[:40]:
        print(" ", e)
    return errs


if __name__ == "__main__":
    a = int(sys.argv[1]) if len(sys.argv) > 2 else 5
    b = int(sys.argv[2]) if len(sys.argv) > 2 else 34
    check(a, b)
