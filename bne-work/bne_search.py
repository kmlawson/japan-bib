#!/usr/bin/env python3
"""Search BNE Digital for the Spanish-language entries, by driving Chrome.

The Biblioteca Nacional de España answers no script: curl, a full set of browser headers and headless
Chrome are all refused by its Cloudflare. An ordinary Chrome window is not, so this asks Chrome to do
the searching (see chrome.py; Chrome needs View > Developer > Allow JavaScript from Apple Events).

Its search wants a quoted phrase - `w="estudios sobre el japon"` with `f=name` for a title - since a
bare word returns nothing at all. Each entry is tried with the first few words of its title, then with
fewer; whatever comes back is written to bne.jsonl with the viewer link, which is the page that opens
the scan. Nothing is typed into any page and no session is read: only the URL bar and the results.

    bne_search.py [--language Spanish] [--limit N] [--words 5]
"""
import argparse, json, os, re, sys, time, urllib.parse
import sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "union-catalog-work"))
from chrome import Chrome  # noqa: E402
from ia_lookup import norm, main_title  # noqa: E402

OUT = os.path.join(HERE, "bne.jsonl")
RESULTS = "https://bnedigital.bne.es/bd/es/results?o=&w={q}&f={f}&l=20&t=score-desc&x="
STOP = set("""el la los las un una unos unas de del al y e o en por para con su sus es que como
    the of and a an in on to for with from tr traduccion prologo edicion tomo vol volumen parte""".split())
READ = """[...document.querySelectorAll('a')].filter(a=>/viewer\\?id=|card\\?oid=/.test(a.href))
    .map(a=>({href:a.href, block:((a.closest('li,article,div.result,tr')||a).innerText||'').replace(/\\s+/g,' ').slice(0,300)}))"""


def words(title, n):
    return [w for w in norm(main_title(title)).split() if w not in STOP and len(w) > 2][:n]


def seen():
    d = set()
    if os.path.exists(OUT):
        for line in open(OUT, encoding="utf-8"):
            try:
                d.add(json.loads(line)["id"])
            except Exception:
                pass
    return d


def targets(db, language):
    con = sqlite3.connect(db)
    rows = con.execute("SELECT id, author, title, year, year_num FROM books WHERE language = ? "
                       "AND type IN ('book','periodical') AND (links IS NULL OR links = '') "
                       "ORDER BY year_num IS NULL, id", (language,)).fetchall()
    con.close()
    return rows


def search(c, title, author, most):
    """Up to three phrases, longest first; returns (hits, the queries used)."""
    ws = words(title, most)
    tries, used, hits = [], [], []
    if len(ws) >= 2:
        tries.append(" ".join(ws))
    if len(ws) > 3:
        tries.append(" ".join(ws[:3]))
    if len(ws) > 2:
        tries.append(" ".join(ws[:2]))
    for phrase in tries:
        used.append(phrase)
        q = urllib.parse.quote(f'"{phrase}"')
        c.go(RESULTS.format(q=q, f="name"), settle=1.5)
        time.sleep(1.0)
        found = c.json(READ) or []
        seen_urls, out = set(), []
        for f in found:
            if f["href"] in seen_urls:
                continue
            seen_urls.add(f["href"])
            out.append(f)
        if out:
            return out, used
    return hits, used


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--language", default="Spanish")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--words", type=int, default=5)
    ap.add_argument("--db", default=os.path.join(HERE, "..", "list.sqlite"))
    args = ap.parse_args()
    have = seen()
    todo = [r for r in targets(args.db, args.language) if r[0] not in have]
    if args.limit:
        todo = todo[:args.limit]
    print(f"{len(have)} already searched, {len(todo)} to go", flush=True)
    with Chrome() as c:
        for n, (rid, author, title, year, year_num) in enumerate(todo, 1):
            try:
                hits, used = search(c, title, author, args.words)
                rec = {"id": rid, "author": author, "title": title, "year": year, "year_num": year_num,
                       "queries": used, "hits": hits}
            except Exception as e:
                rec = {"id": rid, "author": author, "title": title, "year": year, "error": repr(e)[:200]}
            with open(OUT, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            print(f"{n}/{len(todo)} id{rid} {rec.get('error') or str(len(rec.get('hits') or [])) + ' hit(s)'}"
                  f" | {title[:50]}", flush=True)
    print("finished", flush=True)
