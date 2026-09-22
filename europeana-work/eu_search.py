#!/usr/bin/env python3
"""Look for entries with no online copy yet on Europeana (europeana.eu), through its Search API.

The API is the documented machine interface (https://europeana.atlassian.net/wiki/spaces/EF/pages/2385739812),
reached with the public demonstration key it publishes; no page is scraped. One search at a time,
--delay seconds apart (2 by default), with a long back-off on errors; results are appended to eu.jsonl as
they arrive, so the run is resumable. Nothing identifying is sent: a plain descriptive User-Agent and no
contact details.

Only TEXT records are asked for. By default the entries searched are those that came from Wenckstern
(1907) and have no copy yet; --source '' searches every entry without a copy.

    eu_search.py [--delay 2] [--limit N] [--source "Wenckstern (1907)"] [--db ../list.sqlite]
"""
import argparse, json, os, re, sqlite3, sys, time, urllib.error, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "union-catalog-work"))
from ia_lookup import norm, main_title, STOP  # noqa: E402
from language import key as rowkey  # noqa: E402

OUT = os.path.join(HERE, "eu.jsonl")
UA = "japan-bib/1.0 (offline bibliography reconciliation)"
API = "https://api.europeana.eu/record/v2/search.json?wskey=api2demo&profile=minimal&rows=10&qf=TYPE%3ATEXT&query="
CUT = re.compile(r",\s+(?:trs?\.|ed\.|rev\.|illus\.|with |foreword|introduction|preface|préface|compiled|adapted|"
                 r"authorized|pub\.|from the |avec |traduits?|übersetzt|aus dem |mit |herausgegeben|edited|translated)", re.I)
MORE_STOP = set("""der die das des dem den ein eine eines einer einem einen und oder von im in auf zu zur zum
    le la les l un une des du de d et ou en dans sur par pour avec au aux il el los las y o con para por
    the a an of and or in on at to for with by from its his her their vol vols bd t""".split())


def words(title, n=6):
    t = CUT.split(main_title(title))[0]
    ws = [w for w in norm(t).split() if w not in STOP and w not in MORE_STOP and len(w) > 2]
    return ws[:n]


def surname(author):
    a = re.sub(r"^\(|\)$", "", (author or "").strip())
    if "," not in a:
        return ""
    head = a.split(",")[0]
    toks = norm(head).split()
    return toks[-1] if toks and len(toks) <= 3 else ""


def get(url, tries=4):
    wait = 20
    for n in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and n < tries - 1:
                print(f"  HTTP {e.code}; pausing {wait}s", flush=True)
                time.sleep(wait)
                wait *= 3
                continue
            raise
        except Exception:
            if n < tries - 1:
                time.sleep(wait)
                wait *= 3
                continue
            raise


def first(x):
    if isinstance(x, list):
        return x[0] if x else ""
    return x or ""


def parse(d):
    out = []
    for it in d.get("items") or []:
        titles = it.get("title") or []
        out.append({"id": it.get("id"), "title": " / ".join(t.strip() for t in titles[:3])[:300],
                    "creator": "; ".join(it.get("dcCreator") or [])[:150],
                    "year": first(it.get("year")), "provider": first(it.get("dataProvider")),
                    "rights": first(it.get("rights")), "language": first(it.get("dcLanguage")),
                    "shown_at": first(it.get("edmIsShownAt")), "has_file": bool(it.get("edmIsShownBy"))})
    return out, d.get("totalResults")


def search(title, author):
    """Up to three queries, from the most specific to the least; stops at the first with results."""
    ws, sn = words(title), surname(author)
    if not ws:
        return [], [], None
    q = lambda xs: "title:(" + " AND ".join(xs) + ")"
    tries = []
    if sn:
        tries.append(f"{q(ws)} AND who:({sn})")
        if len(ws) > 3:
            tries.append(f"{q(ws[:3])} AND who:({sn})")
    tries.append(q(ws))
    used, hits, total = [], [], None
    for x in tries:
        used.append(x)
        hits, total = parse(get(API + urllib.parse.quote(x)))
        if hits:
            break
        time.sleep(1)
    return hits, used, total


def targets(db, source):
    con = sqlite3.connect(db)
    sql = ("SELECT id, author, title, year, year_num FROM books WHERE type IN ('book','periodical') "
           "AND (links IS NULL OR links = '')")
    args = ()
    if source:
        sql += " AND source LIKE ?"
        args = ("%" + source + "%",)
    rows = con.execute(sql + " ORDER BY year_num IS NULL, id", args).fetchall()
    con.close()
    return rows


def done():
    d = set()
    if os.path.exists(OUT):
        for line in open(OUT, encoding="utf-8"):
            try:
                r = json.loads(line)
                d.add(rowkey(r.get("author"), r.get("title"), r.get("year")))
            except Exception:
                pass
    return d


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--delay", type=float, default=2.0)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--source", default="Wenckstern (1907)")
    ap.add_argument("--db", default=os.path.join(HERE, "..", "list.sqlite"))
    args = ap.parse_args()
    have = done()
    todo = [r for r in targets(args.db, args.source) if rowkey(r[1], r[2], r[3]) not in have]
    if args.limit:
        todo = todo[:args.limit]
    print(f"{len(have)} already searched, {len(todo)} to go, delay {args.delay}s "
          f"(about {len(todo) * (args.delay + 1) / 60:.0f} minutes)", flush=True)
    for n, (rid, author, title, year, year_num) in enumerate(todo, 1):
        try:
            hits, used, total = search(title, author)
            rec = {"id": rid, "author": author, "title": title, "year": year, "year_num": year_num,
                   "queries": used, "total": total, "hits": hits[:10]}
        except Exception as e:
            rec = {"id": rid, "author": author, "title": title, "year": year, "error": repr(e)[:160]}
        with open(OUT, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        if rec.get("hits") or rec.get("error") or n % 50 == 0:
            print(f"{n}/{len(todo)} id{rid} {rec.get('error') or str(len(rec.get('hits') or [])) + ' hit(s)'} "
                  f"| {title[:55]}", flush=True)
        if n < len(todo):
            time.sleep(args.delay)
    print("finished", flush=True)
