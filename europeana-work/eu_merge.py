#!/usr/bin/env python3
"""Put the accepted Europeana copies into the rows build_db.py is about to write.

As for Gallica (gallica-work/gallica_merge.py): eu.jsonl records the entry each search was made for by
its id at the time, but ids move, so the link is attached by what the entry IS (author, title and year
folded to letters and digits). Europeana aggregates digitised public-domain books from the national
libraries, so a link counts as `open`.
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "union-catalog-work"))
from eu_score import accepted, SRC  # noqa: E402
from language import key as rowkey  # noqa: E402


def searched():
    out = {}
    if os.path.exists(SRC):
        for line in open(SRC, encoding="utf-8"):
            r = json.loads(line)
            out[r["id"]] = rowkey(r.get("author"), r.get("title"), r.get("year"))
    return out


def index(rows):
    idx = {}
    for i, row in enumerate(rows):
        idx.setdefault(rowkey(row[0], row[1], row[2]), []).append(i)
    return idx


def apply(rows):
    """Add the links in place; returns (linked, other editions noted, entries no longer in the rows)."""
    if not os.path.exists(SRC):
        return 0, 0, []
    links, other = accepted()
    keys, idx, n_link, n_other, lost = searched(), index(rows), 0, 0, []
    for rid, (url, year) in list(links.items()) + list(other.items()):
        hits = idx.get(keys.get(rid, ""), [])
        if not hits:
            lost.append(rid)
            continue
        for i in hits:
            if rid in links:
                have = rows[i][6].split("\n") if rows[i][6] else []
                if url not in have:
                    rows[i][6] = "\n".join(have + [url])
                    n_link += 1
            else:
                note = f"Europeana, other editions: {url}" + (f" ({year})" if year else "")
                if "Europeana, other editions" not in rows[i][7]:
                    rows[i][7] += " | " + note
                    n_other += 1
    return n_link, n_other, lost


if __name__ == "__main__":
    links, other = accepted()
    print(f"{len(links)} copies to link, {len(other)} other editions to note")
