#!/usr/bin/env python3
"""Build ../list.md (dated 1850-1955 books, with IA links) and ../list-undated.md from batches/*.jsonl."""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ia_lookup import load_records, load_cache, key, fold, HERE, surname, norm

OUT = os.path.join(HERE, "..", "list.md")
OUT_ND = os.path.join(HERE, "..", "list-undated.md")
FIRST, LAST = 11, 553


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
    return min(ys) <= 1955 and max(ys) >= 1850


def ia_matches(r, cache):
    """Filtered archive.org candidates for a record: None = not searched, [] = no match."""
    c = cache.get(key(r))
    if c is None:
        return None
    ys = set(years(r))
    ms = c["matches"]
    if not surname(r["author"]):
        # no personal-author check was possible: keep only items whose year fits, or long exact titles
        nwords = len(norm(r["title"]).split())
        ms = [m for m in ms if (m["year"] is not None and any(abs(m["year"] - y) <= 2 for y in ys))
              or (nwords >= 6 and m["score"] >= 0.97 and (m["year"] is None or m["year"] <= 1960))]
    return sorted(ms, key=lambda m: (m["year"] not in ys, -m["score"]))[:6]


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
            s += "  \n  IA: " + " · ".join(
                f"[{m['identifier']}](https://archive.org/details/{m['identifier']})"
                + (f" ({m['year']})" if m["year"] else "") for m in ms)
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
