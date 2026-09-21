#!/usr/bin/env python3
"""Put the accepted Online Books Page copies into the rows build_db.py is about to write.

Like the Gallica merge, the search recorded each entry by its id in list.sqlite, that is by its
position in the row list, so this runs after the rows are in their final order; each row is checked
against the title that was searched for and skipped if it has moved.

The Online Books Page lists copies that anyone may read, so they count as `open` (an archive.org
copy is still classified by the usual access check).
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from ob_score import accepted  # noqa: E402

SRC = os.path.join(HERE, "ob.jsonl")


def titles():
    return {json.loads(l)["id"]: json.loads(l)["title"] for l in open(SRC, encoding="utf-8")}


def apply(rows):
    """Add the links in place; returns (rows linked, other editions noted, rows that had moved)."""
    links, other = accepted()
    ttl, n_link, n_other, moved = titles(), 0, 0, []
    for rid in sorted(set(links) | set(other)):
        i = rid - 1
        if not (0 <= i < len(rows)) or rows[i][1].strip() != (ttl.get(rid) or "").strip():
            moved.append(rid)
            continue
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
    return n_link, n_other, moved


if __name__ == "__main__":
    links, other = accepted()
    print(f"{len(links)} copies to link, {len(other)} other editions to note")
