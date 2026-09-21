#!/usr/bin/env python3
"""Write the two files the page offers for download: the whole list as Markdown and as PDF.

    build_downloads.py [--db list.sqlite] [--out downloads] [--no-pdf]

Both hold the same thing: every entry in the published database, alphabetised by author and then by
year, with its online copies. The head of each file carries the version and the date of the build, so
a saved copy can be told apart from a later one.

The PDF is made with pandoc and xelatex, in Times with Hiragino Sans for the Japanese; without them
(`--no-pdf`, or pandoc missing) only the Markdown is written and the page's PDF button will 404, so
check the output of this script before publishing.
"""
import argparse, datetime, os, re, shutil, sqlite3, subprocess, sys, unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "list.sqlite")
OUT = os.path.join(HERE, "downloads")
VERSION = os.path.join(HERE, "page", "version.txt")
SOURCES_MD = os.path.join(HERE, "page", "modern-japan.md")   # the lists behind the buttons on the page
SITE = "https://kmlawson.github.io/japan-bib/"
HOLDER = [("archive.org/", "Internet Archive"), ("gallica.bnf.fr/", "Gallica"),
          ("dl.ndl.go.jp/", "National Diet Library"), ("europeana.eu/", "Europeana"),
          ("nb.no/", "National Library of Norway"), ("alvin-portal.org/", "Alvin"),
          ("hathitrust.org/", "HathiTrust"), ("onlinebooks.library.upenn.edu/", "The Online Books Page")]


def version():
    if os.path.exists(VERSION):
        m = re.search(r"(\d+)\s*$", open(VERSION, encoding="utf-8").read().strip())
        if m:
            return f"1.{int(m.group(1)):04d}"
    return "1.0000"


def fold(s):
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def holder(url):
    for frag, name in HOLDER:
        if frag in url:
            return name
    return re.sub(r"^https?://(www\.)?([^/]+)/.*$", r"\2", url)


def rows(db):
    con = sqlite3.connect(db)
    out = list(con.execute(
        "SELECT id, author, title, year, year_num, edition, volume, links, links_access, links_checked,"
        " other, source, type, language, access FROM books"))
    con.close()
    return out


def entry(r):
    (rid, author, title, year, ynum, edition, volume, links, laccess, lchecked,
     other, source, typ, language, access) = r
    bits = []
    head = f"**{author.rstrip('.')}.** " if author else ""
    bits.append(f"{head}*{title}*.")
    tail = [year or "n.d."]
    if edition:
        tail.append(edition)
    if volume:
        tail.append(volume)
    if typ and typ != "book":
        tail.append(typ)
    if language:
        tail.append(language)
    bits.append(" ".join(x for x in [", ".join(tail) + "."] if x))
    urls = (links or "").split("\n") if links else []
    acc = (laccess or "").split("\n")
    chk = (lchecked or "").split("\n")
    for i, u in enumerate(u for u in urls if u):
        a = acc[i] if i < len(acc) else ""
        c = ", checked by hand" if i < len(chk) and chk[i] == "1" else ""   # no tick: the PDF font has none
        label = {"open": "read", "borrow": "borrow"}.get(a, "view")
        bits.append(f"{label} at {holder(u)}{c}: <{u}>")
    imprint = re.search(r"Imprint: ([^|]+)", other or "")
    if imprint:
        bits.insert(2, imprint.group(1).strip() + ".")
    bits.append(f"[{source}; no. {rid}]")
    return " ".join(bits)


def sources():
    """The page's own lists - everything behind the buttons - with their headings put one level down,
    so that they sit inside this document rather than beside it. The marker that turns a list into
    bubbles on the page means nothing here and is taken out."""
    if not os.path.exists(SOURCES_MD):
        return []
    out, first, seen_also, before_first_heading = [], True, False, True
    for line in open(SOURCES_MD, encoding="utf-8").read().splitlines():
        line = line.replace("<!--pills-->", "").rstrip()
        m = re.match(r"^(#+)\s+(.*)$", line)
        if m:
            if first:                       # the title of that page; this document has its own
                first = False
                continue
            before_first_heading = False    # from the first real section on, everything is kept
            out.append("#" * (len(m.group(1)) + 1) + " " + m.group(2))
            continue
        if line.strip().lower().startswith("see also"):
            seen_also = True
        if before_first_heading and not seen_also and re.match(r"^\s*[-*+]\s", line):
            continue                        # the index of sections: the headings below say the same
        out.append(line)
    return out


def markdown(db, ver, today):
    rs = rows(db)
    rs.sort(key=lambda r: (fold(r[1]) or "￿", r[4] or 9999, fold(r[2])))
    n_links = sum(1 for r in rs if r[7])
    n_open = sum(1 for r in rs if r[14] == "open")
    n_borrow = sum(1 for r in rs if r[14] == "borrow")
    out = [f"% Western-language works on Japan, 1850–1955",
           f"% Version {ver} · {today}", "",
           f"{len(rs):,} entries, {n_links:,} with an online copy ({n_open:,} freely readable, "
           f"{n_borrow:,} borrowable). Alphabetical by author, then by year.", "",
           f"Compiled from printed bibliographies and library catalogues; the searchable version, with "
           f"filters and a downloadable database, is at <{SITE}>.", "",
           "This file has two parts: the lists of primary sources that the site opens with, and then the "
           "whole bibliography of digitized books.", "", "---", "",
           "# Primary sources", ""] + sources() + ["", "---", "", "# Digitized books", ""]
    letter = None
    for r in rs:
        first = (fold(r[1])[:1] or "—").upper()
        if not first.isalpha() and first != "—":
            first = "—"
        if first != letter:
            letter = first
            out += ["", f"## {letter}", ""]   # a letter of the alphabet, inside "Digitized books"
        out.append(entry(r) + "\n")
    return "\n".join(out)


def pdf(md_path, pdf_path):
    if not shutil.which("pandoc"):
        print("pandoc not found: no PDF written", file=sys.stderr)
        return False
    cmd = ["pandoc", md_path, "--pdf-engine=xelatex", "-V", "geometry:margin=1.8cm",
           "-V", "fontsize=9pt", "-V", "mainfont=Times New Roman", "-V", "CJKmainfont=Hiragino Sans",
           "-V", "colorlinks=true", "-V", "linkcolor=blue", "-V", "urlcolor=blue",
           "-o", pdf_path]     # no table of contents: the list is alphabetical and the headings speak for themselves
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        print(r.stderr[-1500:], file=sys.stderr)
        return False
    return True


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DB)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--no-pdf", dest="want_pdf", action="store_false")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    ver = version()
    today = datetime.date.today().strftime("%d %B %Y").lstrip("0")
    md = markdown(args.db, ver, today)
    md_path = os.path.join(args.out, "japan-bib.md")
    open(md_path, "w", encoding="utf-8").write(md)
    print(f"{os.path.relpath(md_path, HERE)}: {len(md):,} bytes, version {ver}, {today}")
    if args.want_pdf:
        pdf_path = os.path.join(args.out, "japan-bib.pdf")
        if pdf(md_path, pdf_path):
            print(f"{os.path.relpath(pdf_path, HERE)}: {os.path.getsize(pdf_path):,} bytes")
