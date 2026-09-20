#!/usr/bin/env python3
"""Build ../list.sqlite from batches/*.jsonl + ia_cache.jsonl (same records and link filter as list.md).

Union Catalog rows come first; records from the later bibliographies (../next-bib-work: Borton 1954,
Henshall 2014) are merged in by next-bib-work/merge.py - a record already present (same author and
title, years within 3) only adds its source name and a cross-reference to the existing row.

Table books: id, author, title, year, year_num, edition, volume, links, other, source, type
  source    bibliographies listing the work, "; "-separated
  type      book | periodical | article | chapter
  access    best way any linked archive.org copy can be read: open (freely readable) | borrow (controlled
            lending, free account) | unknown (not checked) | '' (no link). Items that can be neither read nor
            borrowed (print-disabled readers only, or gone) are not linked at all.
  links_access  the same flag for each URL in `links`, one per line, same order (open copies are listed first)
  year      as printed ("1874-75", "n.d.", "19--")
  year_num  integer first year for range queries (NULL when undated)
  volume    volume statement from the extent ("2 v.", "3v. in 1.") or, failing that, a volume
            designation in the title ("v.1", "Bd.2", "Pt.1-3")
  links     archive.org URLs, one per line ('' = searched, no match; NULL = undated, not searched);
            only items dated within 3 years of the entry - other dates are listed in `other` as other editions
  other     place, publisher, extent, series, holdings, rare flag, catalogue page, note
books_fts: full-text index over author, title, other (FTS5, diacritics folded).
"""
import os, re, sqlite3, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ia_lookup import load_records, load_cache, HERE
from build_list import in_range, years, ia_matches, ia_other_editions, is_loose
sys.path.insert(0, os.path.join(HERE, "..", "next-bib-work"))
import merge as M  # noqa: E402

DB = os.path.join(HERE, "..", "list.sqlite")
VOL_EXTENT = re.compile(r"\(?\d+\)?\s*(?:v\.|vols?\.|sets\.|pts?\. in \d+\s*v\.)(?:\s*in\s*\d+\.?)?(?:\s*\([^)]*\))?", re.I)
VOL_TITLE = re.compile(r"\b(?:v\.|vol\.|Bd\.|Band|Tome|Tom|t\.|T\.|Deel|Pt\.|pt\.|Part|Book|Chast'|Heft|Fasciculus|no\.)\s*[IVX\d]+(?:\s*[-–,]\s*[IVX\d]+)*\b")


ACCESS_DIR = os.path.join(HERE, "..", "next-bib-work", "ia_access")
RANK = {"open": 0, "borrow": 1, "restricted": 2, "unknown": 3}


def load_access():
    from build_list import access_of
    return access_of


def with_access(row, acc):
    """Sort a row's links open-first and append the per-link and the row-level access flags."""
    links = row[6]
    if not links:
        return row + ["", ""]
    urls = links.split("\n")
    st = [acc(u.rsplit("/", 1)[1]) for u in urls]
    order = sorted(range(len(urls)), key=lambda i: (RANK[st[i]], i))
    urls, st = [urls[i] for i in order], [st[i] for i in order]
    row[6] = "\n".join(urls)
    return row + [st[0], "\n".join(st)]


def volume(r):
    m = VOL_EXTENT.search(r["extent"])
    if m:
        return re.sub(r"(\d\)?)\s*(v\.|vols?\.)", r"\1 \2", m.group(0).strip())  # "2v." -> "2 v." (printed form stays in other)
    m = VOL_TITLE.search(r["title"])
    return m.group(0).strip() if m else ""


def other(r):
    parts = []
    imprint = ", ".join(x for x in (r["place"], r["publisher"]) if x)
    if imprint:
        parts.append("Imprint: " + imprint)
    if r["extent"]:
        parts.append("Extent: " + r["extent"])
    if r["series"]:
        parts.append("Series: " + r["series"])
    if r["holdings"]:
        parts.append("Holdings: " + " ".join(r["holdings"]))
    if r["rare"]:
        parts.append("Rare (starred in catalogue)")
    parts.append(f"Catalogue p. {r['printed_page'] or '?'} (PDF p. {r['pdf_page']}, col. {r['col']})")
    if r["note"]:
        parts.append("Note: " + r["note"])
    return " | ".join(parts)


if __name__ == "__main__":
    recs, cache = load_records(), load_cache()
    if os.path.exists(DB):
        os.remove(DB)
    con = sqlite3.connect(DB)
    con.executescript("""
        CREATE TABLE books (
            id INTEGER PRIMARY KEY,
            author TEXT NOT NULL,
            title TEXT NOT NULL,
            year TEXT NOT NULL,
            year_num INTEGER,
            edition TEXT NOT NULL,
            volume TEXT NOT NULL,
            links TEXT,
            other TEXT NOT NULL,
            source TEXT NOT NULL,
            type TEXT NOT NULL,
            access TEXT NOT NULL,
            links_access TEXT NOT NULL
        );
        CREATE VIRTUAL TABLE books_fts USING fts5(
            author, title, other, content='books', content_rowid='id',
            tokenize="unicode61 remove_diacritics 2");
    """)
    rows = []
    for r in recs:
        rng = in_range(r)
        if rng is False:
            continue
        oth = []
        if rng is None:
            links, ynum = None, None
        else:
            ms = ia_matches(r, cache) or []
            links = "\n".join(f"https://archive.org/details/{m['identifier']}" for m in ms)
            oth = ia_other_editions(r, cache)
            ys = [y for y in years(r) if 1850 <= y <= 1955] or years(r)
            ynum = r["year_start"] if r["year_start"] is not None else min(ys)
        o = other(r)
        if rng and is_loose(r, cache):
            o += " | IA match: loose (title key words, date within 4 years; author not compared)"
        if oth:
            o += " | IA other editions: " + "; ".join(
                f"https://archive.org/details/{m['identifier']} ({m['year']})" for m in oth)
        rows.append([r["author"].strip(), r["title"].strip(), r["year"], ynum, r["edition"], volume(r), links, o, "Union Catalog (Fukuda)", "book"])
    n_uc = len(rows)
    attach, new = M.merge([dict(author=x[0], title=x[1], year_num=x[3]) for x in rows])
    for i, rs in attach.items():
        for r in rs:
            if r["src"] not in rows[i][8]:
                rows[i][8] += "; " + r["src"]
            rows[i][7] += " | " + M.xref(r)
    cache2 = M.load_cache2()
    rows += [M.new_row(r, cache2) for r in new]
    acc = load_access()
    rows = [with_access(list(x), acc) for x in rows]
    con.executemany("INSERT INTO books(author,title,year,year_num,edition,volume,links,other,source,type,access,links_access) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    con.execute("INSERT INTO books_fts(rowid,author,title,other) SELECT id,author,title,other FROM books")
    con.executescript("""
        CREATE INDEX idx_author ON books(author COLLATE NOCASE);
        CREATE INDEX idx_title ON books(title COLLATE NOCASE);
        CREATE INDEX idx_year ON books(year_num);
        CREATE INDEX idx_type ON books(type);
        CREATE INDEX idx_access ON books(access);
    """)
    con.commit()
    q = lambda s: con.execute(s).fetchone()[0]
    print("Union Catalog rows", n_uc, "| of which also in a later bibliography", len(attach), "| new rows", len(new))
    for t, n in con.execute("SELECT source, count(*) FROM books GROUP BY source ORDER BY 2 DESC"):
        print(f"  {n:5d}  {t}")
    for a, n in con.execute("SELECT access, count(*) FROM books WHERE links<>'' GROUP BY access ORDER BY 2 DESC"):
        print(f"  access {a or '-':10s} {n}")
    print("rows", q("SELECT count(*) FROM books"), "| with links", q("SELECT count(*) FROM books WHERE links<>''"),
          "| undated", q("SELECT count(*) FROM books WHERE year_num IS NULL"),
          "| with edition", q("SELECT count(*) FROM books WHERE edition<>''"),
          "| with volume", q("SELECT count(*) FROM books WHERE volume<>''"))
    con.execute("VACUUM")
    con.close()
