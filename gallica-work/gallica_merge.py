#!/usr/bin/env python3
"""Put the accepted Gallica copies into the rows build_db.py is about to write.

gallica.jsonl records the entry each search was made for by its id in list.sqlite, that is by its
position in the row list, so this runs after the rows are in their final order and before the access
flags are worked out. Every row is checked against the title recorded with the search: if they differ
the row has moved and the link is left out rather than attached to the wrong book.

Gallica's digitisations are scans of public-domain works, freely readable, so a link counts as `open`.
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from gallica_score import accepted  # noqa: E402

SRC = os.path.join(HERE, "gallica.jsonl")


def titles():
    return {json.loads(l)["id"]: json.loads(l)["title"] for l in open(SRC, encoding="utf-8")}


def apply(rows):
    """Add the links in place; returns (linked, other editions noted, rows that had moved)."""
    links, other = accepted()
    ttl, n_link, n_other, moved = titles(), 0, 0, []
    for rid, (ark, year) in list(links.items()) + [(k, v) for k, v in other.items()]:
        if not ark.startswith("http"):
            continue      # a partner institution's bare ark, which does not resolve on gallica.bnf.fr
        i = rid - 1
        if not (0 <= i < len(rows)) or rows[i][1].strip() != (ttl.get(rid) or "").strip():
            moved.append(rid)
            continue
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
    return n_link, n_other, moved


if __name__ == "__main__":
    links, other = accepted()
    print(f"{len(links)} copies to link, {len(other)} other editions to note")
