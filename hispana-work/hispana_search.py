#!/usr/bin/env python3
"""Look for the Spanish-language entries in Hispana, Spain's aggregator of digitised collections.

Hispana (hispana.mcu.es) gathers the digital collections of Spanish libraries, archives and museums -
the Biblioteca Digital Hispánica of the Biblioteca Nacional among them - and answers SRU, so it can be
searched the way Gallica is. The BNE's own endpoints refuse our requests (403), so Hispana is the way
in. One search at a time, --delay seconds apart, results appended to hispana.jsonl as they arrive, so
the run is resumable. Nothing identifying is sent.

Its SRU server takes one term per index, so a title is searched as
`dc.title=japon and dc.title=cristiandad`; quoted phrases come back as "huh?".

    hispana_search.py [--delay 2] [--language Spanish] [--limit N]
"""
import argparse, html, json, os, re, sqlite3, sys, time, urllib.error, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "union-catalog-work"))
from ia_lookup import norm, main_title  # noqa: E402

OUT = os.path.join(HERE, "hispana.jsonl")
UA = "japan-bib/1.0 (offline bibliography reconciliation)"
SRU = ("https://hispana.mcu.es/i18n/sru/sru.cmd?operation=searchRetrieve&version=1.1"
       "&recordSchema=info:srw/schema/1/dc-v1.1&maximumRecords=10&query=")
STOP = set("""el la los las un una unos unas de del al y e o en por para con su sus es que como
    the of and a an in on to for with from tr traduccion traducción prologo prólogo edicion edición
    tomo vol volumen parte""".split())


def words(title, n=3):
    ws = [w for w in norm(main_title(title)).split() if w not in STOP and len(w) > 3]
    return ws[:n]


def surname(author):
    a = (author or "").strip()
    if "," not in a:
        return ""
    toks = norm(a.split(",")[0]).split()
    return toks[-1] if toks and len(toks) <= 3 else ""


def get(url, tries=4):
    wait = 20
    for n in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/xml"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and n < tries - 1:
                print(f"  HTTP {e.code}; pausing {wait}s", flush=True)
                time.sleep(wait); wait *= 3; continue
            raise
        except Exception:
            if n < tries - 1:
                time.sleep(wait); wait *= 3; continue
            raise


def field(rec, tag):
    return [re.sub(r"\s+", " ", html.unescape(x)).strip()
            for x in re.findall(f"<dc:{tag}[^>]*>(.*?)</dc:{tag}>", rec, re.S)]


def parse(xml):
    out = []
    for rec in re.findall(r"<srw_dc:dc[^>]*>(.*?)</srw_dc:dc>", xml, re.S):
        ids = field(rec, "identifier")
        url = next((i for i in ids if i.startswith("http")), "")
        out.append({"title": (field(rec, "title") or [""])[0][:200],
                    "creator": "; ".join(field(rec, "creator"))[:150],
                    "date": (field(rec, "date") or [""])[0][:40],
                    "publisher": (field(rec, "publisher") or [""])[0][:100],
                    "language": (field(rec, "language") or [""])[0][:20],
                    "type": "; ".join(field(rec, "type"))[:60],
                    "rights": "; ".join(field(rec, "rights"))[:120],
                    "url": url, "identifiers": ids[:4]})
    n = re.findall(r"numberOfRecords>(\d+)", xml)
    return out, int(n[0]) if n else None


def search(title, author):
    """Up to three queries, narrowing then widening; stops at the first with results."""
    ws, sn = words(title), surname(author)
    if not ws:
        return [], [], None
    tries = []
    if sn:
        tries.append(" and ".join([f"dc.title={w}" for w in ws] + [f"dc.creator={sn}"]))
    tries.append(" and ".join(f"dc.title={w}" for w in ws))
    if len(ws) > 2:
        tries.append(" and ".join(f"dc.title={w}" for w in ws[:2]))
    used, hits, total = [], [], None
    for q in tries:
        used.append(q)
        hits, total = parse(get(SRU + urllib.parse.quote(q)))
        if hits:
            break
        time.sleep(1.0)
    return hits, used, total


def targets(db, language):
    con = sqlite3.connect(db)
    rows = con.execute("SELECT id, author, title, year, year_num FROM books WHERE language = ? "
                       "AND type IN ('book','periodical') AND (links IS NULL OR links = '') "
                       "ORDER BY year_num IS NULL, id", (language,)).fetchall()
    con.close()
    return rows


def done():
    d = set()
    if os.path.exists(OUT):
        for line in open(OUT, encoding="utf-8"):
            try:
                d.add(json.loads(line)["id"])
            except Exception:
                pass
    return d


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--delay", type=float, default=2.0)
    ap.add_argument("--language", default="Spanish")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--db", default=os.path.join(HERE, "..", "list.sqlite"))
    args = ap.parse_args()
    have = done()
    todo = [r for r in targets(args.db, args.language) if r[0] not in have]
    if args.limit:
        todo = todo[:args.limit]
    print(f"{len(have)} already searched, {len(todo)} to go, delay {args.delay}s", flush=True)
    for n, (rid, author, title, year, year_num) in enumerate(todo, 1):
        try:
            hits, used, total = search(title, author)
            rec = {"id": rid, "author": author, "title": title, "year": year, "year_num": year_num,
                   "language": args.language, "queries": used, "total": total, "hits": hits[:10]}
        except Exception as e:
            rec = {"id": rid, "author": author, "title": title, "year": year, "error": repr(e)[:160]}
        with open(OUT, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"{n}/{len(todo)} id{rid} {rec.get('error') or str(len(rec.get('hits') or [])) + ' hit(s)'} "
              f"| {title[:55]}", flush=True)
        if n < len(todo):
            time.sleep(args.delay)
    print("finished", flush=True)
