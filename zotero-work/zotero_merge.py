#!/usr/bin/env python3
"""Merge the hand-checked Zotero collection "Japan Online" (zotero.jsonl, made by zotero_parse.py) into the rows
built by union-catalog-work/build_db.py.

Every Zotero item carries a link that was checked by hand, in one of two exports: openly readable / borrow only.
  * the link is ALWAYS kept, listed first, with the access it was checked to have;
  * an item already in the database (its archive.org identifier is among a row's links, or same author +
    title proper with years within 3) does not get a new row. Whichever description is fuller becomes the
    row's description; the other one is kept as an "Also in ..." note, so nothing is lost;
  * anything else becomes a new row with source SRC.
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "next-bib-work"))
sys.path.insert(0, os.path.join(HERE, "..", "union-catalog-work"))
import merge as M  # noqa: E402

SRC = "KML Zotero"
CORP = re.compile(r"\b(society|office|department|dept|japan|company|co|inc|press|university|bureau|commission|library|museum|"
                  r"association|board|church|mission|missions|government|ministry|institute|committee|united|states|railways?|"
                  r"hotel|firm|group|deputation|kaisha|kyokai|kōsha|of|the|and|for|club|bank|league|army|navy|council)\b|[&(\[]|[a-z]{3,}\.(\s|$)", re.I)
BOILER = re.compile(r"digitized by Google|uploaded to the Internet Archive|metadata below describe the original scanning", re.I)


def invert(name):
    """'Willard Price' -> 'Price, Willard' for plain personal names; corporate names are left alone."""
    name = name.strip()
    if not name or name.lower() == "not available":
        return ""
    if "," in name or CORP.search(name):
        return name
    toks = name.split()
    if 2 <= len(toks) <= 4:
        return f"{toks[-1]}, {' '.join(toks[:-1])}"
    return name


def norm_url(u):
    return re.sub(r"^http://(www\.)?archive\.org/", "https://archive.org/", u.strip())


# Links taken out again after being looked at: a HathiTrust record that turns out not to be readable
# outside the United States, a copy that is not the work it was filed under, and so on.
DROP = {
    "https://catalog.hathitrust.org/Record/102619708",   # Pocket Guide to Japan: the HathiTrust copy is not open
}


def reachable(u):
    """A host on someone's internal network (.local, localhost) is a dead link for everyone else."""
    host = re.sub(r"^https?://([^/]*).*$", r"\1", u).lower()
    return not (host.endswith(".local") or host.startswith("localhost"))


def load():
    seen, out = {}, []
    for line in open(os.path.join(HERE, "zotero.jsonl"), encoding="utf-8"):
        z = json.loads(line)
        z["urls"] = [u for u in (norm_url(u) for u in z["urls"]) if reachable(u) and u not in DROP]
        if not z["urls"]:
            continue          # nothing left to link to
        k = z["urls"][0] if z["urls"] else None
        if k and k in seen:
            continue  # the same item filed twice in the collection
        if k:
            seen[k] = 1
        names = [invert(a) for a in z["authors"]] or [invert(a) + ", ed." for a in z["editors"] if invert(a)]
        z["author"] = "; ".join(n for n in names if n)
        m = re.search(r"(?<!\d)(1[5-9]\d\d|20[0-2]\d)(?!\d)", z["date"])
        z["year_num"] = int(m.group(1)) if m else None
        z["year"] = (m.group(1) if re.fullmatch(r"\d{4}(-\d\d){0,2}", z["date"]) else z["date"]) if z["date"] else "n.d."
        if z["abstract"] and (BOILER.search(z["abstract"]) or re.fullmatch(r"[\d\s]+", z["abstract"])):
            z["abstract"] = ""
        out.append(z)
    return out


def describe(z):
    """'other' parts for a Zotero item."""
    parts = []
    imprint = ", ".join(x for x in (z["place"], z["publisher"]) if x)
    if imprint:
        parts.append("Imprint: " + imprint)
    if z["pages"]:
        parts.append("Extent: " + (z["pages"] + " p." if z["pages"].isdigit() else z["pages"]))
    if z["series"]:
        parts.append("Series: " + z["series"])
    if z["language"]:
        parts.append("Language: " + z["language"])
    people = [("Translator", z["translators"]), ("Contributor", z["contributors"])]
    for label, ps in people:
        if ps:
            parts.append(f"{label}: " + "; ".join(invert(p) for p in ps))
    if z["subjects"]:
        parts.append("Subjects: " + "; ".join(z["subjects"][:12]))
    if z["abstract"]:
        parts.append("Note: " + z["abstract"])
    return parts


def fullness_z(z):
    return sum(bool(x) for x in (z["author"], z["title"], z["year_num"], z["edition"], z["volume"] or z["num_volumes"],
                                 z["publisher"], z["place"], z["pages"], z["series"], z["abstract"]))


def fullness_row(row):
    other = row[7]
    has = lambda k: (k + ": ") in other
    imp = re.search(r"Imprint: ([^|]+)", other)
    return sum(bool(x) for x in (row[0], row[1], row[3], row[4], row[5], imp, imp and "," in imp.group(1), has("Extent"),
                                 has("Series"), has("Annotation") or has("Note")))


ART = re.compile(r"^(the|a|an|der|die|das|le|la|les|l) ")
STOPW = set("the a an of and in on to for by with from its their de la le les du des et der die das und von in".split())


def _split(t):
    """(title proper, subtitle) as lists of significant words."""
    m = re.match(r"(.{8,}?)(?:[:;]|\.\s|,\s(?=(?:with|being|an?|or|the)\b))(.*)", t, re.I | re.S)
    a, b = (m.group(1), m.group(2)) if m else (t, "")
    w = lambda x: [y for y in ART.sub("", M.norm(x)).split() if y not in STOPW and (len(y) > 1 or y.isdigit())]
    return w(a), w(b)


def _cov(ws, pool):
    close = lambda w: any(w == x or (min(len(w), len(x)) >= 4 and M.difflib.SequenceMatcher(None, w, x).ratio() >= 0.8) for x in pool)
    return sum(close(w) for w in ws) / len(ws) if ws else 0.0


def titles_agree(t1, a1, t2, a2, strict=False):
    """Is the archive.org item described by the hand-made Zotero record (t1, a1) the work of the row (t2, a2) that
    links to it? One title proper must be found in the other title (series titles may precede it); then the
    authors must agree, or the titles share four or more words, or the subtitles agree
    ("Japan and Korea: questions and answers" is not "Japan and Korea, map of missions"). Different part or
    section numbers never agree."""
    resp = re.compile(r"[.,;]\s+(?:ed\.|tr\.|trans\.|translated|edited|comp\.|compiled|illus\.|by |with (?:an? )?(?:introd|forew|pref))", re.I)
    p1, s1 = _split(resp.split(t1)[0])
    p2, s2 = _split(resp.split(t2)[0])
    f1, f2 = p1 + s1, p2 + s2
    if not p1 or not p2:
        return False
    nums = lambda f: {w for w in f if w.isdigit() and int(w) < 100}
    n1, n2 = nums(f1), nums(f2)
    if n1 and n2 and not (n1 <= n2 or n2 <= n1):
        return False
    if max(_cov(p1, f2), _cov(p2, f1)) < 0.8:
        return False
    su1, su2 = M.sur(a1), M.sur(a2)
    w1, w2 = set(M.norm(a1 + " " + t1).split()), set(M.norm(a2 + " " + t2).split())
    if (su1 and su1 in w2) or (su2 and su2 in w1) or (su1 and su2 and M.difflib.SequenceMatcher(None, su1, su2).ratio() >= 0.8):
        return True
    sf, lf = (f1, f2) if len(f1) <= len(f2) else (f2, f1)
    if len(sf) >= 4 and _cov(sf, lf) >= 0.8:
        return True
    same_proper = min(_cov(p1, p2), _cov(p2, p1)) >= 0.8
    if same_proper and min(len(p1), len(p2)) >= 4:
        return True
    if s1 and s2:
        return max(_cov(s1, s2), _cov(s2, s1)) >= 0.4
    return (not strict and same_proper and min(len(p1), len(p2)) >= 3) or not (su1 and su2)


def ids_in(links):
    return [u.rsplit("/", 1)[1] for u in (links or "").split("\n") if "archive.org/details/" in u]


FALSE = []  # (row author, row title, row year, Zotero title, identifier) for automatic links shown to be wrong


def apply(rows):
    """rows: lists [author,title,year,year_num,edition,volume,links,other,source,type]. Mutates/extends rows.
    Returns {url: access} for the hand-checked links."""
    by_id, idx = {}, M.Index()
    for i, r in enumerate(rows):
        for ident in ids_in(r[6]):
            by_id.setdefault(ident, []).append(i)
        if r[9] in ("book", "periodical"):
            idx.add(M.item(M.sur(r[0]), r[1], r[3], "book", i))
    checked, stats = {}, {"by_link": 0, "by_title": 0, "new": 0, "zotero_fuller": 0, "false_links_removed": 0}
    del FALSE[:]
    for z in load():
        url = z["urls"][0] if z["urls"] else None
        if url:
            checked[url] = z["access_checked"]
        hit = None
        ident = url.rsplit("/", 1)[1] if url and "archive.org/details/" in url else None
        if ident and ident in by_id:
            good = [i for i in by_id[ident] if titles_agree(z["title"], z["author"], rows[i][1], rows[i][0])]
            for i in by_id[ident]:
                if i not in good:
                    # the hand-made record shows that this automatic link pointed at a different work: drop it there
                    rows[i][6] = "\n".join(u for u in rows[i][6].split("\n") if not u.endswith("/" + ident))
                    stats["false_links_removed"] += 1
                    FALSE.append((rows[i][0], rows[i][1], rows[i][2], z["title"], ident))
            if good:
                hit = min(good, key=lambda i: abs((rows[i][3] or 0) - (z["year_num"] or 0)))
                stats["by_link"] += 1
        if hit is None:
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
            if h is not None and not titles_agree(z["title"], z["author"], rows[h["ref"]][1], rows[h["ref"]][0], strict=True):
                h = None  # same short title, but another work (other section, other author)
            if h is not None:
                hit = h["ref"]
                stats["by_title"] += 1
        zdesc = describe(z)
        if hit is None:
            rows.append([z["author"], z["title"], z["year"], z["year_num"], z["edition"], z["volume"] or (z["num_volumes"] + " v." if z["num_volumes"] else ""),
                         url or "", " | ".join(zdesc + [SRC]), SRC, "book"])
            i = len(rows) - 1
            idx.add(M.item(M.sur(z["author"]), z["title"], z["year_num"], "book", i))
            if ident:
                by_id.setdefault(ident, []).append(i)
            stats["new"] += 1
            continue
        r = rows[hit]
        if url and url not in (r[6] or "").split("\n"):
            r[6] = "\n".join([url] + [u for u in (r[6] or "").split("\n") if u])
        if SRC not in r[8]:
            r[8] += "; " + SRC
        zline = ". ".join(x for x in (z["author"], z["title"], ", ".join(y for y in (z["place"], z["publisher"], z["year"]) if y)) if x)
        if fullness_z(z) > fullness_row(r) and "Also in " + SRC not in r[7] and "Description from " + SRC not in r[7]:
            old = ". ".join(x for x in (r[0], r[1], r[4], r[2]) if x)
            r[0], r[1], r[2], r[4] = z["author"] or r[0], z["title"], z["year"], z["edition"] or r[4]
            r[3] = z["year_num"] if z["year_num"] is not None else r[3]
            r[7] = " | ".join(zdesc + [f"Description from {SRC}; entered elsewhere as: {old}", r[7]])
            stats["zotero_fuller"] += 1
        else:
            r[7] += f" | Also in {SRC}: {zline}" + (f" ({z['pages']} p.)" if z["pages"].isdigit() else "")
    print("Zotero:", stats, "| hand-checked links", len(checked))
    return checked
