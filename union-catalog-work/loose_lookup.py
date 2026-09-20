#!/usr/bin/env python3
"""Second, looser archive.org pass for the records that got no same-book link from the strict pass.

Search on the key words of the title proper only (no creator), limited to items dated within 4 years of
the entry; candidates are stored with word-coverage figures so that they can be classified afterwards
(loose_classify.py) and the edge cases reviewed by hand. Resumable; cache = ia_loose.jsonl.

Run with the interpreter that has the `internetarchive` package (the one behind the `ia` command):
    $(head -1 $(which ia) | sed 's/^#!//') loose_lookup.py [--workers 5]
"""
import argparse, difflib, json, os, re, sys, threading, time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "next-bib-work"))
from ia_lookup import load_records, load_cache, key, norm, main_title, STOP, surname  # noqa: E402
from build_list import in_range, years, ia_matches, ia_other_editions  # noqa: E402

LOOSE = os.path.join(HERE, "ia_loose.jsonl")
TOL4 = 4
lock = threading.Lock()
CUT = re.compile(r",\s+(?:trs?\.|ed\.|rev\.|illus\.|with |foreword|introduction|preface|préface|compiled|adapted|authorized|pub\.|"
                 r"from the |avec |traduits?|übersetzt|aus dem |mit |collotypes)|\s+\((?:formerly|traduction)", re.I)


def title_proper(t):
    t = CUT.split(t)[0]
    return main_title(re.sub(r"\s+\.\s\.\s\.\s*", " ", t))


def sig(t):
    return [w for w in norm(t).split() if w not in STOP and (len(w) > 2 or w.isdigit())]


def tok_eq(a, b):
    if a == b:
        return True
    if a.isdigit() or b.isdigit():
        return False
    if min(len(a), len(b)) >= 5 and (a.startswith(b) or b.startswith(a)):
        return True
    return min(len(a), len(b)) >= 4 and difflib.SequenceMatcher(None, a, b).ratio() >= 0.84


def cover(ws, pool):
    return sum(1 for w in ws if any(tok_eq(w, p) for p in pool)) / len(ws) if ws else 0.0


def cand_main(t):
    """Title proper of an archive.org title: up to the first ' : ', ';', ' / ' or ' - '."""
    return re.split(r"\s[:/]\s|;|\s[-–—]\s|\s?:\s", t, maxsplit=1)[0]


def search(q):
    import internetarchive as ia
    for attempt in range(4):
        try:
            return list(ia.search_items(q, fields=["identifier", "title", "creator", "year", "date"],
                                        params={"rows": 100}, max_retries=3).iter_as_results())[:100]
        except Exception as e:  # network hiccup / rate limit
            err = e
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"search failed: {q!r}: {err}")


def cyear(c):
    y = c.get("year")
    if not y and c.get("date"):
        m = re.match(r"(\d{4})", str(c["date"]))
        y = m.group(1) if m else None
    try:
        return int(y)
    except Exception:
        return None


def lookup(author, title, ys):
    tp = title_proper(title)
    ws = sig(tp)
    if not ws or not ys:
        return {"queries": [], "cands": []}
    yq = " OR ".join(f"year:[{y - TOL4} TO {y + TOL4}]" for y in sorted(set(ys)))
    qs = [" ".join(ws[:5])]
    if len(ws) >= 4:
        qs.append(" ".join(sorted(set(ws[:6]), key=lambda w: (-len(w), w))[:3]))
    sn, full = surname(author), sig(title)
    seen, cands, used = set(), [], []
    for words in qs:
        q = f"title:({words}) AND ({yq}) AND mediatype:texts"
        used.append(q)
        for c in search(q):
            if c["identifier"] in seen:
                continue
            seen.add(c["identifier"])
            ct = c.get("title") or ""
            ct = ct[0] if isinstance(ct, list) else ct
            cr = c.get("creator") or ""
            cr = "; ".join(cr) if isinstance(cr, list) else cr
            cw, cm = sig(ct), sig(cand_main(ct))
            cov_r = cover(ws[:8], cw)
            if cov_r < 0.6:
                continue
            auth = None
            if sn:
                auth = any(tok_eq(sn, w) for w in norm(cr + " " + ct).split()) if (cr or sn in norm(ct)) else None
            cands.append({"identifier": c["identifier"], "title": ct, "creator": cr, "year": cyear(c),
                          "cov_r": round(cov_r, 2), "cov_c": round(cover(cm, full), 2), "auth": auth})
        if any(c["cov_r"] >= 0.8 and c["cov_c"] >= 0.8 for c in cands):
            break
    cands.sort(key=lambda c: (-(c["cov_r"] + c["cov_c"] + (0.3 if c["auth"] else 0)), c["identifier"]))
    return {"queries": used, "cands": cands[:15], "nwords": len(ws)}


def load_loose():
    d = {}
    if os.path.exists(LOOSE):
        for line in open(LOOSE, encoding="utf-8"):
            try:
                x = json.loads(line)
                d[x["key"]] = x
            except Exception:
                pass
    return d


def targets():
    """(key, author, title, years) for every dated book/periodical that has no archive.org candidate at all yet."""
    out, cache = {}, load_cache()
    for r in load_records():
        if in_range(r) and not ia_matches(r, cache) and not ia_other_editions(r, cache):
            out.setdefault("uc|" + key(r), (r["author"], r["title"], [y for y in years(r) if 1840 <= y <= 1965]))
    import merge as M
    c2 = M.load_cache2()
    _, new = M.merge(M.uc_rows_from_db())
    for r in new:
        if M.wants_lookup(r) and not any(M.split_matches(r, c2)):
            ys = M.rec_years(r) if r["type"] != "periodical" else [y for y in M.rec_years(r)]
            out.setdefault("new|" + M.lkey(r), (re.sub(r"\s*\([^)]*\)", "", r["author"]), r["title"], ys))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    done_keys = load_loose()
    todo = [(k, v) for k, v in targets().items() if k not in done_keys]
    if args.limit:
        todo = todo[:args.limit]
    print(f"cached {len(done_keys)}, to do {len(todo)}", flush=True)
    n = [0]

    def work(kv):
        k, (author, title, ys) = kv
        try:
            res = lookup(author, title, ys)
        except Exception as e:
            print("ERR", e, flush=True)
            return
        res.update(key=k, author=author, title=title, years=ys)
        with lock:
            with open(LOOSE, "a", encoding="utf-8") as f:
                f.write(json.dumps(res, ensure_ascii=False) + "\n")
            n[0] += 1
            if n[0] % 100 == 0:
                print(f"{n[0]}/{len(todo)}", flush=True)

    with ThreadPoolExecutor(args.workers) as ex:
        list(ex.map(work, todo))
    print("finished", n[0], flush=True)
