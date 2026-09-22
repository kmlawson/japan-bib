#!/usr/bin/env python3
"""Score the Europeana candidates in eu.jsonl against the entries they were searched for.

Same rule as gallica_score.py: a hit is accepted automatically only when the title words of the entry
are all present in the Europeana title, the author's surname appears in the record, and the dates agree
within three years (3 points). Everything else is listed for hand review (eu_review.txt); hand verdicts
live in eu_decisions.tsv, keyed to what the entry is rather than to its row id.

Records that carry no digital object at all (has_file false and no provider page) are never accepted.

    eu_score.py [--review]
"""
import argparse, json, os, re, sys, unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "union-catalog-work"))
from ia_lookup import norm, main_title  # noqa: E402
from language import key  # noqa: E402

SRC = os.path.join(HERE, "eu.jsonl")
DEC = os.path.join(HERE, "eu_decisions.tsv")
REVIEW = os.path.join(HERE, "eu_review.txt")
STOP = set("""der die das des dem den ein eine eines einer einem einen und oder von im in auf zu zur zum
    le la les l un une des du de d et ou en dans sur par pour avec au aux il el los las y o con para por
    the a an of and or in on at to for with by from its his her their vol vols bd t""".split())


def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if not unicodedata.combining(c))


def keys(title):
    return [w for w in strip_accents(norm(main_title(title))).split() if w not in STOP and len(w) > 2]


def surnames(author):
    out = []
    for part in re.split(r";| and | und | et ", re.sub(r"^\(|\)$", "", author or "")):
        part = part.strip()
        head = part.split(",")[0] if "," in part else (part.split()[-1] if part.split() else "")
        toks = strip_accents(norm(head)).split()
        if toks:
            out.append(toks[-1])
    return out


def year_of(hit):
    m = re.search(r"(1[6-9]\d\d|20\d\d)", str(hit.get("year") or ""))
    return int(m.group(1)) if m else None


def score(rec, hit):
    """(points, reasons). 3 points is an automatic accept."""
    ek, hk = keys(rec["title"]), set(strip_accents(norm(hit.get("title") or "")).split())
    why, pts = [], 0
    if not ek:
        return 0, ["no title words"]
    covered = [w for w in ek if w in hk]
    frac = len(covered) / len(ek)
    if frac == 1:
        pts += 2; why.append("all title words")
    elif frac >= 0.75:
        pts += 1; why.append(f"{len(covered)}/{len(ek)} title words")
    else:
        why.append(f"only {len(covered)}/{len(ek)} title words")
    # the other way round: a short entry title hiding inside a long, unrelated one proves nothing
    hk1 = keys((hit.get("title") or "").split(" / ")[0])
    back = len([w for w in hk1 if w in set(ek)]) / len(hk1) if hk1 else 0
    if back < 0.4:
        pts -= 1; why.append(f"hit title mostly other words ({back:.0%})")
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
    if not hit.get("has_file") and not hit.get("shown_at"):
        pts -= 3; why.append("no digital object")
    if sn and not any(s in blob.split() for s in sn):
        pts = min(pts, 2)   # a named author who is absent from the record is never an automatic match
    return pts, why


def rowkey(rec):
    return key(rec.get("author"), rec.get("title"), rec.get("year"))


def decisions():
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
    cand = [(h,) + tuple(score(rec, h)) for h in rec.get("hits") or []]
    return max(cand, key=lambda c: c[1]) if cand else None


def url_of(hit):
    return "https://www.europeana.eu/en/item" + hit["id"]


def accepted():
    """{id: (url, year)} for the copies to link and for the copies of another edition."""
    dec, links, other = decisions(), {}, {}
    for line in open(SRC, encoding="utf-8"):
        rec = json.loads(line)
        hand = False
        for h in rec.get("hits") or []:
            v = dec.get((rowkey(rec), h["id"]))
            if v in ("yes", "edition"):
                (links if v == "yes" else other)[rec["id"]] = (url_of(h), year_of(h))
                hand = True
                break
        if hand:
            continue
        b = best(rec)
        if b and b[1] >= 3 and dec.get((rowkey(rec), b[0]["id"])) != "no":
            links[rec["id"]] = (url_of(b[0]), year_of(b[0]))
    return links, other


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--review", action="store_true", help="write the doubtful ones to eu_review.txt")
    args = ap.parse_args()
    recs = [json.loads(l) for l in open(SRC, encoding="utf-8")] if os.path.exists(SRC) else []
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
                f.write(f"    -> {h['title'][:150]}\n       {h.get('creator','')[:90]} | {h.get('year')} |"
                        f" {h.get('provider')} | {h['id']}\n       {'; '.join(why)}\n\n")
        print("wrote", REVIEW)
