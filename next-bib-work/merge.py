#!/usr/bin/env python3
"""Merge Borton (1954) and Henshall (2014) records into the Union Catalog rows, minimising duplicates.

Same work = same author surname (or both anonymous) + matching title proper + publication years no
more than TOL (3) years apart. A new record that matches an existing row adds its source name and a
cross-reference to that row instead of creating a new one. New records are also de-duplicated among
themselves (Borton first, then Henshall).

    merge.py            report what would be merged / added (no network, writes nothing but dedup_report.tsv)
    merge.py --todo     list the new books that still need an archive.org lookup
"""
import difflib, glob, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "union-catalog-work"))
from ia_lookup import norm, main_title  # noqa: E402

TOL = 3
SRC_BORTON = "Borton (1954)"
SRC_HENSHALL = "Henshall (2014)"
CACHE2 = os.path.join(HERE, "ia_cache2.jsonl")
EXCLUDE_HENSHALL = [("duus", "abacus")]  # Henshall misprints 1955 for 1995


def load_new():
    """All full records from both new sources, tagged with src; Borton first."""
    out = []
    for fn in sorted(glob.glob(os.path.join(HERE, "borton", "p*.jsonl"))):
        for line in open(fn, encoding="utf-8"):
            if line.strip():
                r = json.loads(line)
                if r.get("empty") or "skipped" in r:
                    continue
                r["src"] = SRC_BORTON
                if r["section"].startswith("III. Periodicals") and r["type"] == "book":
                    r["type"] = "periodical"  # the whole chapter lists journals and serials
                out.append(r)
    for line in open(os.path.join(HERE, "henshall", "entries.jsonl"), encoding="utf-8"):
        if line.strip():
            r = json.loads(line)
            if any(a in norm(r["author"]) and t in norm(r["title"]) for a, t in EXCLUDE_HENSHALL):
                continue
            r["src"] = SRC_HENSHALL
            out.append(r)
    return out


def sur(author):
    """Normalised surname of the first-named author; '' for anonymous / corporate-looking headings."""
    a = re.sub(r"^\(|\)$", "", author.strip())
    if not a or "," not in a:
        return ""
    head = a.split(",")[0]
    toks = norm(head).split()
    return toks[-1] if toks and len(toks) <= 3 else ""


def tkey(title):
    return norm(main_title(title))


def _uniq_ok(a, b):
    """Reject pairs whose differing words are really different words (Criminal/Civil, -yu/-mi) rather than
    spelling variants (Architeckur/Architektur)."""
    ta, tb = set(a.split()), set(b.split())
    ua, ub = ta - tb, tb - ta
    if not ua or not ub:
        return True
    close = lambda w, others: any(difflib.SequenceMatcher(None, w, o).ratio() >= 0.75 for o in others)
    return all(close(w, ub) for w in ua if len(w) > 2) and all(close(w, ua) for w in ub if len(w) > 2) \
        and all(any(difflib.SequenceMatcher(None, w, o).ratio() >= 0.5 for o in ub) for w in ua if len(w) <= 2 and any(len(o) <= 2 for o in ub))


def same_title(a, b, fa, fb, strict=False):
    """a, b: normalised title proper; fa, fb: normalised full titles. strict: parts of books/journals and
    author-less fallbacks, where a shared series title must not be enough."""
    if not a or not b:
        return False
    da, db = set(re.findall(r"\d+", a)), set(re.findall(r"\d+", b))
    if da and db and da != db:
        return False  # numbered parts / different years of a serial
    if a == b:
        return True
    if strict:
        return difflib.SequenceMatcher(None, fa, fb).ratio() >= 0.95 and _uniq_ok(fa, fb)
    short, long_ = (a, b) if len(a) <= len(b) else (b, a)
    if len(short) >= 14 and (long_.startswith(short + " ") or fa.startswith(fb + " ") or fb.startswith(fa + " ")):
        return True
    if difflib.SequenceMatcher(None, a, b).ratio() >= 0.9 and _uniq_ok(a, b):
        return True
    n = min(len(fa), len(fb))
    return n >= 20 and difflib.SequenceMatcher(None, fa[:n], fb[:n]).ratio() >= 0.93 and _uniq_ok(fa[:n], fb[:n])


def years_close(y1, y2):
    if y1 is None or y2 is None:
        return None  # unknown
    return abs(y1 - y2) <= TOL


class Index:
    """Bucket rows by surname ('' bucket for anonymous) for candidate lookup."""

    def __init__(self):
        self.b, self.t = {}, {}

    def add(self, item):
        self.b.setdefault(item["sur"], []).append(item)
        self.t.setdefault(item["tk"], []).append(item)

    def exact(self, tk, full, year, kind):
        dg = set(re.findall(r"\d+", full))
        c = [it for it in self.t.get(tk, []) if it["kind"] == kind and years_close(year, it["year"])
             and not (dg and set(re.findall(r"\d+", it["full"])) and dg != set(re.findall(r"\d+", it["full"])))]
        return min(c, key=lambda it: abs(year - it["year"])) if c else None

    def find(self, sur_, tk, full, year, kind, strict=False):
        best = None
        toks = set(tk.split())
        for it in self.b.get(sur_, []):
            if it["kind"] != kind:
                continue
            yc = years_close(year, it["year"])
            if yc is False:
                continue
            common = len(toks & it["toks"])
            if common * 2 < min(len(toks), len(it["toks"])):
                continue  # cheap pre-filter before difflib
            if not same_title(tk, it["tk"], full, it["full"], strict or kind == "part"):
                continue
            if yc is None and tk != it["tk"]:
                continue  # an undated side needs an exact title
            d = abs(year - it["year"]) if yc else 99
            if best is None or d < best[0]:
                best = (d, it)
        return best[1] if best else None


def kind_of(r):
    return "book" if r["type"] in ("book", "periodical") else "part"  # articles & chapters never match a book row


def item(sur_, title, year, kind, ref):
    tk = tkey(title)
    return {"sur": sur_, "tk": tk, "toks": set(tk.split()), "full": norm(title), "year": year, "kind": kind, "ref": ref}


def merge(uc_rows):
    """uc_rows: list of dicts with author, title, year_num (Union Catalog rows, in DB order).
    Returns (attach, new): attach = {uc_index: [new records]}, new = [record, ...] where each new
    record carries r['also'] = later duplicates folded into it."""
    idx = Index()
    for i, u in enumerate(uc_rows):
        idx.add(item(sur(u["author"]), u["title"], u["year_num"], "book", ("uc", i)))
    attach, new = {}, []
    for r in load_new():
        k = kind_of(r)
        hit = idx.find(sur(r["author"]), tkey(r["title"]), norm(r["title"]), r["year_start"], k)
        tk, full, su = tkey(r["title"]), norm(r["title"]), sur(r["author"])
        if hit is None and su:
            # the same person under a variant spelling (Uyehara/Uehara, Inouye/Inoue, Elisséev/Elisséeff)
            for other in list(idx.b):
                if other and other != su and other[0] == su[0] and difflib.SequenceMatcher(None, su, other).ratio() >= 0.8:
                    hit = idx.find(other, tk, full, r["year_start"], k)
                    if hit:
                        break
        if hit is None and su and len(tk) >= 25:
            # corporate/anonymous cataloguing of the same work
            hit = idx.find("", tk, full, r["year_start"], k, strict=len(tk) < 40)
        if hit is None and len(tk) >= 20 and r["year_start"] is not None:
            # entered under another heading (translator vs. original author, editor vs. diarist): identical
            # title proper of some length + years within tolerance
            hit = idx.exact(tk, full, r["year_start"], k)
        if hit is not None:
            kind, ref = hit["ref"]
            if kind == "uc":
                attach.setdefault(ref, []).append(r)
            else:
                new[ref].setdefault("also", []).append(r)
            continue
        r["also"] = []
        new.append(r)
        idx.add(item(sur(r["author"]), r["title"], r["year_start"], k, ("new", len(new) - 1)))
    return attach, new


SUFFIX = re.compile(r'printed (?:as|entry number is)(?: entry)? "?\d+([a-c])', re.I)


def where(r):
    if r["src"] == SRC_BORTON:
        m = SUFFIX.search(r.get("note") or "")
        return f"{SRC_BORTON} no. {r['entry_no']}{m.group(1) if m else ''}, p. {r['pdf_page']}"
    return f"{SRC_HENSHALL} bibliography, p. {r['pdf_page']}"


def xref(r):
    """Cross-reference added to an existing row for a duplicate found in a later bibliography."""
    s = f"Also in {where(r)} (as {r['year']})"
    if r.get("annotation"):
        s += f": {r['annotation']}"
    return s


VOLS = re.compile(r"\b\d+\s+Vols?\.(?:\s*\([^)]*\))?|\bVols?\.\s*[IVX\d]+(?:\s*[-–]\s*[IVX\d]*)?", re.I)


def rec_years(r):
    ys = [int(y) for y in re.findall(r"(?<!\d)(1[6-9]\d\d|20[0-2]\d)(?!\d)", r["year"])]
    if r["year_start"] is not None:
        ys.append(r["year_start"])
    return ys


def split_matches(r, cache):
    """(links, other_editions) from the lookup cache. A match whose date is within TOL years of any year
    printed for the record is taken to be the same book; an undated match is kept only when the record
    has a personal author (creator was part of the match)."""
    d = cache.get(lkey(r))
    if d is None:
        return None, []
    ys, links, others = rec_years(r), [], []
    short = len(tkey(r["title"]).split()) < 4
    from build_list import usable
    for m in d["matches"]:
        if not usable(m):
            continue  # can be neither read nor borrowed
        y = m.get("year")
        if short and not m.get("creator"):
            continue  # "Le Japon", "Japan": a bare short title with no creator proves nothing
        if y is None:
            if sur(r["author"]):
                links.append(m)
        elif any(abs(y - x) <= TOL for x in ys) or (r["type"] == "periodical" and ys and y >= min(ys) - TOL):
            links.append(m)  # a serial: any volume from its first year on
        elif sur(r["author"]) and m.get("creator") and m["score"] >= 0.95:
            others.append(m)
    return links, others


def new_row(r, cache):
    url = lambda m: f"https://archive.org/details/{m['identifier']}"
    links, others = split_matches(r, cache) if wants_lookup(r) else (None, [])
    loose = False
    if links is not None and not links and not others:
        from build_list import loose_matches
        links = loose_matches("new|" + lkey(r))
        loose = bool(links)
    parts = []
    if r["type"] != "book":
        parts.append("Type: " + r["type"])
    if r["container"]:
        parts.append(("In: " if r["type"] in ("article", "chapter") else "Series / issuing body: ") + r["container"])
    imprint = ", ".join(x for x in (r["place"], r["publisher"]) if x)
    if imprint:
        parts.append("Imprint: " + imprint)
    if r["extent"]:
        parts.append("Extent: " + r["extent"])
    if r["section"]:
        parts.append("Section: " + r["section"])
    parts.append(where(r))
    if r["annotation"]:
        parts.append("Annotation: " + r["annotation"])
    if r["note"]:
        parts.append("Note: " + r["note"])
    for d in r["also"]:
        parts.append(xref(d))
    if loose:
        parts.append("IA match: loose (title key words, date within 4 years; author not compared)")
    if others:
        parts.append("IA other editions: " +
                     "; ".join(f"{url(m)} ({m['year']})" for m in others[:8]))
    m = VOLS.search(r["extent"]) or VOLS.search(r["title"])
    src = "; ".join(dict.fromkeys([r["src"]] + [d["src"] for d in r["also"]]))
    linktxt = None if links is None else "\n".join(url(m) for m in links)
    return [r["author"].strip(), r["title"].strip(), r["year"], r["year_start"], r["edition"],
            m.group(0).strip() if m else "", linktxt, " | ".join(parts), src, r["type"]]


def load_cache2():
    c = {}
    if os.path.exists(CACHE2):
        for line in open(CACHE2, encoding="utf-8"):
            try:
                d = json.loads(line)
                c[d["key"]] = d
            except Exception:
                pass
    return c


def lkey(r):
    return norm(r["author"]) + "|" + norm(r["title"])


def wants_lookup(r):
    return r["type"] in ("book", "periodical") and (r["year_start"] is not None or re.search(r"\d{4}", r["year"]))


def uc_rows_from_db():
    import sqlite3
    con = sqlite3.connect(os.path.join(HERE, "..", "list.sqlite"))
    rows = [dict(author=a, title=t, year_num=y) for a, t, y in
            con.execute("SELECT author,title,year_num FROM books WHERE source LIKE 'Union Catalog%' ORDER BY id")]
    con.close()
    return rows


if __name__ == "__main__":
    uc = uc_rows_from_db()
    attach, new = merge(uc)
    n_att = sum(len(v) for v in attach.values())
    n_also = sum(len(r["also"]) for r in new)
    books = [r for r in new if wants_lookup(r)]
    cache = load_cache2()
    todo = [r for r in books if lkey(r) not in cache]
    if "--todo" in sys.argv:
        for r in todo:
            print(r["src"], "|", r["author"], "|", r["title"][:70], "|", r["year"])
    with open(os.path.join(HERE, "dedup_report.tsv"), "w", encoding="utf-8") as f:
        f.write("kind\tnew_src\tnew_author\tnew_title\tnew_year\tmatched_author\tmatched_title\tmatched_year\n")
        for i, rs in sorted(attach.items()):
            for r in rs:
                f.write("\t".join(["UC", r["src"], r["author"], r["title"], r["year"], uc[i]["author"], uc[i]["title"], str(uc[i]["year_num"])]) + "\n")
        for r in new:
            for d in r["also"]:
                f.write("\t".join(["NEW", d["src"], d["author"], d["title"], d["year"], r["author"], r["title"], r["year"]]) + "\n")
    total = len(load_new())
    print(f"new-source records {total}: matched to Union Catalog rows {n_att}, folded into another new record {n_also}, "
          f"new rows {len(new)} (books to look up {len(books)}, not yet looked up {len(todo)})")
