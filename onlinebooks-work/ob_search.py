#!/usr/bin/env python3
"""Look for the entries that have no online copy yet on The Online Books Page (onlinebooks.library.upenn.edu).

One search per entry, spaced by --delay seconds (default 5, the Crawl-delay their robots.txt asks for),
one at a time, with a long back-off on errors. Results are appended to ob.jsonl as they come in, so the
run can be stopped and resumed at any time. Nothing identifying is sent: a plain descriptive User-Agent,
no cookies, no contact details, and only this one site is contacted.

    ob_search.py [--delay 5] [--limit N] [--db ../list.sqlite]
"""
import argparse, html, json, os, re, sqlite3, sys, time, urllib.error, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "union-catalog-work"))
from ia_lookup import norm, main_title, STOP  # noqa: E402

OUT = os.path.join(HERE, "ob.jsonl")
UA = "japan-bib/1.0 (offline bibliography reconciliation)"
SEARCH = "https://onlinebooks.library.upenn.edu/webbin/book/search"
CUT = re.compile(r",\s+(?:trs?\.|ed\.|rev\.|illus\.|with |foreword|introduction|preface|compiled|adapted|"
                 r"authorized|pub\.|from the |avec |traduits?|übersetzt|aus dem )", re.I)


def words(title, n=6):
    t = CUT.split(main_title(title))[0]
    ws = [w for w in norm(t).split() if w not in STOP and len(w) > 1]
    return ws[:n] or [w for w in norm(t).split() if len(w) > 1][:n]


def surname(author):
    a = (author or "").strip()
    if "," not in a:
        return ""
    head = a.split(",")[0]
    toks = norm(head).split()
    return toks[-1] if toks and len(toks) <= 3 else ""


def get(url, tries=4):
    wait = 30
    for n in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
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


def strip(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", s))).strip()


ENTRY = re.compile(r'(?=<li><a href="[^"]*lookupid\?key=)')
ANCHOR = re.compile(r'<a href="([^"]+)"[^>]*>(.*?)</a>', re.S)
# HathiTrust copies are not wanted at all (many are US-only, and the rest need their own reader);
# anything else marked as restricted is dropped too. Dropped copies are still recorded, so the rule
# can be changed later without searching again.
RESTRICTED = re.compile(r"hathitrust|US access only|access only in the US|restricted", re.I)


def parse(page):
    """Entries from a results page; each copy keeps its label. HathiTrust copies and anything marked
    "US access only" go to `dropped` rather than `copies`."""
    out = []
    block = re.search(r'<ul class="nodot">(.*?)</ul>\s*<hr', page, re.S)
    if not block:
        return out
    for chunk in ENTRY.split(block.group(1)):
        if "lookupid?key=" not in chunk:
            continue
        key = re.search(r"lookupid\?key=([\w.-]+)", chunk).group(1)
        cite = re.search(r"<cite>(.*?)</cite>", chunk, re.S)
        if not cite:
            continue
        head = re.sub(r"^\[Info\]\s*", "", strip(chunk[:cite.start()])).rstrip(": ")
        copies, dropped = [], []
        for m in ANCHOR.finditer(chunk):
            if "lookupid?key=" in m.group(1):
                continue
            tail = strip(chunk[m.end():m.end() + 160].split("</li>")[0].split("<a ")[0])
            label = strip(m.group(2))
            if "<cite>" in m.group(2):          # the title itself is the link: the label follows it
                label = tail or label
                tail = ""
            full = (label + " " + tail).strip()
            url = html.unescape(m.group(1))
            bad = RESTRICTED.search(full) or "hathitrust.org" in url.lower()
            (dropped if bad else copies).append({"label": full[:120], "url": url})
        imprint = strip(chunk[cite.end():].split("<ul")[0].split("</li>")[0])
        out.append({"key": key, "author": head, "title": strip(cite.group(1)), "imprint": imprint[:160],
                    "copies": copies[:8], "dropped": dropped[:8]})
        if len(out) >= 25:
            break
    return out


def targets(db):
    con = sqlite3.connect(db)
    rows = con.execute("SELECT id, author, title, year, year_num FROM books "
                       "WHERE (links IS NULL OR links = '') AND type IN ('book','periodical') "
                       "ORDER BY year_num IS NULL, id").fetchall()
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
    ap.add_argument("--delay", type=float, default=5.0)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--db", default=os.path.join(HERE, "..", "list.sqlite"))
    args = ap.parse_args()
    have = done()
    todo = [r for r in targets(args.db) if r[0] not in have]
    if args.limit:
        todo = todo[:args.limit]
    print(f"{len(have)} already searched, {len(todo)} to go, delay {args.delay}s "
          f"(about {len(todo) * args.delay / 3600:.1f} hours)", flush=True)
    for n, (rid, author, title, year, year_num) in enumerate(todo, 1):
        ws = words(title)
        if not ws:
            continue
        q = {"title": " ".join(ws), "tmode": "words"}
        sn = surname(author)
        if sn:
            q.update(author=sn, amode="words")
        url = SEARCH + "?" + urllib.parse.urlencode(q)
        try:
            page = get(url)
            rec = {"id": rid, "author": author, "title": title, "year": year, "query": q, "hits": parse(page)}
            m = re.search(r"([\d,]+)\s+items? (?:was|were) found", page)
            rec["total"] = int(m.group(1).replace(",", "")) if m else (0 if "No items were found" in page else None)
        except Exception as e:
            rec = {"id": rid, "author": author, "title": title, "year": year, "query": q, "error": repr(e)[:160]}
        with open(OUT, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        if n % 50 == 0 or rec.get("hits"):
            print(f"{n}/{len(todo)} id{rid} {rec.get('error') or str(len(rec.get('hits') or [])) + ' hit(s)'} "
                  f"| {title[:55]}", flush=True)
        if n < len(todo):
            time.sleep(args.delay)
    print("finished", flush=True)
