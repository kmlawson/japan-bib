#!/usr/bin/env python3
"""Merge the entries transcribed from Dower & George into the rows build_db.py is assembling.

The entries were read by eye from the page scans (pages/pNNN.jsonl, one file per page; the first line
of each file is that page's summary). Only works first published 1850-1960 were written out.

Dower prints names in their natural order and titles in capitals, so both are put into the form the
rest of the database uses: "Beloff, Max" and "Soviet Policy in the Far East". The capitals carry no
information about the original capitalisation, so a name that the rule would get wrong (MacArthur,
McCoy, GHQ) is listed in KEEP below; anything still wrong can be corrected there.

Duplicates are found the same way as for Borton and Henshall (next-bib-work/merge.py): same surname,
matching title proper, years within three. A duplicate only adds the source name and a cross-reference
to the row that is already there.

    dower_merge.py              what would be merged and what would be added
    dower_merge.py --todo       the new books that still need an archive.org lookup
"""
import difflib, glob, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "next-bib-work"))
sys.path.insert(0, os.path.join(HERE, "..", "union-catalog-work"))
import merge as M  # noqa: E402

PAGES = os.path.join(HERE, "pages")
CACHE3 = os.path.join(HERE, "ia_cache3.jsonl")
SRC = M.SRC_DOWER

# words that stay lower case inside a title
SMALL = set("a an and as at but by for from in into nor of on onto or over per the to up upon via vs with "
            "de del della des du la le les von van der den het en y".split())
# capitalisations the plain rule would get wrong; compared in lower case
KEEP = {}
for w in """MacArthur McCoy McCormack MacDonald McClain McKean McLaren MacNair McLaughlin DeVos DeBary
        GHQ SCAP UN US USA USSR CIA OSS POW POWs FEC IMTFE NHK NIRA UNESCO IPR
        II III IV VI VII VIII IX XI XII XIII XIV XV XVI XVII XVIII XIX
        Japan Japanese Tokyo Kyoto Osaka Nagasaki Hiroshima Okinawa Korea Korean China Chinese Manchuria
        Manchukuo Taiwan Formosa America American Americans Britain British Soviet Russia Russian Europe
        European Asia Asian Pacific Meiji Taisho Shōwa Showa Nippon Nihon Ainu Shinto Buddhist Buddhism
        Christian Christianity Marxist Marxism Diet Emperor""".split():
    KEEP[w.lower()] = w
APOS = re.compile(r"^(\w+)'(\w+)$")
CORP = re.compile(r"\b(?:Ministry|Bureau|Office|Association|Institute|Society|Department|Commission|"
                  r"University|Press|Government|Command|Section|Committee|Council|Agency|Corps|Service|"
                  r"Headquarters|Nations|States|Library|Museum|Company|Board|Staff|Conference)\b", re.I)


def titlecase(t):
    """A title printed in capitals put back into the ordinary form. Words already in mixed case (a
    transcriber's note, a macron'd romanisation) are left as they are."""
    if t != t.upper():
        return t
    out, first = [], True
    parts = re.split(r"(\s+)", t)
    for p in parts:
        if not p.strip():
            out.append(p)
            continue
        w = p
        core = w.strip("\"'([{,.;:!?)]}‘’“”")
        pre, post = w[:w.find(core)] if core else "", w[w.find(core) + len(core):] if core else ""
        low = core.lower()
        stem = low[:-2] if low.endswith("'s") else low      # MACARTHUR'S -> MacArthur's
        if low in KEEP:
            new = KEEP[low]
        elif stem in KEEP:
            new = KEEP[stem] + "'s"

        elif not first and low in SMALL:
            new = low
        elif core[:2].upper() == "MC" and len(core) > 3:
            new = "Mc" + core[2].upper() + core[3:].lower()
        elif "-" in core:
            new = "-".join(x[:1].upper() + x[1:].lower() if x.lower() not in SMALL or i == 0 else x.lower()
                           for i, x in enumerate(core.split("-")))
        else:
            new = core[:1].upper() + core[1:].lower()
        m = APOS.match(new)
        if m and len(m.group(2)) == 1:          # JAPAN'S -> Japan's, not Japan'S
            new = m.group(1) + "'" + m.group(2).lower()
        out.append(pre + new + post)
        first = post.endswith(":") or (not core)
    return "".join(out)


def author(name):
    """'Paul H. Clyde & Burton F. Beers' -> 'Clyde, Paul H. & Burton F. Beers'; only the first name is
    inverted, an editor statement is kept ('Morley, James, ed.'), corporate headings are left alone."""
    a = (name or "").strip()
    if not a:
        return ""
    tail = ""
    m = re.search(r",?\s+(eds?\.|trs?\.|comps?\.|ed\.\s*(?:and|&)\s*trs?\.)$", a, re.I)
    if m:
        a, tail = a[:m.start()].strip(), ", " + m.group(1)
    m = re.search(r"\s*(?:,\s*)?(?:&|\band\b)\s+|,\s+", a)   # where the first name ends
    first, rest = (a[:m.start()], a[m.start():]) if m else (a, "")
    toks = first.split()
    if 2 <= len(toks) <= 4 and not CORP.search(first):
        first = f"{toks[-1]}, {' '.join(toks[:-1])}"
    return (first + rest + tail).strip()


def load():
    """Every in-range entry, in page order, in the shape next-bib-work/merge.py works with."""
    out = []
    for fn in sorted(glob.glob(os.path.join(PAGES, "p*.jsonl"))):
        for line in open(fn, encoding="utf-8"):
            if not line.strip():
                continue
            r = json.loads(line)
            if "entries_on_page" in r:          # the page summary
                continue
            out.append({
                "author": author(r.get("author", "")),
                "title": titlecase((r.get("title") or "").strip()),
                "container": r.get("container", ""),
                "edition": r.get("edition", ""),
                "place": "",
                "publisher": r.get("publisher", ""),
                "extent": "",
                "year": r.get("year", ""),
                "year_start": r.get("year_start"),
                "type": r.get("type") or "book",
                "section": r.get("section", ""),
                "annotation": r.get("annotation", ""),
                "note": r.get("note", ""),
                "printed_page": r.get("printed_page"),
                "pdf_page": r.get("pdf_page"),
                "entry_no": r.get("entry_no"),
                "src": SRC,
                "also": [],
            })
    return out


def index_of(rows):
    """An index over the rows already assembled (Union Catalog + the other bibliographies + Zotero + NDL)."""
    idx = M.Index()
    for i, row in enumerate(rows):
        kind = "book" if row[9] in ("book", "periodical") else "part"
        idx.add(M.item(M.sur(row[0]), row[1], row[3], kind, ("row", i)))
    return idx


def match(idx, r):
    """The row this record duplicates, or None. Same tests as merge.merge()."""
    k = M.kind_of(r)
    tk, full, su = M.tkey(r["title"]), M.norm(r["title"]), M.sur(r["author"])
    hit = idx.find(su, tk, full, r["year_start"], k)
    if hit is None and su:
        for other in list(idx.b):
            if other and other != su and other[0] == su[0] and \
                    difflib.SequenceMatcher(None, su, other).ratio() >= 0.8:
                hit = idx.find(other, tk, full, r["year_start"], k)
                if hit:
                    break
    if hit is None and su and len(tk) >= 25:
        hit = idx.find("", tk, full, r["year_start"], k, strict=len(tk) < 40)
    if hit is None and len(tk) >= 20 and r["year_start"] is not None:
        hit = idx.exact(tk, full, r["year_start"], k)
    return hit


def split(rows):
    """(attach, new): attach = {row index: [records]}, new = records to add as rows of their own."""
    idx, attach, new = index_of(rows), {}, []
    for r in load():
        hit = match(idx, r)
        if hit is not None:
            kind, ref = hit["ref"]
            if kind == "row":
                attach.setdefault(ref, []).append(r)
            else:
                new[ref]["also"].append(r)
            continue
        new.append(r)
        idx.add(M.item(M.sur(r["author"]), r["title"], r["year_start"], M.kind_of(r), ("new", len(new) - 1)))
    return attach, new


def apply(rows, last_year=None):
    """Attach the duplicates to the rows they repeat and append the rest. Called by build_db.py after
    every other source, so that the ids of the existing rows do not move."""
    attach, new = split(rows)
    for i, rs in attach.items():
        for r in rs:
            if SRC not in rows[i][8]:
                rows[i][8] += "; " + SRC
            rows[i][7] += " | " + M.xref(r)
    cache = M.load_cache2(CACHE3)
    added = [M.new_row(r, cache) for r in new]
    if last_year is not None:
        added = [x for x in added if x[3] is None or x[3] <= last_year]
    rows += added
    return sum(len(v) for v in attach.values()), len(added), len(new) - len(added)


if __name__ == "__main__":
    import sqlite3
    con = sqlite3.connect(os.path.join(HERE, "..", "list.sqlite"))
    rows = [list(x) + ["", "", ""] for x in con.execute(
        "SELECT author,title,year,year_num,edition,volume,links,other,source,type FROM books ORDER BY id")]
    con.close()
    attach, new = split(rows)
    books = [r for r in new if M.wants_lookup(r)]
    cache = M.load_cache2(CACHE3)
    todo = [r for r in books if M.lkey(r) not in cache]
    if "--todo" in sys.argv:
        for r in todo:
            print(f"{r['author']} | {r['title'][:70]} | {r['year']}")
    print(f"{len(load())} Dower entries: {sum(len(v) for v in attach.values())} already in the database, "
          f"{len(new)} new ({len(books)} books to look up, {len(todo)} not yet looked up)")
