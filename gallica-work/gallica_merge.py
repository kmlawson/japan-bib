#!/usr/bin/env python3
"""Put the accepted Gallica copies into the rows build_db.py is about to write.

gallica.jsonl records the entry each search was made for by its id in list.sqlite at the time, but ids
move whenever rows are added or the date cut changes, so the link is attached by what the entry IS:
author, title and year, folded to letters and digits (language.key). An entry that no longer answers
to that description simply keeps no link, rather than one belonging to another book.

Gallica's digitisations are scans of public-domain works, freely readable, so a link counts as `open`.
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "union-catalog-work"))
from gallica_score import accepted  # noqa: E402
from language import key as rowkey  # noqa: E402

SRC = os.path.join(HERE, "gallica.jsonl")


def searched():
    """{id of the entry at search time: its key}."""
    out = {}
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
    links, other = accepted()
    keys, idx, n_link, n_other, lost = searched(), index(rows), 0, 0, []
    for rid, (ark, year) in list(links.items()) + [(k, v) for k, v in other.items()]:
        if not ark.startswith("http"):
            continue      # a partner institution's bare ark, which does not resolve on gallica.bnf.fr
        hits = idx.get(keys.get(rid, ""), [])
        if not hits:
            lost.append(rid)
            continue
        for i in hits:    # the same work is sometimes entered twice; both get the copy
            if rid in links:
                have = rows[i][6].split("\n") if rows[i][6] else []
                if ark not in have:
                    rows[i][6] = "\n".join(have + [ark])
                    n_link += 1
            else:
                note = f"Gallica, other editions: {ark}" + (f" ({year})" if year else "")
                if "Gallica, other editions" not in rows[i][7]:
                    rows[i][7] += " | " + note
                    n_other += 1
    return n_link, n_other, lost


if __name__ == "__main__":
    links, other = accepted()
    print(f"{len(links)} copies to link, {len(other)} other editions to note")
