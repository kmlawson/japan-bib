#!/usr/bin/env python3
"""Merge the Japan-related entries read from the Asiatic Society of Japan's 1888 library catalogue.

The pages were read by eye (pages/pNN.jsonl, one file per page, first line a summary). Everything on
each page was transcribed; the choosing happens here:

  * periodicals are left out, as the compiler asked (runs of journals, transactions, annual reports);
  * only works dated 1850-1955 are taken - the catalogue is of 1888, so in practice 1850-1888, and
    anything undated is left out because the date cannot be checked;
  * only works to do with Japan. The transcriber marked each entry true / false / "uncertain"; the
    uncertain ones are decided here, in JAPAN_DECIDED, so the judgement is written down rather than
    left to a rule.

Duplicates are found as for the other bibliographies (next-bib-work/merge.py): same surname, matching
title proper, years within three.

    asj_merge.py            what would be merged and what would be added
    asj_merge.py --todo     the new books that still need an archive.org lookup
    asj_merge.py --uncertain   the entries whose Japanese connection is undecided
"""
import glob, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "next-bib-work"))
sys.path.insert(0, os.path.join(HERE, "..", "union-catalog-work"))
import merge as M  # noqa: E402

SRC = "Asiatic Society of Japan (1888)"
PAGES = os.path.join(HERE, "pages")
CACHE4 = os.path.join(HERE, "ia_cache4.jsonl")
DECIDED = os.path.join(HERE, "japan_decided.tsv")
FIRST_YEAR, LAST_YEAR = 1850, 1955


def decided():
    """{page|entry: true|false} - the uncertain ones, settled by hand."""
    d = {}
    if os.path.exists(DECIDED):
        for line in open(DECIDED, encoding="utf-8"):
            if line.startswith("#"):
                continue
            p = line.rstrip("\n").split("\t")
            if len(p) >= 2 and p[0].strip():
                d[p[0].strip()] = p[1].strip().lower() in ("yes", "true", "1")
    return d


def author(name):
    """'Adams (Francis Ottiwell)' -> 'Adams, Francis Ottiwell'; anything else is left as printed."""
    a = (name or "").strip()
    m = re.match(r"^([^()]+?)\s*\(([^)]*)\)\s*$", a)
    return f"{m.group(1).strip()}, {m.group(2).strip()}" if m else a


def entries():
    """Every transcribed entry, in page order."""
    out = []
    for fn in sorted(glob.glob(os.path.join(PAGES, "p*.jsonl"))):
        for line in open(fn, encoding="utf-8"):
            if not line.strip():
                continue
            r = json.loads(line)
            if "entries_on_page" in r:
                continue
            out.append(r)
    return out


def wanted():
    """The entries that go into the database, in the shape merge.py works with."""
    dec, out = decided(), []
    for r in entries():
        if r.get("kind") == "periodical":
            continue
        y = r.get("year_num")
        if y is None or not (FIRST_YEAR <= y <= LAST_YEAR):
            continue
        jp = r.get("japan")
        if jp == "uncertain":
            jp = dec.get(f"{r['pdf_page']}|{r['entry_no']}", False)
        if not jp:
            continue
        note = "; ".join(x for x in [r.get("note") or "",
                                     "" if r.get("kind") == "book" else f"A {r.get('kind')} in the catalogue"] if x)
        out.append({
            "author": author(r.get("author")), "title": (r.get("title") or "").strip(),
            "year": str(r.get("year") or ""), "year_start": y,
            "edition": "", "place": r.get("place") or "", "publisher": "", "extent": "",
            "container": "", "type": "book", "section": "", "annotation": "",
            "volumes": r.get("volumes") or "", "note": note,
            "pdf_page": r["pdf_page"], "entry_no": r["entry_no"], "src": SRC, "also": [],
        })
    return out


def where(r):
    return f"{SRC}, PDF p. {r['pdf_page']}, entry {r['entry_no']}"


def new_row(r, cache):
    links, others = (M.split_matches(r, cache) if M.wants_lookup(r) else (None, []))
    parts = []
    if r["place"]:
        parts.append("Imprint: " + r["place"])
    if r["volumes"]:
        parts.append("Extent: " + r["volumes"])
    parts.append(where(r))
    if r["note"]:
        parts.append("Note: " + r["note"])
    if others:
        parts.append("IA other editions: " + "; ".join(
            f"https://archive.org/details/{m['identifier']} ({m['year']})" for m in others[:8]))
    linktxt = None if links is None else "\n".join(f"https://archive.org/details/{m['identifier']}" for m in links)
    return [r["author"], r["title"], r["year"], r["year_start"], "", r["volumes"], linktxt,
            " | ".join(parts), SRC, "book"]


def split(rows):
    """(attach, new): attach = {row index: [records]}, new = records to add as rows of their own."""
    idx = M.Index()
    for i, row in enumerate(rows):
        kind = "book" if row[9] in ("book", "periodical") else "part"
        idx.add(M.item(M.sur(row[0]), row[1], row[3], kind, ("row", i)))
    attach, new = {}, []
    for r in wanted():
        tk, full, su = M.tkey(r["title"]), M.norm(r["title"]), M.sur(r["author"])
        hit = idx.find(su, tk, full, r["year_start"], "book")
        if hit is None and su and len(tk) >= 25:
            hit = idx.find("", tk, full, r["year_start"], "book", strict=len(tk) < 40)
        if hit is None and len(tk) >= 20:
            hit = idx.exact(tk, full, r["year_start"], "book")
        if hit is not None:
            kind, ref = hit["ref"]
            if kind == "row":
                attach.setdefault(ref, []).append(r)
            else:
                new[ref]["also"].append(r)
            continue
        new.append(r)
        idx.add(M.item(su, r["title"], r["year_start"], "book", ("new", len(new) - 1)))
    return attach, new


def xref(r):
    return f"Also in {where(r)} (as {r['year']})"


def apply(rows):
    """Attach the duplicates and append the rest; returns (attached, added)."""
    attach, new = split(rows)
    for i, rs in attach.items():
        for r in rs:
            if SRC not in rows[i][8]:
                rows[i][8] += "; " + SRC
            rows[i][7] += " | " + xref(r)
    cache = M.load_cache2(CACHE4)
    added = [new_row(r, cache) for r in new]
    rows += added
    return sum(len(v) for v in attach.values()), len(added)


if __name__ == "__main__":
    import sqlite3
    if "--uncertain" in sys.argv:
        dec = decided()
        for r in entries():
            if r.get("japan") == "uncertain" and f"{r['pdf_page']}|{r['entry_no']}" not in dec:
                print(f"{r['pdf_page']}|{r['entry_no']}\t{author(r.get('author'))} | {r.get('title')} | "
                      f"{r.get('place')} {r.get('year')} | {r.get('japan_why')}")
        sys.exit()
    con = sqlite3.connect(os.path.join(HERE, "..", "union-catalog-work", "list-full.sqlite"))
    rows = [list(x) for x in con.execute(
        "SELECT author,title,year,year_num,edition,volume,links,other,source,type FROM books "
        "WHERE source <> ? ORDER BY id", (SRC,))]
    con.close()
    attach, new = split(rows)
    cache = M.load_cache2(CACHE4)
    todo = [r for r in new if M.wants_lookup(r) and M.lkey(r) not in cache]
    if "--todo" in sys.argv:
        for r in todo:
            print(f"{r['author']} | {r['title'][:70]} | {r['year']}")
    print(f"{len(entries())} entries transcribed, {len(wanted())} wanted: "
          f"{sum(len(v) for v in attach.values())} already in the database, {len(new)} new "
          f"({len(todo)} still to look up on archive.org)")
