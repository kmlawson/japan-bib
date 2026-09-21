#!/usr/bin/env python3
"""Put the BNE Digital records read by Chrome (bne_cards.jsonl) into the database.

Each record gives a title, an author with life dates, an imprint and a year; the link kept is the
reader, `/bd/es/viewer?id=<uuid>&page=1`, which is what opens the scan. A work already in the database
only gains the link and a note; anything else becomes a row of its own, with source SRC.

Everything here was chosen by the compiler, so the links count as checked by hand and as freely
readable - the Biblioteca Nacional digitises what is out of copyright and serves it to anyone.

    bne_merge.py        what would be attached or added
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "next-bib-work"))
sys.path.insert(0, os.path.join(HERE, "..", "union-catalog-work"))
import merge as M  # noqa: E402

SRC = "Biblioteca Nacional de España"
DATA = os.path.join(HERE, "bne_cards.jsonl")
DATES = re.compile(r"\s*\((?:[bd]\.\s*)?\d{3,4}\??(?:-\d{0,4}\??)?\)\s*$")


NO_PLACE = re.compile(r"^\[?s\.\s*l\.?\]?$", re.I)      # [S.l.]: no place given
NO_PUB = re.compile(r"^\[?s\.\s*n\.?\]?$", re.I)        # [s.n.]: no publisher given


def imprint_of(text):
    """The imprint as the catalogue prints it, cut into place and publisher.

    'Madrid : [s.n.] (Imp. Hispánica)'                      -> Madrid, Imp. Hispánica
    '[S.l.] : [s.n.] (Madrid : Imp. del Asilo de Huérfanos)' -> Madrid, Imp. del Asilo de Huérfanos
    """
    t = (text or "").strip()
    if not t:
        return "", ""
    inner = re.search(r"\(([^)]+)\)", t)
    outer = re.sub(r"\s*\([^)]*\)", "", t).strip()
    place, _, pub = outer.partition(":")
    place, pub = place.strip(" ,.[]"), pub.strip(" ,.[]")
    if NO_PLACE.match(place):
        place = ""
    if NO_PUB.match(pub):
        pub = ""
    if inner and (not place or not pub):            # the printer in brackets stands in for both
        ip, _, ipub = inner.group(1).partition(":")
        if not pub:
            pub = (ipub or ip).strip(" ,.")
        if not place and ipub:
            place = ip.strip(" ,.")
    return place, pub


def load():
    out = []
    for line in open(DATA, encoding="utf-8"):
        r = json.loads(line)
        f = r.get("fields") or {}
        if r.get("error") or not f.get("Título"):
            continue
        title = re.split(r"\s+/\s+", f["Título"])[0].strip(" .")
        author = DATES.sub("", (f.get("Autoría") or f.get("Autor") or "").split("|")[0]).strip()
        m = re.search(r"(1[5-9]\d\d|20\d\d)", f.get("Fecha") or "")
        y = int(m.group(1)) if m else None
        head = f.get("_head") or ""
        pub_line = ""
        mm = re.search(r"Publicación, distribución, etc\. / ([^/]+)", head)
        if mm:
            pub_line = mm.group(1).strip()
        place, publisher = imprint_of(pub_line)
        out.append({
            "author": author, "title": title, "year": str(y) if y else "n.d.", "year_start": y,
            "edition": "", "place": place, "publisher": publisher,
            "extent": (f.get("Descripción física") or "").strip(), "container": "", "type": "book",
            "section": "", "annotation": "", "note": "", "language": "Spanish",
            "url": r["viewer"], "card": r["card"], "uuid": r["uuid"],
            "signature": (f.get("Signatura") or "").strip(), "src": SRC, "also": [],
        })
    return out


def where(r):
    return f"{SRC}, BNE Digital {r['uuid']}" + (f" (signatura {r['signature']})" if r["signature"] else "")


def row_of(r):
    parts = []
    imprint = ", ".join(x for x in (r["place"], r["publisher"]) if x)
    if imprint:
        parts.append("Imprint: " + imprint)
    if r["extent"]:
        parts.append("Extent: " + r["extent"])
    parts.append("Language: Spanish")
    parts.append(where(r))
    return [r["author"], r["title"], r["year"], r["year_start"], "", "", r["url"], " | ".join(parts), SRC, "book"]


def apply(rows):
    """Attach or append in place; returns ({url: access}, attached, added)."""
    idx = M.Index()
    for i, row in enumerate(rows):
        kind = "book" if row[9] in ("book", "periodical") else "part"
        idx.add(M.item(M.sur(row[0]), row[1], row[3], kind, ("row", i)))
    checked, n_att, added = {}, 0, []
    for r in load():
        checked[r["url"]] = "open"
        here = [i for i, row in enumerate(rows) if r["uuid"] in (row[6] or "")]
        if not here:
            tk, full, su = M.tkey(r["title"]), M.norm(r["title"]), M.sur(r["author"])
            hit = idx.find(su, tk, full, r["year_start"], "book")
            if hit is None and len(tk) >= 18 and r["year_start"]:
                hit = idx.exact(tk, full, r["year_start"], "book")
            if hit is not None and hit["ref"][0] == "row":
                here = [hit["ref"][1]]
        if here:
            i = here[0]
            if SRC not in rows[i][8]:
                rows[i][8] += "; " + SRC
            if r["url"] not in (rows[i][6] or ""):
                rows[i][6] = "\n".join(([rows[i][6]] if rows[i][6] else []) + [r["url"]])
            if r["uuid"] not in rows[i][7]:
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
    recs = load()
    checked, n_att, n_new = apply(rows)
    print(f"{len(recs)} BNE records: {n_att} already in the database, {n_new} added")
    for r in recs:
        print(f"  {r['year']} | {(r['author'] or '-')[:26]:26s} | {r['title'][:52]:52s} | {r['place']}, {r['publisher']}")
