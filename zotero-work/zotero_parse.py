#!/usr/bin/env python3
"""Parse Zotero RDF exports into zotero.jsonl (one record per item).

    zotero_parse.py OPEN.rdf BORROW.rdf        rewrite zotero.jsonl from the two collections
    zotero_parse.py --add FILE.rdf ACCESS      add one more export (open | borrow) to what is there

The export an item came from is recorded as the access its links were checked to have. --add is for a
later export, such as the HathiTrust items that can be read anywhere, when the earlier RDF files are
no longer to hand; items already in zotero.jsonl (same first URL) are not added twice.
"""
import json, os, re, sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
NS = {"rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#", "z": "http://www.zotero.org/namespaces/export#",
      "dc": "http://purl.org/dc/elements/1.1/", "foaf": "http://xmlns.com/foaf/0.1/", "bib": "http://purl.org/net/biblio#",
      "dcterms": "http://purl.org/dc/terms/", "link": "http://purl.org/rss/1.0/modules/link/",
      "prism": "http://prismstandard.org/namespaces/1.2/basic/", "vcard": "http://nwalsh.com/rdf/vCard#"}
RDF = "{%s}" % NS["rdf"]


def text(el, path):
    x = el.find(path, NS)
    return re.sub(r"\s+", " ", x.text).strip() if x is not None and x.text else ""


def people(el, tag):
    out = []
    for p in el.findall(f"bib:{tag}/rdf:Seq/rdf:li/foaf:Person", NS):
        sn, gn = text(p, "foaf:surname"), text(p, "foaf:givenName")
        out.append(f"{sn}, {gn}" if sn and gn else sn or gn)
    return out


def parse(fn, access):
    root = ET.parse(fn).getroot()
    recs = []
    for el in root:
        itype = text(el, "z:itemType")
        if itype in ("attachment", "note", "") :
            continue
        about = el.get(RDF + "about") or ""
        urls = [text(u, "rdf:value") for u in el.findall("dc:identifier/dcterms:URI", NS)]
        if about.startswith("http"):
            urls.insert(0, about)
        urls = list(dict.fromkeys(u for u in urls if u))
        idents = [v.text.strip() for v in el.findall("dc:identifier", NS) if v.text and v.text.strip()]
        series = text(el, "dcterms:isPartOf/bib:Series/dc:title")
        container = text(el, "dcterms:isPartOf/bib:Journal/dc:title") or text(el, "dcterms:isPartOf/bib:Book/dc:title")
        subjects = [re.sub(r"\s+", " ", s.text).strip() for s in el.findall("dc:subject", NS) if s.text and s.text.strip()]
        recs.append({
            "zotero_type": itype, "access_checked": access, "urls": urls,
            "authors": people(el, "authors"), "editors": people(el, "editors"), "translators": people(el, "translators"),
            "contributors": people(el, "contributors"),
            "title": text(el, "dc:title"), "date": text(el, "dc:date"),
            "publisher": text(el, "dc:publisher/foaf:Organization/foaf:name"),
            "place": text(el, "dc:publisher/foaf:Organization/vcard:adr/vcard:Address/vcard:locality"),
            "edition": text(el, "prism:edition"), "volume": text(el, "prism:volume"), "num_volumes": text(el, "z:numberOfVolumes"),
            "pages": text(el, "z:numPages") or text(el, "bib:pages"), "language": text(el, "z:language"),
            "series": series, "container": container, "abstract": text(el, "dcterms:abstract"),
            "short_title": text(el, "z:shortTitle"), "subjects": subjects, "identifiers": idents,
        })
    return recs


OUT = os.path.join(HERE, "zotero.jsonl")

if __name__ == "__main__":
    if sys.argv[1] == "--add":
        have = set()
        for line in open(OUT, encoding="utf-8"):
            r = json.loads(line)
            have.update(r["urls"])
        new = [r for r in parse(sys.argv[2], sys.argv[3]) if not (set(r["urls"]) & have)]
        with open(OUT, "a", encoding="utf-8") as f:
            for r in new:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"added {len(new)} items ({len(parse(sys.argv[2], sys.argv[3])) - len(new)} were already there)")
    else:
        recs = parse(sys.argv[1], "open") + parse(sys.argv[2], "borrow")
        with open(OUT, "w", encoding="utf-8") as f:
            for r in recs:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print("items", len(recs))
