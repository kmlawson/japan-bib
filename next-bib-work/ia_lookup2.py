#!/usr/bin/env python3
"""archive.org lookups (via the `ia` CLI) for the NEW books from Borton/Henshall only - records already
matched to a Union Catalog row are not looked up again. Resumable; cache = ia_cache2.jsonl.
Usage: ia_lookup2.py [--workers 3]"""
import argparse, json, os, re, sys, threading
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "union-catalog-work"))
from ia_lookup import lookup  # noqa: E402
from merge import merge, uc_rows_from_db, load_cache2, lkey, wants_lookup, rec_years, CACHE2  # noqa: E402

lock = threading.Lock()
CUT = re.compile(r",\s+(?:trs?\.|ed\.|rev\.|illus\.|with |foreword|introduction|preface|préface|compiled|adapted|authorized|pub\.|"
                 r"from the |avec |traduits?|übersetzt|aus dem |mit |collotypes|tr\. )|\s+\((?:formerly|traduction)", re.I)


def clean_title(t):
    """Borton runs the statement of responsibility on after a comma: keep the title proper for searching."""
    t = CUT.split(t)[0]
    return re.sub(r"\s+\.\s\.\s\.\s*", " ", t).strip(" ,;")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args()
    _, new = merge(uc_rows_from_db())
    cache = load_cache2()
    todo = {}
    for r in new:
        if not wants_lookup(r):
            continue
        c = cache.get(lkey(r))
        # not looked up yet, or looked up when only 12 candidates were kept (nearest dates might have been cut)
        if c is None or (len(c["matches"]) == 12 and not c.get("redone")):
            todo.setdefault(lkey(r), r)
    print(f"cached {len(cache)}, to do {len(todo)}", flush=True)
    done = [0]

    def work(kr):
        k, r = kr
        try:
            res = lookup(re.sub(r"\s*\([^)]*\)", "", r["author"]), clean_title(r["title"]), rec_years(r))
        except Exception as e:
            print("ERR", e, flush=True)
            return
        res.update(key=k, author=r["author"], title=r["title"], redone=True)
        with lock:
            with open(CACHE2, "a", encoding="utf-8") as f:
                f.write(json.dumps(res, ensure_ascii=False) + "\n")
            done[0] += 1
            if done[0] % 25 == 0:
                print(f"{done[0]}/{len(todo)}", flush=True)

    with ThreadPoolExecutor(args.workers) as ex:
        list(ex.map(work, todo.items()))
    print("finished", done[0], flush=True)
