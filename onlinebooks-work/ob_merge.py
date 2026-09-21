#!/usr/bin/env python3
"""Put the accepted Online Books Page copies into the rows build_db.py is about to write.

Like the Gallica merge, the copy is attached by what the entry is - author, title and year folded to
letters and digits (language.key) - rather than by the row id it had when the search was made, because
ids move whenever rows are added or the date cut changes.

The Online Books Page lists copies that anyone may read, so they count as `open` (an archive.org
copy is still classified by the usual access check).
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "union-catalog-work"))
from ob_score import accepted  # noqa: E402
from language import key as rowkey  # noqa: E402

SRC = os.path.join(HERE, "ob.jsonl")


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
    """Add the links in place; returns (rows linked, other editions noted, entries no longer in the rows)."""
    links, other = accepted()
    keys, idx, n_link, n_other, lost = searched(), index(rows), 0, 0, []
    for rid in sorted(set(links) | set(other)):
        hits = idx.get(keys.get(rid, ""), [])
        if not hits:
            lost.append(rid)
            continue
        for i in hits:
            if rid in links:
                us, _, _ = links[rid]
                have = rows[i][6].split("\n") if rows[i][6] else []
                add = [u for u in us if u not in have]
                if add:
                    rows[i][6] = "\n".join(have + add)
                    n_link += 1
            else:
                us, title, year = other[rid]
                if "Online Books, other editions" not in rows[i][7]:
                    rows[i][7] += " | Online Books, other editions: " + "; ".join(us) + (f" ({year})" if year else "")
                    n_other += 1
    return n_link, n_other, lost


if __name__ == "__main__":
    links, other = accepted()
    print(f"{len(links)} copies to link, {len(other)} other editions to note")
