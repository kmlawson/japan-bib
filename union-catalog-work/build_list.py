#!/usr/bin/env python3
"""Build ../list.md (dated 1850-1950 books, with IA links) and ../list-undated.md from batches/*.jsonl."""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ia_lookup import load_records, load_cache, key, fold, HERE, surname, norm

OUT = os.path.join(HERE, "..", "list.md")
OUT_ND = os.path.join(HERE, "..", "list-undated.md")
FIRST, LAST = 11, 553
LAST_YEAR = 1950  # works first published 1850-1950 (the sources were transcribed to 1955/1960)


def years(r):
    ys = [int(y) for y in re.findall(r"(?<!\d)(1[5-9]\d\d)(?!\d)", r["year"])]
    if r["year_start"] is not None:
        ys.append(r["year_start"])
    m = re.search(r"(1[89])(\d\d)\s*[-–]\s*(\d{1,2})(?!\d)", r["year"])  # 1874-75, 1905-6
    if m:
        a = int(m.group(1) + m.group(2))
        tail = m.group(3)
        ys.append(int(str(a)[:4 - len(tail)] + tail))
    return ys


def in_range(r):
    ys = years(r)
    if not ys:
        return None  # undated
    return min(ys) <= LAST_YEAR and max(ys) >= 1850


_ACC = None


def access_of(identifier):
    """open | borrow | restricted | unknown - from the access check in next-bib-work/ia_access/part*.jsonl"""
    global _ACC
    if _ACC is None:
        import glob
        _ACC = {}
        for fn in sorted(glob.glob(os.path.join(HERE, "..", "next-bib-work", "ia_access", "part*.jsonl"))):
            for line in open(fn, encoding="utf-8"):
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                a = {"open": "open", "borrow": "borrow"}.get(d.get("access"), "restricted")
                if a == "restricted" and d.get("inlibrary"):
                    a = "borrow"  # in the lending collection; the search index just had no lending status for it
                _ACC[d["identifier"]] = a
    return _ACC.get(identifier, "unknown")


def usable(m):
    """An item that can be neither read nor borrowed (print-disabled only, dark, removed) is not offered at all."""
    return access_of(m["identifier"]) != "restricted"


TOL = 3  # archive.org items dated within 3 years of the catalogue entry are taken to be the same book


def _split(r, cache):
    c = cache.get(key(r))
    if c is None:
        return None, []
    ys = set(years(r))
    personal = bool(surname(r["author"]))
    nwords = len(norm(r["title"]).split())
    same, other = [], []
    for m in c["matches"]:
        if not usable(m):
            continue
        y = m["year"]
        if y is not None and any(abs(y - x) <= TOL for x in ys):
            same.append(m)
        elif y is None:
            # undated item: the creator check (personal author) or a long exact title has to carry it
            if personal or (nwords >= 6 and m["score"] >= 0.97):
                same.append(m)
        elif personal and m.get("creator"):
            other.append(m)  # same author and title, another date: a different edition
    same.sort(key=lambda m: (m["year"] not in ys, m["year"] is None, -m["score"]))
    other.sort(key=lambda m: (-m["score"], m["year"]))
    return same[:6], other[:6]


_LOOSE = None


def loose_matches(k):
    """Items accepted from the looser second pass (title key words, +-4 years; see loose_classify.py)."""
    global _LOOSE
    if _LOOSE is None:
        from loose_classify import accepted
        _LOOSE = accepted()
    return [m for m in _LOOSE.get(k, []) if usable(m)]


def ia_matches(r, cache):
    """archive.org items taken to be this book: None = not searched, [] = none."""
    same, other = _split(r, cache)
    if same is not None and not same and not other:
        return loose_matches("uc|" + key(r))
    return same


def is_loose(r, cache):
    same, other = _split(r, cache)
    return same is not None and not same and not other and bool(loose_matches("uc|" + key(r)))


def ia_other_editions(r, cache):
    """archive.org items with the same author and title but dated more than TOL years away."""
    return _split(r, cache)[1]


def fmt(r, cache, links=True):
    parts = []
    star = "\\* " if r["rare"] else ""
    head = f"**{r['author'].rstrip()}** " if r["author"].strip() else ""
    imprint = ", ".join(x for x in [r["place"], r["publisher"], r["year"]] if x)
    s = f"- {star}{head}*{r['title'].strip()}*"
    if r["edition"]:
        s += f" {r['edition']}"
    if imprint:
        s += f" {imprint}."
    if r["extent"]:
        s += f" {r['extent']}"
    if r["series"]:
        s += f" ({r['series']})"
    tail = []
    if r["holdings"]:
        tail.append("Holdings: " + " ".join(r["holdings"]))
    tail.append(f"cat. p. {r['printed_page'] or '?'}")
    s += "  \n  " + " · ".join(tail)
    if r["note"]:
        s += f"  \n  Note: {r['note']}"
    if links:
        ms = ia_matches(r, cache)
        if ms is None:
            s += "  \n  IA: (not yet searched)"
        elif not ms:
            s += "  \n  IA: no match found"
        else:
            s += ("  \n  IA (loose title match): " if is_loose(r, cache) else "  \n  IA: ") + " · ".join(
                f"[{m['identifier']}](https://archive.org/details/{m['identifier']})"
                + (f" ({m['year']})" if m["year"] else "") for m in ms)
        oth = ia_other_editions(r, cache)
        if oth:
            s += "  \n  IA, other editions: " + " · ".join(
                f"[{m['identifier']}](https://archive.org/details/{m['identifier']}) ({m['year']})" for m in oth)
    return s


def letter(r):
    h = fold((r["author"] or r["title"]).lstrip("*[\"'( ")).upper()
    return h[0] if h and h[0].isalpha() else "#"


if __name__ == "__main__":
    recs, cache = load_records(), load_cache()
    dated = [r for r in recs if in_range(r)]
    undated = [r for r in recs if in_range(r) is None]
    pages = {int(re.search(r"p(\d+)", f).group(1)) for f in os.listdir(os.path.join(HERE, "batches")) if f.endswith(".jsonl")}
    searched = sum(1 for r in dated if key(r) in cache)
    lines = [(letter(r), fmt(r, cache)) for r in dated]
    found = sum(1 for _, t in lines if "IA: [" in t)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("# Union Catalog of Books on Japan in Western Languages — books published 1850–1955\n\n")
        f.write("Transcribed by eye (no OCR) from the scan of the reprint edition (ed. Naomi Fukuda). "
                "Entries are in catalogue order; `\\*` marks a book the catalogue flags as rare. "
                "Holdings codes: IHJ International House Library, KBS Kokusai Bunka Shinkokai, NDL National Diet Library, "
                "TY Toyo Bunko, Ueno (Ueno Library). IA links are archive.org items whose title/creator match the entry "
                "(found with `ia search`); the year in parentheses is the IA item's year, matching-year items first. "
                "They are candidates, not verified identical editions.\n\n")
        f.write(f"Status: {len(pages)}/{LAST - FIRST + 1} catalogue pages transcribed · {len(dated)} entries · "
                f"IA searched {searched}, with match {found}. Undated entries are in `list-undated.md`.\n")
        cur = None
        for L, t in lines:
            if L != cur:
                f.write(f"\n## {L}\n\n")
                cur = L
            f.write(t + "\n")
    with open(OUT_ND, "w", encoding="utf-8") as f:
        f.write("# Union Catalog — undated (n.d.) book entries\n\nNot searched on archive.org.\n\n")
        for r in undated:
            f.write(fmt(r, cache, links=False) + "\n")
    print(f"pages {len(pages)}, dated {len(dated)}, undated {len(undated)}, dropped {len(recs) - len(dated) - len(undated)}, searched {searched}, found {found}")
