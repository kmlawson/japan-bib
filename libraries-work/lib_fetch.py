#!/usr/bin/env python3
"""Fetch the catalogue record for each item listed by hand in ids.txt.

Three libraries, each through its own public interface, one request at a time and nothing identifying
sent (a plain descriptive User-Agent, no contact address, no account):

  * nb.no (National Library of Norway)  - api.nb.no/catalog/v1 (JSON) plus the MODS record, which is
    where the publisher and the series statement live.
  * europeana.eu                        - data.europeana.eu/item/... as JSON-LD. The descriptive fields
    sit in the two ore:Proxy nodes: the provider's own record and Europeana's enriched copy. The
    provider's is preferred and the enriched one fills the gaps.
  * alvin-portal.org (Uppsala)          - no API answers for a single record, so the record page is
    read and its labelled fields (Language, Persons, Origin, ...) are picked out.

Answers are cached in lib.jsonl, so the run is resumable.

    lib_fetch.py [--delay 2]
"""
import argparse, html, json, os, re, sys, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
IDS = os.path.join(HERE, "ids.txt")
OUT = os.path.join(HERE, "lib.jsonl")
UA = "japan-bib/1.0 (offline bibliography reconciliation)"


def get(url, accept="application/json", tries=4):
    wait = 10
    for n in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode("utf-8", "replace")
        except Exception:
            if n == tries - 1:
                raise
            time.sleep(wait)
            wait *= 3


def text(x, prefer=()):
    """A Dublin Core value out of JSON-LD: a string, a {'@value': ...}, or a list of either."""
    if x is None:
        return ""
    if isinstance(x, str):
        return x
    if isinstance(x, dict):
        return x.get("@value") or ""
    vals = [v for v in (text(i) for i in x) if v]
    for lang in prefer:
        for i in x:
            if isinstance(i, dict) and i.get("@language") == lang and i.get("@value"):
                return i["@value"]
    return vals[0] if vals else ""


# ---------------------------------------------------------------- nb.no
def nb(url):
    ident = url.rstrip("/").split("/")[-1].split("?")[0]
    d = json.loads(get(f"https://api.nb.no/catalog/v1/items/{ident}"))
    md = d.get("metadata") or {}
    people = md.get("people") or []
    author = next((p.get("name", "") for p in people
                   if any(r.get("name") in ("cre", "aut") for r in p.get("roles") or [])), "")
    if not author and people:
        author = people[0].get("name", "")
    mods = get(f"https://api.nb.no/catalog/v1/metadata/{ident}/mods", "application/xml")
    tags = lambda t: [re.sub(r"\s+", " ", html.unescape(x)).strip()
                      for x in re.findall(f"<{t}[^>]*>(.*?)</{t}>", mods, re.S)]
    titles = [re.sub(r"^<title>", "", t) for t in tags("title")]
    series = titles[1] if len(titles) > 1 else ""
    return {
        "host": "NB", "url": f"https://www.nb.no/items/{ident}",
        "author": author,
        "author_dates": next((p.get("date", "") for p in people if p.get("name") == author), ""),
        "title": (md.get("title") or (titles[0] if titles else "")),
        "subtitle": md.get("subtitle") or "",
        "series": series,
        "year": str((md.get("originInfo") or {}).get("issued") or ""),
        "place": (md.get("geographic") or {}).get("city") or "",
        "publisher": "; ".join(tags("publisher")),
        "extent": (md.get("physicalDescription") or {}).get("extent") or "",
        "pages": md.get("pageCount"),
        "rights": (d.get("accessInfo") or {}).get("license") or "",
        "access": "open" if (d.get("accessInfo") or {}).get("accessAllowedFrom") == "EVERYWHERE" else "limited",
        "urn": (md.get("identifiers") or {}).get("urn") or "",
        "notes": "; ".join(md.get("notes") or []),
    }


# ------------------------------------------------------------ europeana
def europeana(url):
    m = re.search(r"/item/([^/]+)/([^/?#]+)", url)
    set_, ident = m.group(1), m.group(2)
    d = json.loads(get(f"https://data.europeana.eu/item/{set_}/{ident}", "application/ld+json"))
    graph = d.get("@graph", d)
    prox = {n["@id"].split("/proxy/")[1].split("/")[0]: n for n in graph if n.get("@type") == "ore:Proxy"}
    own, eu = prox.get("provider", {}), prox.get("europeana", {})
    agg = next((n for n in graph if n.get("@type") == "ore:Aggregation"), {})
    pick = lambda k, prefer=(): text(own.get(k), prefer) or text(eu.get(k), prefer)
    return {
        "host": "EU", "url": f"https://www.europeana.eu/en/item/{set_}/{ident}",
        "author": pick("dc:creator") or pick("dcterms:creator"),
        "author_dates": "",
        "title": pick("dc:title"), "title_en": text(eu.get("dc:title"), ("en",)),
        "subtitle": pick("dcterms:alternative"), "series": "",
        "year": pick("dcterms:issued") or pick("dc:date") or pick("dcterms:created"),
        "place": pick("dcterms:spatial"), "publisher": pick("dc:publisher"),
        "extent": pick("dcterms:extent"), "pages": None,
        "rights": (agg.get("edm:rights") or {}).get("@id", ""),
        "access": "open",
        "provider_url": (agg.get("edm:isShownAt") or {}).get("@id", ""),
        "file_url": (agg.get("edm:isShownBy") or {}).get("@id", ""),
        "description": pick("dc:description")[:400],
        "type": pick("dc:type"),
        "notes": "",
    }


# ---------------------------------------------------------------- alvin
def alvin(url):
    page = get(url, "text/html")
    body = re.sub(r"<script.*?</script>", " ", page, flags=re.S)
    body = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", body)))
    field = lambda label, nxt: (re.search(label + r"\s+(.*?)\s+(?:" + nxt + ")", body).group(1)
                                if re.search(label + r"\s+(.*?)\s+(?:" + nxt + ")", body) else "")
    title = field(r"ui-button Extended search \| About Alvin \| Copyright \| Contact us P N 1", r"\(Text\)|Language")
    origin = field(r"Origin", r"Physical description|Notes|Contact")
    m = re.search(r"(.*?),\s*[^,]*:\s*(.*?),\s*(\d{4})\s*$", origin.strip())
    pid = urllib.parse.unquote(re.search(r"pid=([^&]+)", url).group(1))
    return {
        "host": "ALVIN", "url": f"https://www.alvin-portal.org/alvin/view.jsf?pid={urllib.parse.quote(pid)}",
        "author": field(r"Persons", r"\(author\)"), "author_dates": "",
        "title": title, "subtitle": "", "series": "",
        "year": m.group(3) if m else "", "place": m.group(1).strip() if m else "",
        "publisher": m.group(2).strip() if m else "",
        "extent": field(r"Physical description", r"Format:|Notes|Contact"),
        "pages": None,
        "rights": "Public Domain Mark" if "Public Domain Mark" in body else "",
        "access": "open",
        "urn": (re.search(r"(urn:nbn:se:alvin:portal:record-\d+)", body) or [""])[0]
        if re.search(r"(urn:nbn:se:alvin:portal:record-\d+)", body) else "",
        "notes": field(r"Notes", r"Contact"),
    }


def fetch(url):
    host = urllib.parse.urlparse(url).netloc
    if "nb.no" in host:
        return nb(url)
    if "europeana.eu" in host:
        return europeana(url)
    if "alvin-portal.org" in host:
        return alvin(url)
    raise ValueError("no reader for " + host)


def done():
    d = {}
    if os.path.exists(OUT):
        for line in open(OUT, encoding="utf-8"):
            try:
                r = json.loads(line)
                d[r["source_url"]] = r
            except Exception:
                pass
    return d


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--delay", type=float, default=2.0)
    args = ap.parse_args()
    wanted = []
    for line in open(IDS, encoding="utf-8"):
        if line.strip() and not line.startswith("#"):
            p = line.rstrip("\n").split("\t")
            wanted.append((p[0].strip(), p[1].strip() if len(p) > 1 else ""))
    have = done()
    todo = [(u, l) for u, l in wanted if u not in have]
    print(f"{len(wanted)} items, {len(todo)} to fetch", flush=True)
    for n, (url, lang) in enumerate(todo, 1):
        try:
            rec = fetch(url)
            rec.update(source_url=url, language=lang)
        except Exception as e:
            rec = {"source_url": url, "language": lang, "error": repr(e)[:200]}
        with open(OUT, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"{n}/{len(todo)} {rec.get('host', '?')} {str(rec.get('title'))[:55]} | {rec.get('year')}"
              f"{' | ' + rec['error'] if rec.get('error') else ''}", flush=True)
        if n < len(todo):
            time.sleep(args.delay)
    print("finished", flush=True)
