#!/usr/bin/env python3
"""Check how each National Diet Library item may be read.

dl.ndl.go.jp's own records give only coded access rights, but NDL Search's OAI-PMH returns the plain
wording ("インターネット公開", "図書館・個人送信資料", "国立国会図書館内限定"). One request per item,
spaced out; resumable (ndl_access.jsonl). Only the NDL is contacted and no personal data is sent.

    ndl_access.py [--delay 4]
"""
import argparse, json, os, re, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from ndl_fetch import get  # noqa: E402

OUT = os.path.join(HERE, "ndl_access.jsonl")
URL = ("https://ndlsearch.ndl.go.jp/api/oaipmh?verb=GetRecord&metadataPrefix=dcndl"
       "&identifier=oai:ndlsearch.ndl.go.jp:R100000039-I{pid}")
OPEN_WORDS = ("インターネット公開", "インターネット公開（保護期間満了）", "Internet")


def classify(rights):
    """open = anyone may read it; limited = only in the library or by registered transmission."""
    if not rights:
        return "unknown"
    if any(w in r for r in rights for w in OPEN_WORDS):
        return "open"
    return "limited"


def load():
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
    ap.add_argument("--delay", type=float, default=4.0)
    args = ap.parse_args()
    pids = [json.loads(l)["pid"] for l in open(os.path.join(HERE, "ndl.jsonl"), encoding="utf-8")
            if not json.loads(l).get("error")]
    have = load()
    todo = [p for p in pids if p not in have or have[p].get("access") == "unknown"]
    print(f"{len(pids)} items, {len(todo)} to check", flush=True)
    for i, pid in enumerate(todo, 1):
        try:
            xml = get(URL.format(pid=pid))
            rights = re.findall(r"<dcterms:accessRights[^>]*>(.*?)</dcterms:accessRights>", xml, re.S)
            rights = [re.sub(r"\s+", " ", x).strip() for x in rights]
            rec = {"pid": pid, "rights": rights, "access": classify(rights)}
        except Exception as e:
            rec = {"pid": pid, "rights": [], "access": "unknown", "error": repr(e)[:120]}
        with open(OUT, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"{i}/{len(todo)} {pid} {rec['access']} {rec['rights']}", flush=True)
        if i < len(todo):
            time.sleep(args.delay)
    print("finished", flush=True)
