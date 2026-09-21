#!/usr/bin/env python3
"""Add the items from the National Library of Norway, Europeana, Alvin and HathiTrust (lib.jsonl).

These are copies the compiler chose and checked, so the link is always kept and counts as checked by
hand. An item whose work is already in the database only adds its link; anything else becomes a row.

The catalogue record is used as it stands, except for the corrections in FIX below, each of which says
why it is there. Nothing is invented: where a catalogue is silent or plainly wrong, the field is left
empty and the doubt is written into the note.

HathiTrust answers automated requests with 403, so nothing can be fetched from it: such a record is
written into lib.jsonl by hand, marked "by_hand", with the compiler's own description of the book and
his word that this copy can be read outside the United States.

    lib_merge.py        what would be added or attached
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "next-bib-work"))
sys.path.insert(0, os.path.join(HERE, "..", "union-catalog-work"))
import merge as M  # noqa: E402

SRC = "KML Additions"
DATA = os.path.join(HERE, "lib.jsonl")
HOLDER = {"NB": "National Library of Norway", "EU": "Europeana", "ALVIN": "Alvin (Uppsala University Library)",
          "H": "HathiTrust"}
# second titles in the Norwegian MODS records that are not series statements
NOT_A_SERIES = {"Norbok"}
JUNK_EXTENT = re.compile(r"^[\d.]+\s*x\s*cm\.?$", re.I)

FIX = {
    "https://www.nb.no/items/18073585b5fc57b9b1391d3628280606": {
        "author": "",
        "note": 'The catalogue names the author only as "N" (lyricist), so the heading is left blank.',
    },
    "https://www.nb.no/items/7de997986b2049f10ab67cc00551ee6f": {
        "author": "",
        "year": "n.d.", "year_start": None,
        "note": "The catalogue dates it 1855 (estimated range 1855-1899), but the song is about the "
                "Russo-Japanese war of 1904-05, so that date cannot be right; left undated here. "
                "Printed in fraktur; the catalogue names no author.",
    },
}


def value(r, k, default=""):
    return FIX.get(r["source_url"], {}).get(k, r.get(k) or default)


def load():
    out = []
    for line in open(DATA, encoding="utf-8"):
        r = json.loads(line)
        if r.get("error"):
            print("skipped (fetch failed):", r["source_url"], r["error"], file=sys.stderr)
            continue
        fix = FIX.get(r["source_url"], {})
        year = fix.get("year", (r.get("year") or "").strip() or "n.d.")
        m = re.search(r"(1[5-9]\d\d|20\d\d)", year)
        rec = {
            "author": value(r, "author"),
            "title": re.sub(r"\s+", " ", value(r, "title")).strip(),
            "year": year,
            "year_start": fix["year_start"] if "year_start" in fix else (int(m.group(1)) if m else None),
            "edition": "", "extent": "" if JUNK_EXTENT.match(r.get("extent") or "") else (r.get("extent") or ""),
            "place": "" if r["host"] == "EU" else (r.get("place") or ""),   # Europeana's place is a subject, not an imprint
            "publisher": r.get("publisher") or "",
            "series": "" if (r.get("series") or "") in NOT_A_SERIES else (r.get("series") or ""),
            "container": "", "type": "book", "section": "", "annotation": "",
            "language": r.get("language") or "",
            "title_en": r.get("title_en") or "",
            "host": r["host"], "url": r["url"], "rights": r.get("rights") or "",
            "note": fix.get("note", ""), "cat_note": r.get("notes") or "",
            "src": SRC, "also": [],
        }
        out.append(rec)
    return out


def other(r):
    parts = []
    imprint = ", ".join(x for x in (r["place"], r["publisher"]) if x)
    if imprint:
        parts.append("Imprint: " + imprint)
    if r["extent"]:
        parts.append("Extent: " + r["extent"])
    if r["series"]:
        parts.append("Also catalogued under the title: " + r["series"])
    if r["language"]:
        parts.append("Language: " + r["language"])
    if r["title_en"] and r["title_en"] != r["title"]:
        parts.append("Title in English (Europeana's own translation): " + r["title_en"])
    parts.append(f"{HOLDER.get(r['host'], r['host'])}, chosen by hand")
    if r["note"]:
        parts.append("Note: " + r["note"])
    if r["cat_note"]:
        parts.append("Catalogue note: " + r["cat_note"][:300])
    return " | ".join(parts)


def row_of(r):
    return [r["author"], r["title"], r["year"], r["year_start"], "", "", r["url"], other(r), SRC, r["type"]]


def apply(rows):
    """Attach or append in place; returns ({url: access}, attached, added)."""
    idx = M.Index()
    for i, row in enumerate(rows):
        kind = "book" if row[9] in ("book", "periodical") else "part"
        idx.add(M.item(M.sur(row[0]), row[1], row[3], kind, ("row", i)))
    checked, n_att, added = {}, 0, []
    for r in load():
        checked[r["url"]] = "open"
        here = [i for i, row in enumerate(rows) if r["url"] in (row[6] or "")]
        if not here:
            k = M.kind_of(r)
            hit = idx.find(M.sur(r["author"]), M.tkey(r["title"]), M.norm(r["title"]), r["year_start"], k)
            if hit is not None and hit["ref"][0] == "row":
                here = [hit["ref"][1]]
        if here:
            i = here[0]
            if SRC not in rows[i][8]:
                rows[i][8] += "; " + SRC
            if r["url"] not in (rows[i][6] or ""):
                rows[i][6] = "\n".join(([rows[i][6]] if rows[i][6] else []) + [r["url"]])
            rows[i][7] += f" | {HOLDER.get(r['host'], r['host'])}: {r['url']}"
            n_att += 1
        else:
            added.append(row_of(r))
    rows += added
    return checked, n_att, len(added)


def language_lines():
    """The language of each item as the compiler gave it, in the form language_fixes.tsv wants."""
    from language import key
    out = []
    for r in load():
        if r["language"]:
            out.append(f"{key(r['author'], r['title'], r['year'])}\t{r['language']}\t{r['title'][:60]}")
    return out


if __name__ == "__main__":
    import sqlite3
    con = sqlite3.connect(os.path.join(HERE, "..", "union-catalog-work", "list-full.sqlite"))
    rows = [list(x) for x in con.execute(
        "SELECT author,title,year,year_num,edition,volume,links,other,source,type FROM books ORDER BY id")]
    con.close()
    checked, n_att, n_new = apply(rows)
    print(f"{len(load())} items: {n_att} already in the database, {n_new} added")
    if "--languages" in sys.argv:
        print("\n".join(language_lines()))
