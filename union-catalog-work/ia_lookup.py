#!/usr/bin/env python3
"""Look up each catalog record on archive.org with the `ia` CLI. Resumable: results are cached in
ia_cache.jsonl keyed on (author, title). Usage: ia_lookup.py [--workers 3] [--limit N]"""
import argparse, difflib, glob, json, os, re, subprocess, sys, threading, time, unicodedata
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "ia_cache.jsonl")
STOP = set("the a an of and in on to for by with from its their his her de la le les du des et en "
           "der die das und von zu im dem den des el los las y del il di e da do dos das van het een "
           "au aux sur à zur zum ein eine or not ou oder och og".split())
lock = threading.Lock()


def fold(s):
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", fold(s).lower()).strip()


def main_title(t):
    """Title proper: cut at statements of responsibility and at the first ; or : once long enough."""
    t = re.split(r"\s+(?:Tr\.|Trans\.|Translated|Ed\.|Edited|Text by|Comp\.|Compiled|With an? |Illus\.|Tr by|Uebers|Übers|Trad\.)", t)[0]
    m = re.match(r"(.{12,}?)[;:]\s", t)
    if m:
        t = m.group(1)
    else:
        m = re.match(r"(.{20,}?)\.\s", t)
        if m:
            t = m.group(1)
    return t.strip(" .,;:")


def words(t, n):
    ws = [w for w in norm(t).split() if len(w) > 1]
    sig = [w for w in ws if w not in STOP]
    return (sig if len(sig) >= 2 else ws)[:n]


def surname(author):
    a = author.strip()
    if not a:
        return ""
    if "," in a:
        head = a.split(",")[0]
        toks = norm(head).split()
        return toks[-1] if toks and len(head.split()) <= 3 else ""
    return ""  # corporate / uninverted heading: do not constrain on creator


def ia_search(q):
    for attempt in range(4):
        try:
            p = subprocess.run(["ia", "search", q, "-f", "title", "-f", "creator", "-f", "year",
                                "-f", "date", "-f", "mediatype", "-p", "rows:50", "-t", "60"],
                               capture_output=True, text=True, timeout=120)
            if p.returncode == 0:
                out = []
                for line in p.stdout.splitlines():
                    try:
                        out.append(json.loads(line))
                    except Exception:
                        pass
                    if len(out) >= 60:
                        break
                return out
            err = p.stderr.strip()[-200:]
        except subprocess.TimeoutExpired:
            err = "timeout"
        time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"ia search failed: {q!r}: {err}")


def cand_year(c):
    y = c.get("year")
    if not y and c.get("date"):
        m = re.match(r"(\d{4})", str(c["date"]))
        y = m.group(1) if m else None
    try:
        return int(y)
    except Exception:
        return None


def score(rec_title, mt, sn, c):
    ct = c.get("title") or ""
    if isinstance(ct, list):
        ct = ct[0]
    a, b, full = norm(mt), norm(ct), norm(rec_title)
    if not a or not b:
        return 0
    r = max(difflib.SequenceMatcher(None, a, b).ratio(),
            difflib.SequenceMatcher(None, full, b).ratio(),
            difflib.SequenceMatcher(None, a, b[:len(a) + 3]).ratio() - 0.05)
    if sn:
        cr = c.get("creator") or ""
        if isinstance(cr, list):
            cr = " ".join(cr)
        if cr:
            if sn in norm(cr).split():
                r += 0.1
            else:
                r -= 0.25
    return r


def lookup(author, title):
    mt = main_title(title)
    sn = surname(author)
    queries = []
    w8, w4 = words(mt, 8), words(mt, 4)
    if not w8:
        return {"queries": [], "matches": []}
    if sn:
        queries.append(f"title:({' '.join(w8)}) AND creator:({sn}) AND mediatype:texts")
        if w4 != w8:
            queries.append(f"title:({' '.join(w4)}) AND creator:({sn}) AND mediatype:texts")
    queries.append(f"title:({' '.join(w8)}) AND mediatype:texts")
    seen, matches, used = set(), [], []
    for q in queries:
        used.append(q)
        for c in ia_search(q):
            if c.get("identifier") in seen:
                continue
            seen.add(c["identifier"])
            s = score(title, mt, sn, c)
            if s >= 0.82:
                ct = c.get("title")
                cr = c.get("creator")
                matches.append({"identifier": c["identifier"],
                                "title": ct[0] if isinstance(ct, list) else ct,
                                "creator": "; ".join(cr) if isinstance(cr, list) else cr,
                                "year": cand_year(c), "score": round(s, 3)})
        if matches:
            break
    matches.sort(key=lambda m: -m["score"])
    return {"queries": used, "matches": matches[:12]}


def key(r):
    return norm(r["author"]) + "|" + norm(r["title"])


def load_records():
    recs = []
    for fn in sorted(glob.glob(os.path.join(HERE, "batches", "p*.jsonl"))):
        for line in open(fn, encoding="utf-8"):
            line = line.strip()
            if line:
                r = json.loads(line)
                if not r.get("empty"):
                    recs.append(r)
    return recs


def load_cache():
    c = {}
    if os.path.exists(CACHE):
        for line in open(CACHE, encoding="utf-8"):
            try:
                d = json.loads(line)
                c[d["key"]] = d
            except Exception:
                pass
    return c


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    cache = load_cache()
    todo = {}
    for r in load_records():
        if r["year_start"] is None and not re.search(r"\d{2}", r["year"]):
            continue  # undated: not looked up
        k = key(r)
        if k not in cache and k not in todo:
            todo[k] = r
    items = list(todo.items())
    if args.limit:
        items = items[:args.limit]
    print(f"cached {len(cache)}, to do {len(items)}", flush=True)
    done = [0]

    def work(kr):
        k, r = kr
        try:
            res = lookup(r["author"], r["title"])
        except Exception as e:
            print("ERR", e, flush=True)
            return
        res.update(key=k, author=r["author"], title=r["title"])
        with lock:
            with open(CACHE, "a", encoding="utf-8") as f:
                f.write(json.dumps(res, ensure_ascii=False) + "\n")
            done[0] += 1
            if done[0] % 50 == 0:
                print(f"{done[0]}/{len(items)}", flush=True)

    with ThreadPoolExecutor(args.workers) as ex:
        list(ex.map(work, items))
    print("finished", done[0], flush=True)
