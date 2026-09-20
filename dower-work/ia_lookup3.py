#!/usr/bin/env python3
"""archive.org lookups for the Dower & George books that are not already in the database.

Same search and cache format as next-bib-work/ia_lookup2.py; the cache is ia_cache3.jsonl and the run
is resumable, so it can be repeated as more pages are transcribed.

    ia_lookup3.py [--workers 3]
"""
import argparse, json, os, re, sqlite3, sys, threading
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "next-bib-work"))
sys.path.insert(0, os.path.join(HERE, "..", "union-catalog-work"))
from ia_lookup import lookup  # noqa: E402
from ia_lookup2 import clean_title  # noqa: E402
import merge as M  # noqa: E402
import dower_merge as D  # noqa: E402

lock = threading.Lock()


def rows_from_db():
    """The database without the rows Dower himself contributed - otherwise, once it has been rebuilt,
    every Dower entry would look like a duplicate of itself and nothing would be looked up."""
    con = sqlite3.connect(os.path.join(HERE, "..", "list.sqlite"))
    rows = [list(x) + ["", "", ""] for x in con.execute(
        "SELECT author,title,year,year_num,edition,volume,links,other,source,type FROM books "
        "WHERE source <> ? ORDER BY id", (D.SRC,))]
    con.close()
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args()
    _, new = D.split(rows_from_db())
    cache = M.load_cache2(D.CACHE3)
    todo = {}
    for r in new:
        if M.wants_lookup(r) and M.lkey(r) not in cache:
            todo.setdefault(M.lkey(r), r)
    print(f"cached {len(cache)}, to do {len(todo)}", flush=True)
    done = [0]

    def work(kr):
        k, r = kr
        try:
            res = lookup(re.sub(r"\s*\([^)]*\)", "", r["author"]), clean_title(r["title"]), M.rec_years(r))
        except Exception as e:
            print("ERR", e, flush=True)
            return
        res.update(key=k, author=r["author"], title=r["title"], redone=True)
        with lock:
            with open(D.CACHE3, "a", encoding="utf-8") as f:
                f.write(json.dumps(res, ensure_ascii=False) + "\n")
            done[0] += 1
            if done[0] % 25 == 0:
                print(f"{done[0]}/{len(todo)}", flush=True)

    with ThreadPoolExecutor(args.workers) as ex:
        list(ex.map(work, todo.items()))
    print("finished", done[0], flush=True)
