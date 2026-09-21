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
  links_access  the same flag for each URL in `links`, one per line, same order
  language  language of the work, from the source's own statement where there is one, otherwise worked out
            from the title (see language.py; decisions made by hand are in language_fixes.tsv)
  links_checked 1 for a link that was checked by hand (Zotero collection "Japan Online"), else 0, same order.
                Hand-checked links come first, then open copies, then borrow-only ones.
  year      as printed ("1874-75", "n.d.", "19--")
  year_num  integer first year for range queries (NULL when undated). Rows dated later than LAST_YEAR
            are deleted from the published copy after the ids are given out, so that raising or lowering
            the cut does not move any id; the working copy keeps them.
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
from build_list import LAST_YEAR, in_range, years, ia_matches, ia_other_editions, is_loose
sys.path.insert(0, os.path.join(HERE, "..", "next-bib-work"))
import merge as M  # noqa: E402
sys.path.insert(0, os.path.join(HERE, "..", "zotero-work"))
import zotero_merge as Z  # noqa: E402
from language import guess as guess_language, fixes as language_fixes, key as language_key  # noqa: E402
sys.path.insert(0, os.path.join(HERE, "..", "ndl-work"))
import ndl_merge as N  # noqa: E402
sys.path.insert(0, os.path.join(HERE, "..", "gallica-work"))
import gallica_merge as GAL  # noqa: E402
sys.path.insert(0, os.path.join(HERE, "..", "dower-work"))
import dower_merge as D  # noqa: E402
sys.path.insert(0, os.path.join(HERE, "..", "onlinebooks-work"))
import ob_merge as OB  # noqa: E402
sys.path.insert(0, os.path.join(HERE, "..", "extra-work"))
import extra_merge as X  # noqa: E402
sys.path.insert(0, os.path.join(HERE, "..", "libraries-work"))
import lib_merge as LIB  # noqa: E402
sys.path.insert(0, os.path.join(HERE, "..", "asj-work"))
import asj_merge as ASJ  # noqa: E402

DB = os.path.join(HERE, "..", "list.sqlite")        # published: without the bibliographers' annotations
DB_FULL = os.path.join(HERE, "list-full.sqlite")    # our own copy: everything, stays out of the repository
ANNOT = re.compile(r"\s*\|\s*Annotation: [^|]*")
XREF_ANNOT = re.compile(r"(Also in [^|:]*\([^)]*\)[^|:]*): [^|]*")
# Languages left out of the published database. The working copy (list-full.sqlite) keeps them, so
# hiding is reversible: take a language out of this set and rebuild. Rows are deleted after insertion,
# so that ids - and the language fixes keyed to them - do not shift.
HIDE_LANGUAGES = {
    "Vietnamese",   # not a Western language
    "Latin",        # hidden for now at the user's request (scientific and church works)
}
VOL_EXTENT = re.compile(r"\(?\d+\)?\s*(?:v\.|vols?\.|sets\.|pts?\. in \d+\s*v\.)(?:\s*in\s*\d+\.?)?(?:\s*\([^)]*\))?", re.I)
VOL_TITLE = re.compile(r"\b(?:v\.|vol\.|Bd\.|Band|Tome|Tom|t\.|T\.|Deel|Pt\.|pt\.|Part|Book|Chast'|Heft|Fasciculus|no\.)\s*[IVX\d]+(?:\s*[-–,]\s*[IVX\d]+)*\b")


ACCESS_DIR = os.path.join(HERE, "..", "next-bib-work", "ia_access")
RANK = {"open": 0, "borrow": 1, "restricted": 2, "unknown": 3}


def load_access():
    from build_list import access_of
    return access_of


def with_access(row, acc, checked):
    """Sort a row's links (hand-checked first, then open, then borrow) and append the row-level access flag,
    the per-link access flags and the per-link checked flags."""
    links = row[6]
    if not links:
        return row + ["", "", ""]
    urls = links.split("\n")
    st = [checked.get(u) or (acc(u.rsplit("/", 1)[1]) if "archive.org/details/" in u else "open") for u in urls]
    order = sorted(range(len(urls)), key=lambda i: (urls[i] not in checked, RANK[st[i]], i))
    urls, st = [urls[i] for i in order], [st[i] for i in order]
    row[6] = "\n".join(urls)
    return row + [st[0], "\n".join(st), "\n".join("1" if u in checked else "0" for u in urls)]


def volume(r):
    m = VOL_EXTENT.search(r["extent"])
    if m:
        return re.sub(r"(\d\)?)\s*(v\.|vols?\.)", r"\1 \2", m.group(0).strip())  # "2v." -> "2 v." (printed form stays in other)
    m = VOL_TITLE.search(r["title"])
    return m.group(0).strip() if m else ""


def strip_annotations(text):
    """Remove the annotations written by the compilers of the printed bibliographies (their own words):
    the "Annotation: ..." parts and the comment that follows an "Also in ..." cross-reference."""
    t = ANNOT.sub("", text)
    t = XREF_ANNOT.sub(r"\1", t)
    return re.sub(r"\s*\|\s*\|", " |", t).strip(" |")


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


# Titles as the sources print them are in sentence case and usually end in a full stop, because they were
# copied from catalogue cards. English titles are put into title case for display and the final stop is
# dropped. Only the stored title changes: everything that matches rows (language fixes, Gallica, Online
# Books) keys on the title folded to letters and digits, which this does not touch.
SMALL_WORDS = set("""a an the and but or nor for of in into on onto to from by with without at as over under
    after before between through during against about above across along among around per via vs versus is""".split())
ABBREV_END = re.compile(r"(?:\b[A-Z]\.|\b(?:etc|Co|Ltd|Inc|Jr|Sr|St|Bros|Bd|Nr|Pt|no|vol|ed|U\.S|U\.S\.S\.R)\.)$")
WORD = re.compile(r"[^\W\d_]+(?:['\u2019][^\W\d_]+)*", re.UNICODE)   # japan's, O'Brien, Nan'yo


TITLE_FIXES = os.path.join(HERE, "title_fixes.tsv")


def title_fixes():
    """{key: corrected title} from title_fixes.tsv - e.g. a statement of responsibility the catalogue
    ran on after the title."""
    d = {}
    if os.path.exists(TITLE_FIXES):
        for line in open(TITLE_FIXES, encoding="utf-8"):
            if line.startswith("#"):
                continue
            p = line.rstrip("\n").split("\t")
            if len(p) >= 2 and p[0].strip():
                d[p[0].strip()] = p[1].strip()
    return d


def trim_stop(title):
    """Drop the full stop the catalogues put at the end of a title, but not one that belongs to an
    abbreviation ('... by W. A.', 'Tokyo, Maruzen Co.')."""
    t = title.rstrip()
    if t.endswith(".") and not t.endswith("..") and not ABBREV_END.search(t):
        t = t[:-1].rstrip()   # "..." marks words left out by the cataloguer and stays
    return t


def titlecase_en(title):
    """Sentence case -> title case, leaving alone anything that already carries its own capitals
    (acronyms, MacArthur, Nan'yō) and the small words inside the title."""
    out, start = [], True
    for tok in re.split(r"(\s+)", title):
        if not tok.strip():
            out.append(tok)
            continue
        if not WORD.search(tok):
            out.append(tok)
            continue
        def fix(word, first):
            if word.isupper():
                return word                                   # KBS, NHK, II, the A and D of A.D.
            if any(c.isupper() for c in word[1:]):
                return word                                   # McCoy, MacArthur, O'Brien
            if "-" in word:
                return "-".join(fix(p, first or i == 0) for i, p in enumerate(word.split("-")))
            if not first and word.lower() in SMALL_WORDS:
                return word.lower()
            return word[:1].upper() + word[1:]                # japan's -> Japan's (the tail is untouched)
        # rebuild the token word by word, so that "(japan)" and "japan," keep their punctuation
        parts, pos, first = [], 0, start
        for mm in WORD.finditer(tok):
            parts.append(tok[pos:mm.start()])
            parts.append(fix(mm.group(0), first))
            first = False
            pos = mm.end()
        parts.append(tok[pos:])
        out.append("".join(parts))
        start = bool(re.search(r"[:;?!]\s*$", tok))           # a new clause starts afresh ("." is usually an abbreviation)
    t = "".join(out)
    return t[:1].upper() + t[1:] if t else t


def write_db(path, rows, keep_annotations):
    """Write one SQLite file. The published copy leaves out the bibliographers' own annotations."""
    if os.path.exists(path):
        os.remove(path)
    con = sqlite3.connect(path)
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
            links_access TEXT NOT NULL,
            links_checked TEXT NOT NULL,
            language TEXT NOT NULL
        );
        CREATE VIRTUAL TABLE books_fts USING fts5(
            author, title, other, content='books', content_rowid='id',
            tokenize="unicode61 remove_diacritics 2");
    """)
    out = [r if keep_annotations else (r[:7] + [strip_annotations(r[7])] + r[8:]) for r in rows]
    fx = language_fixes()
    out = [r + [fx.get(language_key(r[0], r[1], r[2])) or guess_language(r[1], r[7])[0]] for r in out]
    tf = title_fixes()
    for r in out:                                             # display form of the title: see the note above
        r[1] = tf.get(language_key(r[0], r[1], r[2]), r[1])
        r[1] = trim_stop(titlecase_en(r[1]) if r[-1] == "English" else r[1])
    con.executemany("INSERT INTO books(author,title,year,year_num,edition,volume,links,other,source,type,"
                    "access,links_access,links_checked,language) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", out)
    if not keep_annotations:   # the working copy keeps everything; the published one leaves these out
        con.execute("DELETE FROM books WHERE language IN (%s)" % ",".join("?" * len(HIDE_LANGUAGES)),
                    sorted(HIDE_LANGUAGES))
        con.execute("DELETE FROM books WHERE year_num IS NOT NULL AND (year_num > ? OR year_num < 1850)",
                    (LAST_YEAR,))
    con.execute("INSERT INTO books_fts(rowid,author,title,other) SELECT id,author,title,other FROM books")
    con.executescript("""
        CREATE INDEX idx_author ON books(author COLLATE NOCASE);
        CREATE INDEX idx_title ON books(title COLLATE NOCASE);
        CREATE INDEX idx_year ON books(year_num);
        CREATE INDEX idx_type ON books(type);
        CREATE INDEX idx_access ON books(access);
        CREATE INDEX idx_language ON books(language);
    """)
    con.commit()
    return con


if __name__ == "__main__":
    recs, cache = load_records(), load_cache()

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
            ys = [y for y in years(r) if 1850 <= y <= LAST_YEAR] or years(r)
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
    checked = Z.apply(rows)  # hand-checked links from the Zotero collection: always kept, listed first
    checked.update(N.apply(rows, LAST_YEAR))  # National Diet Library items supplied by the user
    # Dower & George comes last, so that the ids of every row above it stay where they are (the
    # language fixes and the Gallica / Online Books results are keyed to them).
    n_dup, n_new, _ = D.apply(rows)
    print(f"Dower & George: {n_dup} entries already in the database, {n_new} added")
    x_checked, x_att, x_new = X.apply(rows)   # archive.org items picked by hand
    print(f"Hand-picked archive.org items: {x_att} attached to an entry already there, {x_new} added")
    checked.update(x_checked)
    l_checked, l_att, l_new = LIB.apply(rows)  # items from other libraries, also picked by hand
    print(f"Hand-picked library items: {l_att} attached to an entry already there, {l_new} added")
    checked.update(l_checked)
    a_dup, a_new = ASJ.apply(rows)            # the Asiatic Society of Japan's 1888 library catalogue
    print(f"Asiatic Society of Japan (1888): {a_dup} entries already in the database, {a_new} added")
    n_later = sum(1 for x in rows if x[3] is not None and x[3] > LAST_YEAR)
    print(f"dated later than {LAST_YEAR} (kept in the working copy, left out of the published one): {n_later}")
    # Gallica copies for the French entries. Keyed by row position, so it has to come after the
    # filtering above and before the access flags below.
    n_gal, n_galed, moved = GAL.apply(rows)
    print(f"Gallica: {n_gal} copies linked, {n_galed} other editions noted"
          + (f", {len(moved)} skipped because the row had moved: {moved[:8]}" if moved else ""))
    n_ob, n_obed, moved_ob = OB.apply(rows)
    print(f"Online Books: {n_ob} copies linked, {n_obed} other editions noted"
          + (f", {len(moved_ob)} skipped because the row had moved: {moved_ob[:8]}" if moved_ob else ""))
    acc = load_access()
    rows = [with_access(list(x), acc, checked) for x in rows]
    write_db(DB_FULL, rows, keep_annotations=True)
    con = write_db(DB, rows, keep_annotations=False)
    q = lambda s: con.execute(s).fetchone()[0]
    print("Union Catalog rows", n_uc, "| of which also in a later bibliography", len(attach), "| new rows", len(new))
    for t, n in con.execute("SELECT source, count(*) FROM books GROUP BY source ORDER BY 2 DESC"):
        print(f"  {n:5d}  {t}")
    print("languages:", ", ".join(f"{l} {n}" for l, n in con.execute(
        "SELECT language, count(*) FROM books GROUP BY language ORDER BY 2 DESC LIMIT 8")))
    for a, n in con.execute("SELECT access, count(*) FROM books WHERE links<>'' GROUP BY access ORDER BY 2 DESC"):
        print(f"  access {a or '-':10s} {n}")
    print("rows", q("SELECT count(*) FROM books"), "| with links", q("SELECT count(*) FROM books WHERE links<>''"),
          "| undated", q("SELECT count(*) FROM books WHERE year_num IS NULL"),
          "| with edition", q("SELECT count(*) FROM books WHERE edition<>''"),
          "| with volume", q("SELECT count(*) FROM books WHERE volume<>''"))
    con.execute("VACUUM")
    con.close()
