#!/usr/bin/env python3
"""Classify archive.org items as openly viewable, borrowable (CDL), or neither.

Reads ids_part1.txt (one identifier per line) next to this script and writes
part1.jsonl in the same directory, appending one JSON object per identifier so
that an interruption loses nothing.  On restart, identifiers already present in
part1.jsonl are skipped.

No personal information is sent anywhere: default user-agent, archive.org only.
"""

import json
import os
import sys
import time

import internetarchive as ia

HERE = os.path.dirname(os.path.abspath(__file__))
PART = sys.argv[1] if len(sys.argv) > 1 else "1"      # check_access.py [part]  -> ids_partN.txt / partN.jsonl
IDS = os.path.join(HERE, f"ids_part{PART}.txt")
OUT = os.path.join(HERE, f"part{PART}.jsonl")

FIELDS = [
    "identifier",
    "collection",
    "access-restricted-item",
    "lending___status",
    "subject",
    "mediatype",
]

BATCH = 40
LENDABLE = {
    "is_lendable",
    "is_borrowable",
    "is_browsable",
    "available_to_borrow",
    "available_to_browse",
}


def as_list(v):
    if v is None:
        return []
    if isinstance(v, list):
        return v
    return [v]


def truthy(v):
    if isinstance(v, list):
        v = v[0] if v else None
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in ("true", "1", "yes")


def classify(ident, doc):
    """doc is a search-result / metadata dict, or None for missing."""
    if doc is None:
        return {
            "identifier": ident,
            "restricted": False,
            "inlibrary": False,
            "printdisabled": False,
            "lending_status": None,
            "collections": [],
            "subject_has_inlibrary": False,
            "access": "missing",
        }
    colls = [str(c) for c in as_list(doc.get("collection"))]
    lend = as_list(doc.get("lending___status"))
    lend = [str(x) for x in lend]
    subj = [str(s) for s in as_list(doc.get("subject"))]
    restricted = truthy(doc.get("access-restricted-item"))
    if restricted:
        access = "borrow" if (set(lend) & LENDABLE) else "printdisabled-only"
    else:
        access = "open"
    return {
        "identifier": doc.get("identifier", ident),
        "restricted": restricted,
        "inlibrary": "inlibrary" in colls,
        "printdisabled": "printdisabled" in colls,
        "lending_status": lend if lend else None,
        "collections": colls[:8],
        "subject_has_inlibrary": any("inlibrary" == s.strip().lower() for s in subj),
        "access": access,
        "mediatype": doc.get("mediatype"),
        "n_collections": len(colls),
    }


def search(batch, attempts=5):
    q = "identifier:(" + " OR ".join('"%s"' % b for b in batch) + ")"
    delay = 3.0
    for attempt in range(attempts):
        try:
            s = ia.search_items(q, fields=FIELDS, params={"rows": 100})
            return list(s.iter_as_results())
        except Exception as exc:  # noqa: BLE001
            if attempt == attempts - 1:
                raise
            sys.stderr.write("  retry (%s) after %.0fs: %s\n" % (attempt + 1, delay, exc))
            time.sleep(delay)
            delay *= 2
    return []


def get_meta(ident, attempts=4):
    delay = 3.0
    for attempt in range(attempts):
        try:
            return ia.get_item(ident).metadata or None
        except Exception as exc:  # noqa: BLE001
            if attempt == attempts - 1:
                sys.stderr.write("  get_item failed for %s: %s\n" % (ident, exc))
                return None
            time.sleep(delay)
            delay *= 2
    return None


def main():
    with open(IDS, encoding="utf-8") as fh:
        ids = [ln.strip() for ln in fh if ln.strip()]

    done = set()
    if os.path.exists(OUT):
        with open(OUT, encoding="utf-8") as fh:
            for ln in fh:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    done.add(json.loads(ln)["identifier"])
                except Exception:  # noqa: BLE001
                    pass
    todo = [i for i in ids if i not in done]
    sys.stderr.write("%d ids, %d already done, %d to do\n" % (len(ids), len(done), len(todo)))

    out = open(OUT, "a", encoding="utf-8")

    def emit(rec):
        out.write(json.dumps(rec, ensure_ascii=False) + "\n")
        out.flush()

    for start in range(0, len(todo), BATCH):
        batch = todo[start:start + BATCH]
        results = search(batch)
        by_id = {}
        for r in results:
            by_id[r.get("identifier")] = r
        missing = []
        for ident in batch:
            doc = by_id.get(ident)
            if doc is None:
                missing.append(ident)
            else:
                emit(classify(ident, doc))
        for ident in missing:
            # re-query singly
            time.sleep(0.5)
            single = search([ident])
            doc = None
            for r in single:
                if r.get("identifier") == ident:
                    doc = r
            if doc is None:
                md = get_meta(ident)
                if md:
                    rec = classify(ident, md)
                    rec["via"] = "get_item"
                    emit(rec)
                    continue
                rec = classify(ident, None)
                emit(rec)
                sys.stderr.write("  MISSING: %s\n" % ident)
            else:
                rec = classify(ident, doc)
                rec["via"] = "single"
                emit(rec)
        sys.stderr.write(
            "batch %d/%d done (%d ids, %d needed single lookup)\n"
            % (start // BATCH + 1, (len(todo) + BATCH - 1) // BATCH, len(batch), len(missing))
        )
        time.sleep(0.4)

    out.close()


if __name__ == "__main__":
    main()
