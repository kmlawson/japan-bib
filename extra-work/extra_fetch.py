#!/usr/bin/env python3
"""Fetch the archive.org metadata for the items listed by hand in ids.txt.

One plain HTTPS request per item to archive.org's metadata endpoint, spaced out; no credentials and
nothing identifying is sent (the `ia` command-line tool would put the account's access key in the
User-Agent, so it is not used here). The answers are cached in extra.jsonl, so the run is resumable.

    extra_fetch.py [--delay 2]
"""
import argparse, json, os, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
IDS = os.path.join(HERE, "ids.txt")
OUT = os.path.join(HERE, "extra.jsonl")
UA = "japan-bib/1.0 (offline bibliography reconciliation)"
KEEP = ("identifier", "title", "creator", "date", "year", "publisher", "language", "description",
        "subject", "volume", "collection", "access-restricted-item", "imagecount", "mediatype",
        "contributor", "call_number", "isbn", "related-external-id")


def get(ident, tries=4):
    wait = 10
    for n in range(tries):
        try:
            req = urllib.request.Request(f"https://archive.org/metadata/{ident}",
                                         headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except Exception:
            if n == tries - 1:
                raise
            time.sleep(wait)
            wait *= 3


def done():
    d = {}
    if os.path.exists(OUT):
        for line in open(OUT, encoding="utf-8"):
            try:
                r = json.loads(line)
                d[r["identifier"]] = r
            except Exception:
                pass
    return d


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--delay", type=float, default=2.0)
    args = ap.parse_args()
    ids = [l.strip() for l in open(IDS, encoding="utf-8") if l.strip() and not l.startswith("#")]
    have = done()
    todo = [i for i in ids if i not in have]
    print(f"{len(ids)} items, {len(todo)} to fetch", flush=True)
    for n, ident in enumerate(todo, 1):
        md = (get(ident) or {}).get("metadata") or {}
        rec = {k: md.get(k) for k in KEEP if md.get(k) is not None}
        rec["identifier"] = ident
        with open(OUT, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"{n}/{len(todo)} {ident}: {str(rec.get('title'))[:60]} | {rec.get('date') or rec.get('year')}", flush=True)
        if n < len(todo):
            time.sleep(args.delay)
    print("finished", flush=True)
