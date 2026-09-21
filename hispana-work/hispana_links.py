#!/usr/bin/env python3
"""Find out what a Hispana hit actually leads to.

Hispana is an aggregator: its records carry a link to its own record page, and that page carries the
link to the library that holds the digitised copy. Its rights statement cannot be relied on - an 1868
book comes back marked "In Copyright" - so what matters is which library the record points at and
whether that library serves page images.

This takes the hits that agree on date (within --years of the entry), fetches the Hispana record page
for each, one at a time, and writes what it finds to hispana_links.jsonl: the provider's URL, the
holding institution and whether the link is to a viewer of page images.

    hispana_links.py [--years 3] [--delay 2]
"""
import argparse, html, json, os, re, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "hispana.jsonl")
OUT = os.path.join(HERE, "hispana_links.jsonl")
UA = "japan-bib/1.0 (offline bibliography reconciliation)"
# libraries whose links are page-image viewers of digitised books
VIEWERS = [(re.compile(r"bnedigital\.bne\.es", re.I), "Biblioteca Digital Hispánica", True),
           (re.compile(r"bdh-rd\.bne\.es/viewer", re.I), "Biblioteca Digital Hispánica", True),
           (re.compile(r"bdh\.bne\.es", re.I), "Biblioteca Digital Hispánica", True),
           (re.compile(r"bvpb\.mcu\.es", re.I), "Biblioteca Virtual del Patrimonio Bibliográfico", True),
           (re.compile(r"cervantesvirtual\.com", re.I), "Biblioteca Virtual Miguel de Cervantes", True),
           (re.compile(r"bibliotecadigital\.jcyl\.es", re.I), "Biblioteca Digital de Castilla y León", True),
           (re.compile(r"bibliotecavirtualdefensa\.es", re.I), "Biblioteca Virtual de Defensa", True),
           (re.compile(r"mdc\.ulpgc\.es|jable\.ulpgc\.es", re.I), "Memoria Digital de Canarias", True),
           (re.compile(r"prensahistorica\.mcu\.es", re.I), "Biblioteca Virtual de Prensa Histórica", True),
           (re.compile(r"hemerotecadigital\.bne\.es", re.I), "Hemeroteca Digital, BNE", True)]


def year(s):
    m = re.search(r"(1[5-9]\d\d|20\d\d)", s or "")
    return int(m.group(1)) if m else None


def get(url, tries=3):
    wait = 15
    for n in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode("utf-8", "replace")
        except Exception:
            if n == tries - 1:
                raise
            time.sleep(wait)
            wait *= 3


def provider(record_url):
    """(url, institution, is_viewer) for the copy behind a Hispana record page."""
    h = get(record_url)
    urls = [html.unescape(u) for u in re.findall(r'<a[^>]+href="(https?://[^"]+)"', h)]
    urls = [u for u in urls if "mcu.es" not in u and "hispana" not in u
            and not re.search(r"facebook|twitter|rightsstatements|cultura\.gob\.es|europeana", u, re.I)]
    for u in urls:
        for rx, name, viewer in VIEWERS:
            if rx.search(u):
                return u, name, viewer
    return (urls[0] if urls else ""), "", False


def done():
    d = set()
    if os.path.exists(OUT):
        for line in open(OUT, encoding="utf-8"):
            try:
                r = json.loads(line)
                d.add((r["id"], r["record_url"]))
            except Exception:
                pass
    return d


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=int, default=3)
    ap.add_argument("--delay", type=float, default=2.0)
    args = ap.parse_args()
    have, todo = done(), []
    for line in open(SRC, encoding="utf-8"):
        r = json.loads(line)
        ey = r.get("year_num")
        for h in r.get("hits") or []:
            hy = year(h.get("date"))
            if ey and hy and abs(hy - ey) <= args.years and (r["id"], h["url"]) not in have:
                todo.append((r, h, hy))
    print(f"{len(todo)} hits within {args.years} years to resolve", flush=True)
    for n, (r, h, hy) in enumerate(todo, 1):
        try:
            url, inst, viewer = provider(h["url"])
            rec = {"id": r["id"], "author": r.get("author"), "title": r.get("title"), "year": r.get("year"),
                   "hit_title": h.get("title"), "hit_creator": h.get("creator"), "hit_year": hy,
                   "record_url": h["url"], "url": url, "institution": inst, "viewer": viewer}
        except Exception as e:
            rec = {"id": r["id"], "record_url": h["url"], "error": repr(e)[:160]}
        with open(OUT, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"{n}/{len(todo)} id{rec['id']} {'viewer' if rec.get('viewer') else 'no viewer'} "
              f"{rec.get('institution', '')} | {str(rec.get('hit_title'))[:50]}", flush=True)
        if n < len(todo):
            time.sleep(args.delay)
    print("finished", flush=True)
