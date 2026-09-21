#!/usr/bin/env python3
"""Attach the copies found through Hispana to the rows build_db.py is about to write.

What Hispana gives is a record and a link onward; the copy itself sits at the library that digitised
it, usually the Biblioteca Digital Hispánica. hispana_links.py follows each record that agrees on date
and writes down where it really leads, and hispana_decisions.tsv holds the verdict on each of those,
made by hand - the aggregator's own rights statement is no help, since it marks an 1868 book "In
Copyright".

A link is attached to the entry it belongs to by what the entry is - author, title and year folded to
letters and digits (language.key) - not by the row id it had when the search was made.

The Biblioteca Nacional answers no script - curl, a full set of browser headers and headless Chrome all
get 403 from its Cloudflare - so this cannot check that a viewer really opens. Opened in an ordinary
Chrome window the same links resolve to BNE Digital and the copy is there, which is how they were
checked. The old bdh-rd.bne.es/viewer.vm links redirect to bnedigital.bne.es/bd/card, so the newer
form is what is stored.
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "union-catalog-work"))
from language import key as rowkey  # noqa: E402

LINKS = os.path.join(HERE, "hispana_links.jsonl")
DEC = os.path.join(HERE, "hispana_decisions.tsv")


def decisions():
    """{(entry id, url): yes|no} - the verdicts made by hand."""
    d = {}
    if os.path.exists(DEC):
        for line in open(DEC, encoding="utf-8"):
            if line.startswith("#"):
                continue
            p = line.rstrip("\n").split("\t")
            if len(p) >= 3 and p[0].isdigit():
                d[(int(p[0]), p[1])] = p[2].strip().lower()
    return d


def accepted():
    """[(key, url, institution)] for the copies to attach."""
    dec, out = decisions(), []
    if not os.path.exists(LINKS):
        return out
    for line in open(LINKS, encoding="utf-8"):
        r = json.loads(line)
        if r.get("error") or not r.get("url"):
            continue
        if dec.get((r["id"], r["url"])) != "yes":
            continue
        out.append((rowkey(r.get("author"), r.get("title"), r.get("year")), r["url"], r.get("institution", "")))
    return out


def apply(rows):
    """Add the links in place; returns (linked, entries no longer in the rows)."""
    idx = {}
    for i, row in enumerate(rows):
        idx.setdefault(rowkey(row[0], row[1], row[2]), []).append(i)
    n, lost = 0, []
    for key, url, inst in accepted():
        hits = idx.get(key, [])
        if not hits:
            lost.append(url)
            continue
        for i in hits:
            have = rows[i][6].split("\n") if rows[i][6] else []
            if url not in have:
                rows[i][6] = "\n".join(have + [url])
                rows[i][7] += f" | Copy at {inst}, found through Hispana: {url}"
                n += 1
    return n, lost


if __name__ == "__main__":
    for key, url, inst in accepted():
        print(f"{inst}: {url}")
    print(len(accepted()), "copies to attach")
