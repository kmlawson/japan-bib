#!/usr/bin/env python3
"""Merge the books read from Wenckstern's *A Bibliography of the Japanese Empire*, vol. II (1907) into the
database. The volume covers the literature of 1894-1906, with a supplement to Pagès's *Bibliographie
japonaise* (mostly 16th-18th century) and Palmgren's list of the Swedish literature on Japan.

The pages were read by eye (pages/pNNN.jsonl, one file per page, first line a summary; the entries are
unnumbered in the book and carry a position on the page, `seq`). Books only: journal articles,
Russian-language material and anything published before 1850 were marked as skipped when they were
read, and never reach this stage. What is left is filtered once more here, so that the rule is visible
rather than trusted:

  * an entry with a `skip` is left out, whatever the reason;
  * a book must be dated 1850-1955 (in practice 1850-1907), or carry no date at all;
  * Cyrillic in the author or title, or a remark saying the work is in Russian, is left out;
  * chapter XXI, "Works written by Japanese scholars in European languages on subjects not relating
    to Japan in particular", and section XIII e (dissertations by Japanese medical men in Germany) are
    left out whole, and so is every entry keyed in not_about_japan.tsv: general works with a chapter
    on Japan, books on the Russian side of the war, foreign consular series. The compiler asked for
    works on Japan only.

Duplicates are found as for the other bibliographies (next-bib-work/merge.py): same surname, matching
title proper, years within three.

    wenck_merge.py            what would be merged and what would be added
    wenck_merge.py --todo     the new books that still need an archive.org lookup
"""
import glob, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "next-bib-work"))
sys.path.insert(0, os.path.join(HERE, "..", "union-catalog-work"))
import merge as M  # noqa: E402

SRC = "Wenckstern (1907)"
PAGES = os.path.join(HERE, "pages")
CACHE7 = os.path.join(HERE, "ia_cache7.jsonl")
FIRST_YEAR, LAST_YEAR = 1850, 1955
CYRILLIC = re.compile(r"[Ѐ-ӿ]")
RUSSIAN_NOTE = re.compile(r"in russian|russisch", re.I)
NOT_ABOUT_JAPAN = os.path.join(HERE, "not_about_japan.tsv")
NOT_ON_JAPAN = re.compile(r"^XXI\. |^XIII\. Medicine / e\. ")   # sections left out whole: chapter XXI, and XIII e
# (dissertations by Japanese medical men in Germany, "not referring to Medicine in Japan")


def printed(page):
    """(printed page, part) for a PDF page: the main list, the Pagès supplement or the Swedish list."""
    if page >= 537:
        return page - 536, "Swedish list"
    if page >= 509:
        return page - 508, "Pagès supplement"
    return page - 20, ""


def excluded():
    """The keys (language.key) of the entries the compiler ruled not to be about Japan."""
    sys.path.insert(0, os.path.join(HERE, "..", "union-catalog-work"))
    out = set()
    if os.path.exists(NOT_ABOUT_JAPAN):
        for line in open(NOT_ABOUT_JAPAN, encoding="utf-8"):
            if line.strip() and not line.startswith("#"):
                out.add(line.split("\t")[0].strip())
    return out


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
    from language import key as rowkey
    out, drop = [], excluded()
    for r in entries():
        if r.get("skip") or NOT_ON_JAPAN.match(r.get("section") or ""):
            continue
        if rowkey(r.get("author"), r.get("title"), r.get("year")) in drop:
            continue
        y = r.get("year_num")
        if y is not None and not (FIRST_YEAR <= y <= LAST_YEAR):
            continue
        blob = (r.get("author") or "") + " " + (r.get("title") or "")
        if CYRILLIC.search(blob) or RUSSIAN_NOTE.search(r.get("note") or "") \
                or (r.get("language") or "").lower() == "russian":
            continue
        year = str(r.get("year") or "").strip()
        out.append({
            "author": (r.get("author") or "").strip(),
            "title": (r.get("title") or "").strip(),
            "year": year or "n.d.", "year_start": y,
            "edition": r.get("edition") or "", "place": r.get("place") or "",
            "publisher": r.get("publisher") or "", "extent": r.get("extent") or "",
            "container": "", "type": "book", "section": r.get("section") or "", "annotation": "",
            "series": r.get("series") or "", "language": r.get("language") or "",
            "note": r.get("note") or "", "pdf_page": r["pdf_page"], "seq": r["seq"],
            "src": SRC, "also": [],
        })
    return out


def where(r):
    p, part = printed(r["pdf_page"])
    return f"{SRC}{', ' + part if part else ''} p. {p}"


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
    m = M.VOLS.search(r["extent"]) or M.VOLS.search(r["title"])
    return [r["author"], r["title"], r["year"], r["year_start"], r["edition"], m.group(0).strip() if m else "",
            linktxt, " | ".join(parts), SRC, "book"]


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
    cache = M.load_cache2(CACHE7)
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
    cache = M.load_cache2(CACHE7)
    todo = [r for r in new if M.wants_lookup(r) and M.lkey(r) not in cache]
    if "--todo" in sys.argv:
        for r in todo:
            print(f"{r['author']} | {r['title'][:70]} | {r['year']}")
    if "--dups" in sys.argv:
        for i, rs in sorted(attach.items()):
            for r in rs:
                print(f"{rows[i][0]} | {rows[i][1][:60]} | {rows[i][2]}  <=  {r['author']} | {r['title'][:60]} | {r['year']}")
    print(f"{len(all_lines)} entries read ({dict(kinds)}), {len(wanted())} books wanted: "
          f"{sum(len(v) for v in attach.values())} already in the database, {len(new)} new "
          f"({len(todo)} still to look up on archive.org)")
