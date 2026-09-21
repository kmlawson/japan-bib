#!/usr/bin/env python3
"""Score the Online Books Page candidates in ob.jsonl against the entries they were searched for.

The Online Books Page lists freely readable copies held elsewhere (archive.org, Project Gutenberg,
Google Books, university libraries), so an accepted copy counts as `open`. HathiTrust copies were
dropped when the results were collected and are not considered here.

A candidate is taken automatically when the author's surname appears in the record, all the key words
of the entry's title appear in the listed title, and the dates agree within three years. Everything
else waits for a hand verdict in ob_decisions.tsv (id <TAB> key <TAB> yes|no|edition).

    ob_score.py [--review]
"""
import argparse, json, os, re, sys, unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "union-catalog-work"))
from ia_lookup import norm, main_title  # noqa: E402

SRC = os.path.join(HERE, "ob.jsonl")
DEC = os.path.join(HERE, "ob_decisions.tsv")
REVIEW = os.path.join(HERE, "ob_review.txt")
STOP = set("""a an the of on in to for and or at by with from as its his her their le la les du des et
    der die das und von zum zur tome vol volume""".split())


def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if not unicodedata.combining(c))


def keys(title):
    return [w for w in strip_accents(norm(main_title(title))).split() if w not in STOP and len(w) > 2]


def surname(author):
    a = (author or "").strip()
    if "," not in a:
        toks = strip_accents(norm(a)).split()
        return toks[-1] if 0 < len(toks) <= 3 else ""
    toks = strip_accents(norm(a.split(",")[0])).split()
    return toks[-1] if toks and len(toks) <= 3 else ""


def hit_year(h):
    ys = [int(y) for y in re.findall(r"(?<!\d)(1[6-9]\d\d|20[0-2]\d)(?!\d)", h.get("imprint") or "")]
    return min(ys) if ys else None


def entry_years(rec):
    ys = [int(y) for y in re.findall(r"(?<!\d)(1[6-9]\d\d|20[0-2]\d)(?!\d)", rec.get("year") or "")]
    return ys


def score(rec, h):
    """(points, reasons). 3 or more is taken automatically."""
    ek = keys(rec["title"])
    hk = set(strip_accents(norm(h.get("title") or "")).split())
    why, pts = [], 0
    if not ek or not h.get("copies"):
        return -9, ["no title words" if not ek else "no freely readable copy"]
    covered = [w for w in ek if w in hk]
    frac = len(covered) / len(ek)
    if frac == 1:
        pts += 2; why.append("all title words")
    elif frac >= 0.8:
        pts += 1; why.append(f"{len(covered)}/{len(ek)} title words")
    else:
        why.append(f"only {len(covered)}/{len(ek)} title words")
    sn = surname(rec.get("author") or "")
    hn = strip_accents(norm(h.get("author") or "")).split()
    if sn and sn in hn:
        pts += 1; why.append("author matches")
    elif sn:
        why.append("author not in record")
    hy, ey = hit_year(h), entry_years(rec)
    if hy and ey:
        if any(abs(hy - y) <= 3 for y in ey):
            pts += 1; why.append(f"year {hy}")
        else:
            pts -= 1; why.append(f"year {hy} vs {'/'.join(map(str, ey))}")
    elif hy:
        why.append(f"year {hy}, entry undated")
    else:
        why.append("no year in the imprint")
    return pts, why


def urls(h, n=2):
    """The copies to link, archive.org first (we can say how those may be read)."""
    cs = sorted(h.get("copies") or [], key=lambda c: "archive.org/details/" not in c["url"])
    out, seen = [], set()
    for c in cs:
        u = c["url"].split("#")[0]
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out[:n]


def decisions():
    d = {}
    if os.path.exists(DEC):
        for line in open(DEC, encoding="utf-8"):
            p = line.rstrip("\n").split("\t")
            if len(p) >= 3 and p[0].isdigit():
                d[(int(p[0]), p[1])] = p[2].strip().lower()
    return d


def best(rec):
    cand = [(h,) + tuple(score(rec, h)) for h in rec.get("hits") or []]
    cand = [c for c in cand if c[1] > -9]
    return max(cand, key=lambda c: c[1]) if cand else None


def accepted():
    """({id: (urls, title)}, {id: (urls, title, year)}): copies to link, and copies of another edition."""
    dec, links, other = decisions(), {}, {}
    for line in open(SRC, encoding="utf-8"):
        rec = json.loads(line)
        hand = False
        for h in rec.get("hits") or []:
            v = dec.get((rec["id"], h["key"]))
            if v in ("yes", "edition"):
                (links if v == "yes" else other)[rec["id"]] = (urls(h), h.get("title"), hit_year(h))
                hand = True
                break
        if hand:
            continue
        b = best(rec)
        if b and b[1] >= 3 and dec.get((rec["id"], b[0]["key"])) != "no":
            links[rec["id"]] = (urls(b[0]), b[0].get("title"), hit_year(b[0]))
    return links, other


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--review", action="store_true")
    args = ap.parse_args()
    recs = [json.loads(l) for l in open(SRC, encoding="utf-8")]
    strong, doubt = [], []
    for rec in recs:
        b = best(rec)
        if b:
            (strong if b[1] >= 3 else doubt).append((rec, b))
    print(f"{len(recs)} searched, {sum(1 for r in recs if r.get('hits'))} with candidates, "
          f"{len(strong)} strong, {len(doubt)} to look at by hand")
    if args.review:
        with open(REVIEW, "w", encoding="utf-8") as f:
            for rec, (h, p, why) in sorted(doubt, key=lambda x: -x[1][1]):
                f.write(f"id{rec['id']} [{p}] {rec.get('author') or '-'} | {rec['title']} | {rec.get('year')}\n")
                f.write(f"    -> {h.get('author','')[:60]} | {h['title'][:110]}\n       {h['imprint'][:110]}\n"
                        f"       {'; '.join(why)}\n")
                for u in urls(h, 4):
                    f.write(f"       {u}\n")
                f.write("\n")
        print("wrote", REVIEW)
