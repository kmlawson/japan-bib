#!/usr/bin/env python3
"""Read the Nichibunken catalogue of Western-language books on Japan (日本関係欧文図書目録).

    https://shinku.nichibun.ac.jp/gpub/all_list.php?disprow=9999&changed=yes

The list page gives a year and a title for each of 1,061 works; the record behind it gives the author,
the title page as printed, the imprint and the collation. This fetches the list once, keeps the works
published in a chosen range (1850-1900 by default), and then fetches one record at a time, a second or
two apart. Nothing identifying is sent: a plain descriptive User-Agent, no contact address, no account.
The catalogue's own full-text links are dead and are not followed.

Characters the site cannot show in its encoding are served as little images; each is kept as the token
{gNNNN} and turned into a letter later from gaiji.tsv (see nichi_gaiji.py).

    nichi_fetch.py [--delay 1.5] [--from 1850] [--to 1900] [--limit N]
"""
import argparse, html, json, os, re, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "nichi.jsonl")
LIST_HTML = os.path.join(HERE, "all_list.html")
UA = "japan-bib/1.0 (offline bibliography reconciliation)"
BASE = "https://shinku.nichibun.ac.jp/gpub/"
ROW = re.compile(r'<tr><td align="center">(\d{4})<br></td><td><A HREF="book/(g\d+)\.html"[^>]*>(.*?)</A>', re.S)
GAIJI = re.compile(r"<IMG[^>]*?gaiji/images/(\w+)\.gif[^>]*>", re.I)   # ../gaiji/... on the record pages


def get(url, tries=4):
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


def text(s):
    """Markup out, gaiji kept as a token, entities decoded, spaces tidied."""
    s = GAIJI.sub(lambda m: "{" + m.group(1) + "}", s)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"[\s　]+", " ", html.unescape(s)).strip()


def listing(refresh=False):
    if refresh or not os.path.exists(LIST_HTML):
        open(LIST_HTML, "w", encoding="utf-8").write(get(BASE + "all_list.php?disprow=9999&changed=yes"))
    h = open(LIST_HTML, encoding="utf-8").read()
    return [{"year": int(y), "id": i, "list_title": text(t)} for y, i, t in ROW.findall(h)]


def record(ident):
    """The fields of one catalogue record; the contents list at the foot is not kept."""
    h = get(f"{BASE}book/{ident}.html")
    body = h[h.find("<HR>"):]
    m = re.search(r"<B>(\d+)</B><B>(.*?)</B><BR>(.*?)<BR>", body, re.S)
    num, author, head = (m.group(1), text(m.group(2)), text(m.group(3))) if m else ("", "", "")
    block = re.search(r"<FONT SIZE=-1>(.*?)</FONT>", body, re.S)
    lines = [text(x) for x in re.split(r"<BR>", block.group(1))] if block else []
    lines = [x for x in lines if x]
    call = re.search(r"<p align=right>\[(.*?)\]\((\d+)\)</p>", body)
    ttl, yr = head, ""
    m = re.match(r"(.*?)\.?\s*((?:15|16|17|18|19|20)\d\d)\.?\s*$", head)
    if m:
        ttl, yr = m.group(1).rstrip(" ."), m.group(2)
    return {"id": ident, "number": num, "author": author, "title": ttl, "year": yr,
            "titlepage": lines[0] if lines else "", "imprint": lines[1] if len(lines) > 1 else "",
            "collation": lines[2] if len(lines) > 2 else "", "extra": lines[3:6],
            "call_number": call.group(1) if call else "", "record_id": call.group(2) if call else "",
            "url": f"{BASE}book/{ident}.html"}


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
    ap.add_argument("--delay", type=float, default=1.5)
    ap.add_argument("--from", dest="a", type=int, default=1850)
    ap.add_argument("--to", dest="b", type=int, default=1900)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--refresh", action="store_true", help="fetch the list page again")
    args = ap.parse_args()
    rows = [r for r in listing(args.refresh) if args.a <= r["year"] <= args.b]
    have = done()
    todo = [r for r in rows if r["id"] not in have]
    if args.limit:
        todo = todo[:args.limit]
    print(f"{len(rows)} works {args.a}-{args.b}, {len(todo)} to fetch", flush=True)
    for n, row in enumerate(todo, 1):
        try:
            rec = record(row["id"])
            rec.update(list_year=row["year"], list_title=row["list_title"])
        except Exception as e:
            rec = {"id": row["id"], "list_year": row["year"], "list_title": row["list_title"],
                   "error": repr(e)[:160]}
        with open(OUT, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        if n % 25 == 0 or rec.get("error"):
            print(f"{n}/{len(todo)} {row['id']} {rec.get('error') or rec.get('title', '')[:60]}", flush=True)
        if n < len(todo):
            time.sleep(args.delay)
    print("finished", flush=True)
