#!/usr/bin/env python3
"""Look for the French-language entries on Gallica (gallica.bnf.fr) through the BnF's SRU API.

The API is the documented machine interface (https://api.bnf.fr/fr/api-gallica-de-recherche), so no
page scraping and no captcha is involved. One search at a time, --delay seconds apart (3 by default),
with a long back-off on errors; results are appended to gallica.jsonl as they arrive, so the run is
resumable. Nothing identifying is sent: a plain descriptive User-Agent and no contact details.

    gallica_search.py [--delay 3] [--limit N] [--language French] [--db ../list.sqlite]
"""
import argparse, json, os, re, sqlite3, sys, time, urllib.error, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "union-catalog-work"))
from ia_lookup import norm, main_title  # noqa: E402

OUT = os.path.join(HERE, "gallica.jsonl")
UA = "japan-bib/1.0 (offline bibliography reconciliation)"
SRU = "https://gallica.bnf.fr/SRU?operation=searchRetrieve&version=1.2&maximumRecords=10&query="
STOP = set("""le la les l un une des du de d au aux et ou en dans sur sous par pour avec sans chez a
    son sa ses ce cet cette leur leurs notre nos votre vos il elle on nous vous ils elles est sont
    par tr trad traduit traduite traduction par avec preface préface introduction nouvelle edition
    édition tome vol volume""".split())
CUT = re.compile(r",\s+(?:tr\.|trad\.|traduit|traduite|par |avec |préface|preface|introduction|"
                 r"nouvelle édition|nouvelle edition|éd\.|ed\.)", re.I)


def words(title, n=5):
    t = CUT.split(main_title(title))[0]
    ws = [w for w in norm(t).split() if w not in STOP and len(w) > 2]
    return ws[:n]


def surname(author):
    a = (author or "").strip()
    if "," not in a:
        return ""
    head = a.split(",")[0]
    toks = norm(head).split()
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


def field(rec, tag):
    return [re.sub(r"\s+", " ", x).strip() for x in re.findall(f"<dc:{tag}[^>]*>(.*?)</dc:{tag}>", rec, re.S)]


def parse(xml):
    out = []
    for rec in re.findall(r"<srw:recordData>(.*?)</srw:recordData>", xml, re.S):
        ark = next((i for i in field(rec, "identifier") if "ark:" in i), "")
        if not ark:
            continue
        out.append({"ark": ark, "title": (field(rec, "title") or [""])[0][:200],
                    "creator": "; ".join(field(rec, "creator"))[:150],
                    "date": (field(rec, "date") or [""])[0], "type": (field(rec, "type") or [""])[0],
                    "rights": "; ".join(field(rec, "rights"))[:60],
                    "language": (field(rec, "language") or [""])[0]})
    n = re.findall(r"numberOfRecords>(\d+)", xml)
    return out, int(n[0]) if n else None


def search(title, author):
    """Up to three queries, from the most specific to the least; stops at the first with results."""
    ws, sn = words(title), surname(author)
    if not ws:
        return [], [], None
    tries = []
    if sn:
        tries.append(f'(dc.title all "{" ".join(ws)}") and (dc.creator all "{sn}")')
        if len(ws) > 3:
            tries.append(f'(dc.title all "{" ".join(ws[:3])}") and (dc.creator all "{sn}")')
    tries.append(f'(dc.title all "{" ".join(ws)}")')
    used, hits, total = [], [], None
    for q in tries:
        used.append(q)
        hits, total = parse(get(SRU + urllib.parse.quote(q)))
        if hits:
            break
        time.sleep(1.5)
    return hits, used, total


def targets(db, language):
    con = sqlite3.connect(db)
    rows = con.execute("SELECT id, author, title, year, year_num FROM books WHERE language = ? "
                       "AND type IN ('book','periodical') AND (links IS NULL OR links = '') "
                       "ORDER BY year_num IS NULL, id", (language,)).fetchall()
    con.close()
    return rows


def done():
    """What has been searched already, by what the entry is rather than by its row id: ids move
    whenever the database is rebuilt with new sources, and an id reused for another book would
    otherwise be passed over."""
    sys.path.insert(0, os.path.join(HERE, "..", "union-catalog-work"))
    from language import key as rowkey
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
    ap.add_argument("--delay", type=float, default=3.0)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--language", default="French")
    ap.add_argument("--db", default=os.path.join(HERE, "..", "list.sqlite"))
    args = ap.parse_args()
    from language import key as rowkey
    have = done()
    todo = [r for r in targets(args.db, args.language) if rowkey(r[1], r[2], r[3]) not in have]
    if args.limit:
        todo = todo[:args.limit]
    print(f"{len(have)} already searched, {len(todo)} to go, delay {args.delay}s "
          f"(about {len(todo) * args.delay / 60:.0f} minutes)", flush=True)
    for n, (rid, author, title, year, year_num) in enumerate(todo, 1):
        try:
            hits, used, total = search(title, author)
            rec = {"id": rid, "author": author, "title": title, "year": year, "year_num": year_num,
                   "queries": used, "total": total, "hits": hits[:10]}
        except Exception as e:
            rec = {"id": rid, "author": author, "title": title, "year": year, "error": repr(e)[:160]}
        with open(OUT, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        if rec.get("hits") or rec.get("error") or n % 25 == 0:
            print(f"{n}/{len(todo)} id{rid} {rec.get('error') or str(len(rec.get('hits') or [])) + ' hit(s)'} "
                  f"| {title[:55]}", flush=True)
        if n < len(todo):
            time.sleep(args.delay)
    print("finished", flush=True)
