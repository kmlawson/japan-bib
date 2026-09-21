#!/usr/bin/env python3
"""Merge the books read from Nachod's *Bibliography of the Japanese Empire 1906-1926* into the database.

The pages were read by eye (pages/pNNN.jsonl, one file per page, first line a summary). The compiler
asked for books only: journal articles, Russian-language material and anything published before 1850
were marked as skipped when they were read, and never reach this stage. What is left is filtered once
more here, so that the rule is visible rather than trusted:

  * an entry with a `skip` is left out, whatever the reason;
  * a book must be dated 1850-1955 (the volume was published in 1928, so in practice 1850-1928);
  * Cyrillic in the author or title, or a remark saying the work is in Russian, is left out even when
    the transcriber did not mark it.

Duplicates are found as for the other bibliographies (next-bib-work/merge.py): same surname, matching
title proper, years within three.

    bje_merge.py            what would be merged and what would be added
    bje_merge.py --todo     the new books that still need an archive.org lookup
"""
import glob, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "next-bib-work"))
sys.path.insert(0, os.path.join(HERE, "..", "union-catalog-work"))
import merge as M  # noqa: E402

SRC = "Nachod (1928)"
PAGES = os.path.join(HERE, "pages")
CACHE5 = os.path.join(HERE, "ia_cache5.jsonl")
FIRST_YEAR, LAST_YEAR = 1850, 1955
CYRILLIC = re.compile(r"[Ѐ-ӿ]")
RUSSIAN_NOTE = re.compile(r"russisch|in russian", re.I)


def entries():
    """Every transcribed line, in page order, summaries left out."""
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
    """The books that go into the database, in the shape next-bib-work/merge.py works with."""
    out = []
    for r in entries():
        if r.get("skip"):
            continue
        y = r.get("year_num")
        if y is None or not (FIRST_YEAR <= y <= LAST_YEAR):
            continue
        blob = (r.get("author") or "") + " " + (r.get("title") or "")
        if CYRILLIC.search(blob) or RUSSIAN_NOTE.search(r.get("note") or ""):
            continue
        out.append({
            "author": (r.get("author") or "").strip(),
            "title": (r.get("title") or "").strip(),
            "year": str(r.get("year") or ""), "year_start": y,
            "edition": r.get("edition") or "", "place": r.get("place") or "",
            "publisher": r.get("publisher") or "", "extent": r.get("extent") or "",
            "container": "", "type": "book", "section": r.get("section") or "", "annotation": "",
            "series": r.get("series") or "", "language": r.get("language") or "",
            "note": r.get("note") or "", "pdf_page": r["pdf_page"], "entry_no": r["entry_no"],
            "src": SRC, "also": [],
        })
    return out


def where(r):
    return f"{SRC} no. {r['entry_no']}, p. {r['pdf_page'] + 149}"


def xref(r):
    return f"Also in {where(r)} (as {r['year']})"


def new_row(r, cache):
    links, others = (M.split_matches(r, cache) if M.wants_lookup(r) else (None, []))
    parts = []
    imprint = ", ".join(x for x in (r["place"], r["publisher"]) if x)
    if imprint:
        parts.append("Imprint: " + imprint)
    if r["extent"]:
        parts.append("Extent: " + r["extent"])
    if r["series"]:
        parts.append("Series: " + r["series"])
    if r["language"]:
        parts.append("Language: " + r["language"])
    if r["section"]:
        parts.append("Section: " + r["section"])
    parts.append(where(r))
    if r["note"]:
        parts.append("Note: " + r["note"])
    for d in r["also"]:
        parts.append(xref(d))
    if others:
        parts.append("IA other editions: " + "; ".join(
            f"https://archive.org/details/{m['identifier']} ({m['year']})" for m in others[:8]))
    linktxt = None if links is None else "\n".join(f"https://archive.org/details/{m['identifier']}" for m in links)
    return [r["author"], r["title"], r["year"], r["year_start"], r["edition"], "", linktxt,
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
        if hit is None and su:
            import difflib
            for other in list(idx.b):
                if other and other != su and other[0] == su[0] and \
                        difflib.SequenceMatcher(None, su, other).ratio() >= 0.8:
                    hit = idx.find(other, tk, full, r["year_start"], "book")
                    if hit:
                        break
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


def apply(rows):
    """Attach the duplicates and append the rest; returns (attached, added)."""
    attach, new = split(rows)
    for i, rs in attach.items():
        for r in rs:
            if SRC not in rows[i][8]:
                rows[i][8] += "; " + SRC
            rows[i][7] += " | " + xref(r)
    cache = M.load_cache2(CACHE5)
    added = [new_row(r, cache) for r in new]
    rows += added
    return sum(len(v) for v in attach.values()), len(added)


if __name__ == "__main__":
    import collections, sqlite3
    all_lines = entries()
    kinds = collections.Counter(r.get("skip", "book") for r in all_lines)
    con = sqlite3.connect(os.path.join(HERE, "..", "union-catalog-work", "list-full.sqlite"))
    rows = [list(x) for x in con.execute(
        "SELECT author,title,year,year_num,edition,volume,links,other,source,type FROM books "
        "WHERE source <> ? ORDER BY id", (SRC,))]
    con.close()
    attach, new = split(rows)
    cache = M.load_cache2(CACHE5)
    todo = [r for r in new if M.wants_lookup(r) and M.lkey(r) not in cache]
    if "--todo" in sys.argv:
        for r in todo:
            print(f"{r['author']} | {r['title'][:70]} | {r['year']}")
    print(f"{len(all_lines)} entries read ({dict(kinds)}), {len(wanted())} books wanted: "
          f"{sum(len(v) for v in attach.values())} already in the database, {len(new)} new "
          f"({len(todo)} still to look up on archive.org)")
