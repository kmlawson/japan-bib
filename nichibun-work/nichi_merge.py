#!/usr/bin/env python3
"""Merge the Nichibunken catalogue records (nichi.jsonl) into the database.

The catalogue gives, for each work, an author with life dates, a short title, the year, the title page
as printed, the imprint line and the collation. Place and publisher are taken from the imprint line -
"LONDON: CHAPMAN AND HALL, 193, PICCADILLY. 1869." gives London and Chapman and Hall - and the street
address is dropped. Characters the site serves as images ({g0nae} and the like) are put back from
gaiji.tsv, which was read off those images by eye.

The catalogue lists the same work more than once when Nichibunken holds more than one copy; those fold
together here. Duplicates of works already in the database are found as for the other sources (same
surname, matching title proper, years within three) and only add a note.

    nichi_merge.py             what would be merged and what would be added
    nichi_merge.py --todo      the new books that still need an archive.org lookup
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "next-bib-work"))
sys.path.insert(0, os.path.join(HERE, "..", "union-catalog-work"))
import merge as M  # noqa: E402

SRC = "Nichibunken catalogue"
DATA = os.path.join(HERE, "nichi.jsonl")
GAIJI = os.path.join(HERE, "gaiji.tsv")
CACHE6 = os.path.join(HERE, "ia_cache6.jsonl")
FIRST_YEAR, LAST_YEAR = 1850, 1900
DATES = re.compile(r"\s*\((?:[bd]\.\s*)?\d{3,4}(?:\?)?(?:-\d{0,4}\??)?\)\s*$")
ROMAN = re.compile(r"^M+\.?D?C{0,4}\.?L?X{0,4}\.?I{0,4}V?\.?X?\.?$", re.I)


# The codes are systematic: g0n + <mark><letter>, the letter's case being the letter's case. The marks
# were read off the images by eye (see gaiji.tsv); this builds the rest of the alphabet from them, so
# that É and è are decoded as surely as é.
MARKS = {"a": "\u0301", "c": "\u0302", "d": "\u0300", "f": "\u0304", "h": "\u0327",
         "i": "\u0303", "j": "\u0308", "u": "\u0323"}


def gaiji():
    d = {}
    if os.path.exists(GAIJI):
        for line in open(GAIJI, encoding="utf-8"):
            if line.startswith("#"):
                continue
            p = line.rstrip("\n").split("\t")
            if len(p) >= 2:
                d[p[0].strip()] = p[1]
    import unicodedata
    for code in list(d):
        pass
    def built(code):
        m = re.fullmatch(r"g0n([acdfhiju])([A-Za-z])", code)
        if not m:
            return None
        return unicodedata.normalize("NFC", m.group(2) + MARKS[m.group(1)])
    return d, built


G, BUILT = gaiji()
TOKEN = re.compile(r"\{(\w+)\}")


def plain(s):
    """Put the image-served characters back; leave an unknown one visible as {code}."""
    return TOKEN.sub(lambda m: G.get(m.group(1)) or BUILT(m.group(1)) or m.group(0), s or "").strip()


def author_of(r):
    """'Dubois de Jancigny, Adolphe Philibert (1795-1860)' -> without the dates."""
    a = plain(r.get("author"))
    a = DATES.sub("", a)
    a = re.sub(r"\s*\((?:[^()]*)\)\s*$", lambda m: "" if re.search(r"\d", m.group(0)) else m.group(0), a)
    return a.strip(" .,")


# Words that mark a phrase on the title page as something other than the publisher's name. No closing
# \b, so that plurals match; "Frères" and "Fils" are left out, being parts of firm names.
ROLE = re.compile(r"\b(éditeur|editeur|imprimeur|libraire|chevalier|ancien|successeur|"
                  r"rue |street|strasse|straße|piccadilly|avenue|boulevard|"
                  r"printed for|published by|publisher|hofbuchhandlung)", re.I)
SENT = re.compile(r"\.(?=\s+[A-ZÉÈÀÖÜÄ][a-zà-ÿ])")     # a full stop that ends a phrase, not an initial


def imprint_of(r):
    """(place, publisher) from the imprint line. The line is a title page as printed, so it carries a
    street address, a date in roman numerals and often the bookseller's standing - none of which is the
    publisher's name."""
    line = plain(r.get("imprint"))
    if not line:
        return "", ""
    line = re.sub(r"\[\d{4}[^\]]*\]", " ", line)
    line = re.sub(r"\bM\.?D\.?C+[^.,;]*", " ", line)          # M.DCCC.L. and the like
    line = re.sub(r"(?<!\d)\d{4}(?!\d)", " ", line)           # a plain year
    bits = [b.strip(" .,:;") for b in re.split(r"[:,;]", line) if b.strip(" .,:;")]
    if not bits:
        return "", ""
    place = SENT.split(bits[0])[0].strip(" .,")
    rest = []
    for b in bits[1:]:
        b = SENT.split(b)[0].strip(" .,")
        if not b or len(b) < 3 or re.search(r"\d", b) or ROMAN.match(b) or ROLE.search(b):
            continue
        rest.append(b)
        if len(", ".join(rest)) > 40:
            break
    nice = lambda x: re.sub(r"\s+", " ", x).title() if x.isupper() else re.sub(r"\s+", " ", x)
    return nice(place).strip(), nice(", ".join(rest)).strip()


def load():
    """One record per work, copies folded together, only 1850-1900 and only what parsed."""
    out, seen = {}, set()
    for line in open(DATA, encoding="utf-8"):
        r = json.loads(line)
        if r.get("error") or not r.get("title"):
            continue
        year = r.get("year") or str(r.get("list_year") or "")
        m = re.search(r"(1[5-9]\d\d|20\d\d)", year)
        y = int(m.group(1)) if m else None
        if y is None or not (FIRST_YEAR <= y <= LAST_YEAR):
            continue
        author = author_of(r)
        title = re.sub(r"[\s.,]*\b(ca|circa|n\.d)\.?$", "", plain(r.get("title")), flags=re.I).strip(" .,")
        key = (M.sur(author), M.tkey(title), y)
        if key in seen:                                      # another copy of the same book
            continue
        seen.add(key)
        place, publisher = imprint_of(r)
        out[r["id"]] = {
            "author": author, "title": title, "year": str(y), "year_start": y,
            "edition": "", "place": place, "publisher": publisher,
            "extent": plain(r.get("collation")), "container": "", "type": "book",
            "section": "", "annotation": "", "note": "",
            "titlepage": plain(r.get("titlepage"))[:300], "call_number": r.get("call_number", ""),
            "id": r["id"], "src": SRC, "also": [],
        }
    return list(out.values())


def where(r):
    return f"{SRC} {r['id']}" + (f" ({r['call_number']})" if r["call_number"] else "")


def xref(r):
    return f"Also in the {SRC} as {r['id']} ({r['year']})"


def new_row(r, cache):
    links, others = (M.split_matches(r, cache) if M.wants_lookup(r) else (None, []))
    parts = []
    imprint = ", ".join(x for x in (r["place"], r["publisher"]) if x)
    if imprint:
        parts.append("Imprint: " + imprint)
    if r["extent"]:
        parts.append("Extent: " + r["extent"])
    if r["titlepage"]:
        parts.append("Title page: " + r["titlepage"])
    parts.append(where(r))
    if others:
        parts.append("IA other editions: " + "; ".join(
            f"https://archive.org/details/{m['identifier']} ({m['year']})" for m in others[:8]))
    linktxt = None if links is None else "\n".join(f"https://archive.org/details/{m['identifier']}" for m in links)
    return [r["author"], r["title"], r["year"], r["year_start"], "", "", linktxt,
            " | ".join(parts), SRC, "book"]


def split(rows):
    idx = M.Index()
    for i, row in enumerate(rows):
        kind = "book" if row[9] in ("book", "periodical") else "part"
        idx.add(M.item(M.sur(row[0]), row[1], row[3], kind, ("row", i)))
    attach, new = {}, []
    for r in load():
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


def apply(rows):
    attach, new = split(rows)
    for i, rs in attach.items():
        for r in rs:
            if SRC not in rows[i][8]:
                rows[i][8] += "; " + SRC
            rows[i][7] += " | " + xref(r)
    cache = M.load_cache2(CACHE6)
    added = [new_row(r, cache) for r in new]
    rows += added
    return sum(len(v) for v in attach.values()), len(added)


if __name__ == "__main__":
    import sqlite3
    works = load()
    con = sqlite3.connect(os.path.join(HERE, "..", "union-catalog-work", "list-full.sqlite"))
    rows = [list(x) for x in con.execute(
        "SELECT author,title,year,year_num,edition,volume,links,other,source,type FROM books "
        "WHERE source <> ? ORDER BY id", (SRC,))]
    con.close()
    attach, new = split(rows)
    cache = M.load_cache2(CACHE6)
    todo = [r for r in new if M.wants_lookup(r) and M.lkey(r) not in cache]
    if "--todo" in sys.argv:
        for r in todo:
            print(f"{r['author']} | {r['title'][:70]} | {r['year']}")
    if "--new" in sys.argv:
        for r in new:
            print(f"{r['id']} | {r['author'][:28]} | {r['title'][:64]} | {r['year']} | {r['place']}, {r['publisher']}")
    print(f"{len(works)} works 1850-1900 in the catalogue: {sum(len(v) for v in attach.values())} already "
          f"in the database, {len(new)} new ({len(todo)} still to look up on archive.org)")
