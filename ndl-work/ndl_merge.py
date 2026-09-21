#!/usr/bin/env python3
"""Merge the National Diet Library items (ndl.jsonl, made by ndl_fetch.py) into the rows built by
union-catalog-work/build_db.py.

The NDL link comes from the user's own browsing and is always kept, listed first and marked as checked.
An item already in the database (same author + title proper, years within 3) gains the link and the source
name instead of a new row; the fuller of the two descriptions is shown and the other is kept as a note.
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "next-bib-work"))
sys.path.insert(0, os.path.join(HERE, "..", "zotero-work"))
import merge as M  # noqa: E402
import zotero_merge as Z  # noqa: E402

SRC = "NDL Digital Collections"
ROLE = re.compile(r"\s*[\[［]?(著|編|訳|譯|撰|画|校訂|校閲|編纂|述|輯|共著|編著|編訳|編著者|監修|解説)+[\]］]?$")
LANG = {"eng": "English", "jpn": "Japanese", "fre": "French", "fra": "French", "ger": "German", "deu": "German",
        "ita": "Italian", "spa": "Spanish", "dut": "Dutch", "nld": "Dutch", "rus": "Russian", "lat": "Latin",
        "por": "Portuguese", "chi": "Chinese", "zho": "Chinese", "und": ""}


def clean_creator(c):
    """'[by] E. H. House' / 'Walter Henry Medhurst 著' -> a plain name."""
    c = ROLE.sub("", c.strip())
    c = re.sub(r"^\[?(by|ed\.? by|edited by|compiled by|translated by)\]?\s+", "", c, flags=re.I)
    return c.strip(" .,;[]")


def latin(s):
    """Is the name written in the Latin alphabet? (A Japanese-script heading must not replace a Latin one.)"""
    letters = [c for c in s if c.isalpha()]
    return bool(letters) and sum(c.isascii() or "\u00c0" <= c <= "\u024f" for c in letters) / len(letters) > 0.7


def author_of(r):
    """Prefer the authority heading ('House, Edward Howard, 1836-1901'), which is already inverted."""
    if r.get("creator_headings"):
        return "; ".join(re.sub(r",\s*\d{4}-?\d{0,4}$", "", h).strip() for h in r["creator_headings"][:3])
    names = [Z.invert(clean_creator(c)) for c in r.get("creators", [])[:3]]
    return "; ".join(n for n in names if n)


ERA = {"明治": 1867, "大正": 1911, "昭和": 1925, "慶応": 1864, "元治": 1863, "文久": 1860, "万延": 1859, "安政": 1853}
KANJI = {"元": 1, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}


def _kanji_num(s):
    if s.isdigit():
        return int(s)
    if "十" in s:
        a, _, b = s.partition("十")
        return (KANJI.get(a, 1) if a else 1) * 10 + (KANJI.get(b, 0) if b else 0)
    return KANJI.get(s, 0)


ERA_RE = re.compile(r"(明治|大正|昭和|慶応|元治|文久|万延|安政)\s*([0-9]+|元|[一二三四五六七八九十]+)\s*年?")


def to_western(text):
    """'大正6' -> '1917', '昭和12.8' -> '1937.8'; anything that is not an era date is left alone."""
    def sub(m):
        n = _kanji_num(m.group(2))
        return str(ERA[m.group(1)] + n) if n else m.group(0)
    return ERA_RE.sub(sub, text or "")


def year_of(r):
    """Gregorian year: from any of the dcterms:issued values, or converted from a Japanese era date."""
    for v in (r.get("issued_all") or []) + [r.get("issued", "")]:
        m = re.search(r"(?<!\d)(1[5-9]\d\d|20[0-2]\d)(?!\d)", v)
        if m:
            return int(m.group(1))
    for v in (r.get("issued_all") or []) + [r.get("issued", "")]:
        m = re.search(r"(明治|大正|昭和|慶応|元治|文久|万延|安政)\s*([0-9]+|元|[一二三四五六七八九十]+)", v)
        if m:
            n = _kanji_num(m.group(2))
            if n:
                return ERA[m.group(1)] + n
    return None


def access_map():
    """pid -> open | limited, from ndl_access.py (checked against NDL Search, which words the rights plainly)."""
    fn = os.path.join(HERE, "ndl_access.jsonl")
    d = {}
    if os.path.exists(fn):
        for line in open(fn, encoding="utf-8"):
            try:
                r = json.loads(line)
                d[r["pid"]] = r
            except Exception:
                pass
    return d


DESIG = re.compile(r"[^\w]*(?:巻|vol\.?|v\.|no\.|pt\.?|第)?\s*[\dIVXivx一二三四五六七八九十]+\s*(?:巻|編|輯|冊)?[^\w]*\Z", re.I)


def split_volume(z):
    """The NDL 'volume' field holds either a plain designation ('巻1', '1925') or the title of the part
    ('MOMOTARO The Story of Peach-Boy'). Returns (designation, part title)."""
    v = (z.get("volume") or "").strip()
    if not v:
        return "", ""
    w = to_western(v)
    if re.fullmatch(r"\[?\d{4}\]?年?", w) and (z["year_num"] is None or str(z["year_num"]) in to_western(z["year"])):
        return "", ""  # only repeats the date
    if DESIG.fullmatch(v):
        return v, ""
    return "", v


# Notes added by hand to a National Diet Library record, where the compiler knows something the
# catalogue does not say: pid -> {"note": ...} (and "title" if the catalogue title has to be replaced).
BY_HAND = {
    "1028324": {"note": 'The compiler cites this volume as "Glimpses of East Asia"; the yearbook carries '
                        'English text alongside the Japanese (the catalogue notes 英文併記).'},
}


def load():
    out, seen = [], set()
    acc = access_map()
    fn = os.path.join(HERE, "ndl.jsonl")
    if not os.path.exists(fn):
        return out
    for line in open(fn, encoding="utf-8"):
        r = json.loads(line)
        if r.get("error") or r["pid"] in seen or not r.get("title"):
            continue
        seen.add(r["pid"])
        r["author"] = author_of(r)
        r["year_num"] = year_of(r)
        printed = r.get("issued") or ""
        r["year"] = to_western(printed) or "n.d."
        r["year_printed"] = printed if r["year"] != printed else ""
        r["designation"], part = split_volume(r)
        if part and M.norm(part) not in M.norm(r["title"]):
            r["title"] = r["title"].rstrip(" .") + ". " + part
        hand = BY_HAND.get(r["pid"], {})
        if hand.get("title"):
            r["title"] = hand["title"]
        if hand.get("note"):
            r["descriptions"] = list(r.get("descriptions") or []) + [hand["note"]]
        a = acc.get(r["pid"])
        r["access"] = (a or {}).get("access", "unknown")
        r["access_words"] = "; ".join((a or {}).get("rights", []))
        out.append(r)
    return out


def describe(r):
    parts = []
    imprint = ", ".join(x for x in (r.get("place"), r.get("publisher")) if x)
    if imprint:
        parts.append("Imprint: " + imprint)
    if r.get("extent"):
        parts.append("Extent: " + r["extent"])
    if r.get("series"):
        parts.append("Series: " + r["series"])
    lang = LANG.get(r.get("language", ""), r.get("language", ""))
    if lang:
        parts.append("Language: " + lang)
    subj = [s for s in r.get("subjects", []) if not re.fullmatch(r"[A-Z0-9-]{1,10}", s)]
    if subj:
        parts.append("Subjects: " + "; ".join(subj[:8]))
    extra = [c for c in r.get("creators", []) if clean_creator(c) and clean_creator(c) not in r["author"]]
    if extra:
        parts.append("Statement of responsibility: " + "; ".join(extra[:3]))
    if r.get("descriptions"):
        parts.append("Note: " + "; ".join(r["descriptions"][:4]))
    if r.get("year_printed"):
        parts.append("Date as printed: " + r["year_printed"])
    parts.append(f"{SRC} pid {r['pid']}")
    return parts


def fullness(r):
    return sum(bool(x) for x in (r["author"], r["title"], r["year_num"], r.get("edition"), r.get("volume"),
                                 r.get("publisher"), r.get("place"), r.get("extent"), r.get("series"),
                                 r.get("descriptions")))


def apply(rows, last_year=None):
    """Adds/merges the NDL items. Returns {url: access} for the links (all openly readable at the NDL)."""
    idx = M.Index()
    for i, r in enumerate(rows):
        if r[9] in ("book", "periodical"):
            idx.add(M.item(M.sur(r[0]), r[1], r[3], "book", i))
    checked, stats, skipped, skipped_limited = {}, {"merged": 0, "new": 0, "ndl_fuller": 0}, [], []
    for z in load():
        if last_year is not None and z["year_num"] is not None and not (1850 <= z["year_num"] <= last_year):
            skipped.append((z["pid"], z["year"], z["title"][:60]))
            continue
        if z["access"] == "limited":
            # readable only inside the library or by registered transmission: not offered as an online copy
            skipped_limited.append((z["pid"], z["access_words"], z["title"][:50]))
            continue
        checked[z["url"]] = "open"
        su, tk, full = M.sur(z["author"]), M.tkey(z["title"]), M.norm(z["title"])
        h = idx.find(su, tk, full, z["year_num"], "book")
        if h is None and su:
            for other_su in list(idx.b):
                if other_su and other_su != su and other_su[0] == su[0] and M.difflib.SequenceMatcher(None, su, other_su).ratio() >= 0.8:
                    h = idx.find(other_su, tk, full, z["year_num"], "book")
                    if h:
                        break
        if h is None and len(tk) >= 20 and z["year_num"] is not None:
            h = idx.exact(tk, full, z["year_num"], "book")
        if h is not None and not Z.titles_agree(z["title"], z["author"], rows[h["ref"]][1], rows[h["ref"]][0], strict=True):
            h = None
        desc = describe(z)
        if h is None:
            rows.append([z["author"], z["title"], z["year"], z["year_num"], z.get("edition", ""), z["designation"],
                         z["url"], " | ".join(desc), SRC, "book"])
            idx.add(M.item(su, z["title"], z["year_num"], "book", len(rows) - 1))
            stats["new"] += 1
            continue
        r = rows[h["ref"]]
        if z["url"] not in (r[6] or "").split("\n"):
            r[6] = "\n".join([z["url"]] + [u for u in (r[6] or "").split("\n") if u])
        if SRC not in r[8]:
            r[8] += "; " + SRC
        line = ". ".join(x for x in (z["author"], z["title"], ", ".join(y for y in (z.get("place"), z.get("publisher"), z["year"]) if y)) if x)
        if z["author"] and not latin(z["author"]) and r[0] and latin(r[0]):
            desc.insert(0, "Author (NDL heading): " + z["author"])
        if fullness(z) > Z.fullness_row(r) and "Description from " + SRC not in r[7]:
            old = ". ".join(x for x in (r[0], r[1], r[4], r[2]) if x)
            r[0] = z["author"] if z["author"] and (latin(z["author"]) or not latin(r[0])) else r[0]
            r[1], r[2] = z["title"], z["year"]
            r[3] = z["year_num"] if z["year_num"] is not None else r[3]
            r[5] = r[5] or z["designation"]
            r[7] = " | ".join(desc + [f"Description from {SRC}; entered elsewhere as: {old}", r[7]])
            stats["ndl_fuller"] += 1
        else:
            r[7] += f" | Also in {SRC} (pid {z['pid']}): {line}"
        stats["merged"] += 1
    print("NDL:", stats, "| links", len(checked), "| outside 1850-%s: %d" % (last_year, len(skipped)),
          "| not readable online: %d" % len(skipped_limited))
    for s in skipped_limited:
        print("   limited", s)
    for s in skipped:
        print("   skipped", s)
    return checked
