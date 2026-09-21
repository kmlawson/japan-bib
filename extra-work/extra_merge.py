#!/usr/bin/env python3
"""Add the archive.org items picked by hand (ids.txt, metadata in extra.jsonl) to the database.

These are copies the compiler found and checked, so the link is always kept and counts as checked by hand,
like the ones from the Zotero collection. An item whose work is already in the database only adds its
link and its source name; anything else becomes a row of its own.

The archive.org metadata is used as it stands, except for the tidying in FIX below (a title that
repeats the year or the publisher, a date the uploader left out but stated in the description, an
author behind a pen name). Each row says which archive.org item it came from.

    extra_merge.py      what would be added or attached
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "next-bib-work"))
sys.path.insert(0, os.path.join(HERE, "..", "union-catalog-work"))
import merge as M  # noqa: E402

SRC = "KML Additions"
DATA = os.path.join(HERE, "extra.jsonl")
LANG = {"eng": "English", "ger": "German", "spa": "Spanish", "fre": "French", "jpn": ""}

# identifier -> fields to override or add, with the reason
FIX = {
    "notes-on-japanese-cuisine-jtb-1946": {
        "title": "Notes on Japanese Cuisine",
        "publisher": "Japan Travel Bureau",
        "note": 'Printed under the pen name "Eisaku Waseda"; the archive.org record identifies the author as '
                "Senkichirō Katsumata, emeritus professor at Waseda University. Possibly a second edition of a "
                "work of the same title published by the Japan Travel Bureau in 1935.",
    },
    "how-to-see-kyoto-and-nara": {
        "year": "after 1955", "year_start": None,
        "note": "No date printed; the latest date in the work is 1955, so it was published after that year.",
    },
    "about-japan-1920-1928": {
        "title": "About Japan", "year": "1920-1928", "year_start": 1920, "type": "periodical",
        "publisher": "Japan Society, New York",
        "note": "A bound run of the Japan Society's bulletin, 1920-1928.",
    },
    "maptalk-1946.3": {"year": "1946", "year_start": 1946, "type": "periodical",
                       "note": "The issue of 20 March 1946 of a magazine published by the Armed Forces "
                               "Information & Education Section during the occupation of Japan."},
    "what-is-japan-fighting-for-1937": {"title": "What Is Japan Fighting For: The Truth About the Sino-Japanese Conflict"},
    "japan-the-pocket-guide-1946": {"title": "Japan: The Pocket Guide"},
    "japan-the-pocket-guide-1947": {"title": "Japan: The Pocket Guide"},
    "japan-the-pocket-guide-1953": {"title": "Japan: The Pocket Guide"},
    "nyk-feb-1937": {"title": "N.Y.K. Trans-Pacific Sailings, February 1937"},
    "tokyo-joe": {"note": "Cartoons by Ed Doughty published in Stars and Stripes, 1945-1946. The archive.org "
                          "record notes that they contain derogatory and stereotyped depictions of Japanese "
                          "people, and of Japanese women in particular."},
}
CORP = re.compile(r"\b(society|association|bureau|company|line|army|navy|railway|forces|government|"
                  r"ministry|office|department|scholar|mail)\b", re.I)


def author(creator):
    """archive.org creators are free text: 'Hume, Bill; Annarino, John', 'Hermann Lufft', a body's name."""
    c = (creator or "").strip()
    if not c:
        return ""
    if CORP.search(c) or "," in c:
        return re.sub(r"\s+", " ", c)
    toks = c.split()
    return f"{toks[-1]}, {' '.join(toks[:-1])}" if 2 <= len(toks) <= 4 else c


def load():
    out = []
    for line in open(DATA, encoding="utf-8"):
        md = json.loads(line)
        fix = FIX.get(md["identifier"], {})
        date = str(md.get("date") or md.get("year") or "")
        m = re.search(r"(1[6-9]\d\d|20\d\d)", date)
        r = {
            "author": fix.get("author", author(md.get("creator"))),
            "title": fix.get("title", re.sub(r"\s+", " ", str(md.get("title") or "")).strip()),
            "year": fix.get("year", m.group(1) if m else "n.d."),
            "year_start": fix["year_start"] if "year_start" in fix else (int(m.group(1)) if m else None),
            "edition": "", "place": "", "publisher": fix.get("publisher", md.get("publisher") or ""),
            "extent": f"{md['imagecount']} images" if md.get("imagecount") else "",
            "container": "", "type": fix.get("type", "book"),
            "section": "", "annotation": "", "note": fix.get("note", ""),
            "language": LANG.get(str(md.get("language") or "").lower(), ""),
            "identifier": md["identifier"], "src": SRC, "also": [],
        }
        r["url"] = "https://archive.org/details/" + r["identifier"]
        out.append(r)
    return out


def where(r):
    return f"archive.org item {r['identifier']}, chosen by hand"


def row_of(r):
    parts = []
    if r["type"] != "book":
        parts.append("Type: " + r["type"])
    if r["publisher"]:
        parts.append("Imprint: " + r["publisher"])
    if r["extent"]:
        parts.append("Extent: " + r["extent"])
    if r["language"]:
        parts.append("Language: " + r["language"])
    parts.append(where(r))
    if r["note"]:
        parts.append("Note: " + r["note"])
    return [r["author"], r["title"], r["year"], r["year_start"], "", "", r["url"], " | ".join(parts), SRC, r["type"]]


def apply(rows):
    """Attach or append in place; returns ({url: access} for the hand-checked links, attached, added)."""
    idx = M.Index()
    for i, row in enumerate(rows):
        kind = "book" if row[9] in ("book", "periodical") else "part"
        idx.add(M.item(M.sur(row[0]), row[1], row[3], kind, ("row", i)))
    checked, n_att, added = {}, 0, []
    for r in load():
        checked[r["url"]] = "open"
        here = [i for i, row in enumerate(rows) if r["identifier"] in (row[6] or "")]
        if not here:
            k = M.kind_of(r)
            hit = idx.find(M.sur(r["author"]), M.tkey(r["title"]), M.norm(r["title"]), r["year_start"], k)
            if hit is None and len(M.tkey(r["title"])) >= 20 and r["year_start"] is not None:
                hit = idx.exact(M.tkey(r["title"]), M.norm(r["title"]), r["year_start"], k)
            if hit is not None and hit["ref"][0] == "row":
                here = [hit["ref"][1]]
        if here:
            i = here[0]
            if SRC not in rows[i][8]:
                rows[i][8] += "; " + SRC
            if r["url"] not in (rows[i][6] or ""):
                rows[i][6] = "\n".join(([rows[i][6]] if rows[i][6] else []) + [r["url"]])
            if where(r) not in rows[i][7]:
                rows[i][7] += " | " + where(r)
            n_att += 1
        else:
            added.append(row_of(r))
    rows += added
    return checked, n_att, len(added)


if __name__ == "__main__":
    import sqlite3
    con = sqlite3.connect(os.path.join(HERE, "..", "union-catalog-work", "list-full.sqlite"))
    rows = [list(x) for x in con.execute(
        "SELECT author,title,year,year_num,edition,volume,links,other,source,type FROM books ORDER BY id")]
    con.close()
    checked, n_att, n_new = apply(rows)
    print(f"{len(load())} hand-picked items: {n_att} already in the database, {n_new} added")
