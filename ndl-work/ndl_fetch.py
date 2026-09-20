#!/usr/bin/env python3
"""Fetch bibliographic metadata for National Diet Library digital-collection items.

Input: a text file of https://dl.ndl.go.jp/pid/NNNN URLs (other lines are ignored).
Output: ndl.jsonl, one record per PID, written as it goes (re-running skips what is already there).

Only the NDL is contacted, one request at a time with a pause between them and a long back-off on
429/5xx, so as not to burden the service. No personal information is sent: the User-Agent is a plain
descriptive string and no credentials or contact details are used.

    ndl_fetch.py /path/to/urls.txt [--delay 3] [--limit N]
"""
import argparse, json, os, re, sys, time, urllib.error, urllib.request
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "ndl.jsonl")
UA = "japan-bib/1.0 (offline bibliography reconciliation)"
OAI = ("https://dl.ndl.go.jp/api/oaipmh?verb=GetRecord&metadataPrefix=dcndl_porta"
       "&identifier=oai:dl.ndl.go.jp:info:ndljp/pid/{pid}")
NS = {"oai": "http://www.openarchives.org/OAI/2.0/", "dc": "http://purl.org/dc/elements/1.1/",
      "dcterms": "http://purl.org/dc/terms/", "dcndl": "http://ndl.go.jp/dcndl/terms/",
      "xsi": "http://www.w3.org/2001/XMLSchema-instance"}


def get(url, tries=5):
    wait = 5
    for n in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/xml"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and n < tries - 1:
                print(f"  HTTP {e.code}, waiting {wait}s", flush=True)
                time.sleep(wait)
                wait *= 3
                continue
            raise
        except Exception:
            if n < tries - 1:
                time.sleep(wait)
                wait *= 3
                continue
            raise


def texts(el, path):
    return [re.sub(r"\s+", " ", x.text).strip() for x in el.findall(path, NS) if x is not None and x.text]


def parse(pid, xml):
    root = ET.fromstring(xml)
    err = root.find("oai:error", NS)
    if err is not None:
        return {"pid": pid, "error": (err.get("code") or "") + " " + (err.text or "")}
    m = root.find(".//oai:metadata/", NS)
    if m is None:
        return {"pid": pid, "error": "no metadata"}
    creators = texts(m, "dc:creator")
    # the second form is the authority heading ("Medhurst, Walter Henry, 1796-1857"); keep both apart
    heading = [c for c in m.findall("dc:creator", NS) if (c.get("{%s}type" % NS["xsi"]) or "").endswith("NDLNA")]
    heading = [re.sub(r"\s+", " ", c.text).strip() for c in heading if c.text]
    return {
        "pid": pid,
        "url": f"https://dl.ndl.go.jp/pid/{pid}",
        "title": (texts(m, "dcterms:title") or [""])[0],
        "title_kana": (texts(m, "dcndl:titleTranscription") or [""])[0],
        "volume": (texts(m, "dcndl:volume") or [""])[0],
        "series": (texts(m, "dcndl:seriesTitle") or [""])[0],
        "creators": [c for c in creators if c not in heading],
        "creator_headings": heading,
        "publisher": (texts(m, "dc:publisher") or [""])[0],
        "place": (texts(m, "dcndl:publicationPlace") or [""])[0],
        "issued": (texts(m, "dcterms:issued") or [""])[0],
        "issued_all": texts(m, "dcterms:issued"),
        "extent": (texts(m, "dcterms:extent") or [""])[0],
        "language": (texts(m, "dc:language") or [""])[0],
        "subjects": texts(m, "dc:subject"),
        "descriptions": texts(m, "dc:description"),
        "edition": (texts(m, "dcndl:edition") or [""])[0],
        "material": (texts(m, "dcndl:materialType") or [""])[0],
        "call_number": (texts(m, "dcndl:callNumber") or [""])[0],
        "identifiers": texts(m, "dc:identifier"),
        "rights": (texts(m, "dcterms:rights") or [""])[0],
        "access_rights": texts(m, "dcterms:accessRights"),
    }


def done_pids():
    d = {}
    if os.path.exists(OUT):
        for line in open(OUT, encoding="utf-8"):
            try:
                r = json.loads(line)
                d[r["pid"]] = r
            except Exception:
                pass
    return d


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("urls")
    ap.add_argument("--delay", type=float, default=3.0)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    pids, seen = [], set()
    for line in open(args.urls, encoding="utf-8"):
        m = re.search(r"dl\.ndl\.go\.jp/pid/(\d+)", line)
        if m and m.group(1) not in seen:
            seen.add(m.group(1))
            pids.append(m.group(1))
    have = done_pids()
    todo = [p for p in pids if p not in have or "error" in have[p]]
    print(f"{len(pids)} PIDs, {len(have)} already fetched, {len(todo)} to do", flush=True)
    if args.limit:
        todo = todo[:args.limit]
    for i, pid in enumerate(todo, 1):
        try:
            rec = parse(pid, get(OAI.format(pid=pid)))
        except Exception as e:
            rec = {"pid": pid, "error": repr(e)[:200]}
        with open(OUT, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"{i}/{len(todo)} {pid} {rec.get('error') or (rec['issued'] + ' ' + rec['title'][:70])}", flush=True)
        if i < len(todo):
            time.sleep(args.delay)
    print("finished", flush=True)
