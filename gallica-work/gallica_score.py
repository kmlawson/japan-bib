#!/usr/bin/env python3
"""Score the Gallica candidates in gallica.jsonl against the entries they were searched for.

A hit is accepted automatically only when the title words of the entry are all present in the
Gallica title, the author's surname appears in the record, and the dates agree within three years.
Everything else is listed for hand review (gallica_review.txt); hand verdicts live in
gallica_decisions.tsv, keyed to what the entry is rather than to its row id.

    gallica_score.py [--review]
"""
import argparse, json, os, re, sys, unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "union-catalog-work"))
from ia_lookup import norm, main_title  # noqa: E402

SRC = os.path.join(HERE, "gallica.jsonl")
DEC = os.path.join(HERE, "gallica_decisions.tsv")
REVIEW = os.path.join(HERE, "gallica_review.txt")
STOP = set("""le la les l un une des du de d au aux et ou en dans sur sous par pour avec sans chez
    a son sa ses ce cet cette leur leurs notre nos ils est sont tome vol volume""".split())


def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if not unicodedata.combining(c))


def keys(title):
    ws = [w for w in strip_accents(norm(main_title(title))).split() if w not in STOP and len(w) > 2]
    return ws


def surnames(author):
    """The surnames of an entry heading: the part before the first comma of each name."""
    out = []
    for part in re.split(r";| and ", author or ""):
        part = part.strip()
        if "," in part:
            head = part.split(",")[0]
        else:
            head = part.split()[-1] if part.split() else ""
        toks = strip_accents(norm(head)).split()
        if toks:
            out.append(toks[-1])
    return out


def year_of(hit):
    m = re.search(r"(1[6-9]\d\d|20\d\d)", hit.get("date") or "")
    return int(m.group(1)) if m else None


def score(rec, hit):
    """(points, reasons). 3 points is an automatic accept."""
    ek, hk = keys(rec["title"]), set(strip_accents(norm(hit.get("title") or "")).split())
    why = []
    if not ek:
        return 0, ["no title words"]
    covered = [w for w in ek if w in hk]
    frac = len(covered) / len(ek)
    pts = 0
    if frac == 1:
        pts += 2; why.append("all title words")
    elif frac >= 0.75:
        pts += 1; why.append(f"{len(covered)}/{len(ek)} title words")
    else:
        why.append(f"only {len(covered)}/{len(ek)} title words")
    blob = strip_accents(norm((hit.get("creator") or "") + " " + (hit.get("title") or "")))
    sn = surnames(rec.get("author") or "")
    if sn and any(s in blob.split() for s in sn):
        pts += 1; why.append("author matches")
    elif sn:
        why.append("author not in record")
    hy, ey = year_of(hit), rec.get("year_num")
    if hy and ey:
        if abs(hy - ey) <= 3:
            pts += 1; why.append(f"year {hy}")
        else:
            pts -= 1; why.append(f"year {hy} vs {ey}")
    elif hy:
        why.append(f"year {hy}, entry undated")
    if (hit.get("type") or "").lower() not in ("text", ""):
        pts -= 1; why.append("not a text")
    if "domaine public" not in (hit.get("rights") or "") and "public domain" not in (hit.get("rights") or ""):
        why.append("rights: " + (hit.get("rights") or "none stated"))
    return pts, why


def rowkey(rec):
    """What the entry is, folded to letters and digits: a verdict keyed this way holds however the
    database is renumbered, and covers a second search of the same book."""
    sys.path.insert(0, os.path.join(HERE, "..", "union-catalog-work"))
    from language import key
    return key(rec.get("author"), rec.get("title"), rec.get("year"))


def decisions():
    """{(key, ark): yes|no|edition}"""
    d = {}
    if os.path.exists(DEC):
        for line in open(DEC, encoding="utf-8"):
            if line.startswith("#"):
                continue
            p = line.rstrip("\n").split("\t")
            if len(p) >= 3 and p[0].strip():
                d[(p[0].strip(), p[1].strip())] = p[2].strip().lower()
    return d


def best(rec):
    """(hit, points, why) for the highest-scoring candidate of an entry, or None."""
    cand = [(h,) + tuple(score(rec, h)) for h in rec.get("hits") or []]
    return max(cand, key=lambda c: c[1]) if cand else None


def accepted():
    """Two dictionaries keyed by entry id: the copies to link ({id: (ark, year)}) and the copies of
    another edition ({id: (ark, year)}). A hand verdict in gallica_decisions.tsv always wins; without
    one, a candidate scoring 3 or more is taken as the same work."""
    dec, links, other = decisions(), {}, {}
    for line in open(SRC, encoding="utf-8"):
        rec = json.loads(line)
        hand = False
        for h in rec.get("hits") or []:
            v = dec.get((rowkey(rec), h["ark"]))
            if v in ("yes", "edition"):
                (links if v == "yes" else other)[rec["id"]] = (h["ark"], year_of(h))
                hand = True
                break
        if hand:
            continue
        b = best(rec)
        if b and b[1] >= 3 and dec.get((rowkey(rec), b[0]["ark"])) != "no":
            links[rec["id"]] = (b[0]["ark"], year_of(b[0]))
    return links, other


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--review", action="store_true", help="write the doubtful ones to gallica_review.txt")
    args = ap.parse_args()
    recs = [json.loads(l) for l in open(SRC, encoding="utf-8")]
    strong, doubt = [], []
    for rec in recs:
        b = best(rec)
        if not b:
            continue
        (strong if b[1] >= 3 else doubt).append((rec, b))
    print(f"{len(recs)} searched, {len(strong)} strong, {len(doubt)} to look at by hand")
    if args.review:
        with open(REVIEW, "w", encoding="utf-8") as f:
            for rec, (h, p, why) in sorted(doubt, key=lambda x: -x[1][1]):
                f.write(f"id{rec['id']} [{p}] {rec.get('author') or '-'} | {rec['title']} | {rec.get('year')}\n")
                f.write(f"    -> {h['title'][:150]}\n       {h.get('creator','')[:90]} | {h.get('date')} |"
                        f" {h.get('rights')} | {h['ark']}\n       {'; '.join(why)}\n")
                for o in (rec.get("hits") or [])[:4]:
                    if o["ark"] != h["ark"]:
                        f.write(f"    .  {o['title'][:110]} | {o.get('date')} | {o['ark']}\n")
                f.write("\n")
        print("wrote", REVIEW)
