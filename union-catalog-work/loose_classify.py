#!/usr/bin/env python3
"""Classify the candidates found by loose_lookup.py.

  ACCEPT  all key words of the title proper found in the archive.org title and vice versa, the title is long
          enough to be distinctive (or the author's surname is in the item's metadata), numbers agree
  REVIEW  everything plausible but not safe to take automatically - above all short titles and items whose
          creator is somebody else; these are judged by hand and the verdicts kept in loose_decisions.tsv
          (key <TAB> identifier <TAB> y|n <TAB> remark)
  reject  the rest

Writes loose_review.tsv (pending REVIEW pairs without a verdict yet). Usage: loose_classify.py [--stats]"""
import os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from loose_lookup import load_loose, title_proper, cand_main, norm  # noqa: E402

DECISIONS = os.path.join(HERE, "loose_decisions.tsv")
REVIEW = os.path.join(HERE, "loose_review.tsv")


def digits(t):
    return set(re.findall(r"\d+", norm(t)))


def tier(d, c):
    n = d.get("nwords", 0)
    if "." in d["author"].split(",")[0].strip().rstrip("."):
        c = dict(c, auth=None)  # "Japan. Laws, statutes, etc.": a corporate heading, "laws" is not a surname
    dr, dc = digits(title_proper(d["title"])), digits(cand_main(c["title"]))
    if dr and dc and dr != dc:
        return "reject"  # another year of a report, another part of a set
    strong = c["cov_r"] >= 0.8 and c["cov_c"] >= 0.8
    if strong and c["auth"] is True and n >= 2:
        return "ACCEPT"
    if strong and n >= 5 and c["auth"] is not False:
        return "ACCEPT"
    if c["cov_r"] == 1 and c["cov_c"] == 1 and n >= 4 and c["auth"] is None:
        return "ACCEPT"
    if c["cov_c"] < 0.5:
        return "reject"  # the item's own title is mostly about something else
    if strong or (c["cov_r"] >= 0.8 and c["auth"] is True) or (c["cov_r"] >= 0.6 and c["cov_c"] >= 0.6 and n >= 4):
        return "REVIEW"
    return "reject"


def load_decisions():
    d = {}
    if os.path.exists(DECISIONS):
        for line in open(DECISIONS, encoding="utf-8"):
            p = line.rstrip("\n").split("\t")
            if len(p) >= 3 and p[2] in ("y", "n"):
                d[(p[0], p[1])] = p[2]
    return d


def accepted():
    """{key: [candidate, ...]} - automatic ACCEPTs plus hand-approved REVIEW pairs, best first, max 6."""
    dec, out = load_decisions(), {}
    for k, d in load_loose().items():
        for c in d["cands"]:
            t = tier(d, c)
            v = dec.get((k, c["identifier"]))
            if v == "y" or (t == "ACCEPT" and v != "n"):
                out.setdefault(k, []).append(c)
    return {k: v[:6] for k, v in out.items()}


if __name__ == "__main__":
    loose, dec = load_loose(), load_decisions()
    cnt = {"ACCEPT": 0, "REVIEW": 0, "reject": 0}
    recs = {"ACCEPT": set(), "REVIEW": set()}
    pending = []
    for k, d in loose.items():
        for c in d["cands"]:
            t = tier(d, c)
            cnt[t] += 1
            if t in recs:
                recs[t].add(k)
            if t == "REVIEW" and (k, c["identifier"]) not in dec:
                pending.append((k, d, c))
    with open(REVIEW, "w", encoding="utf-8") as f:
        for k, d, c in pending:
            f.write("\t".join([k, c["identifier"], f"n={d.get('nwords')} r={c['cov_r']} c={c['cov_c']} a={c['auth']}",
                               f"{d['author']} | {d['title']} | {'/'.join(map(str, sorted(set(d['years']))))}",
                               f"{c['creator']} | {c['title']} | {c['year']}"]) + "\n")
    print(f"records searched {len(loose)} | candidate pairs: {cnt} | records with an ACCEPT {len(recs['ACCEPT'])}, "
          f"with REVIEW pairs {len(recs['REVIEW'])} | pending review pairs {len(pending)} | decisions on file {len(dec)} "
          f"| records with accepted links now {len(accepted())}")
