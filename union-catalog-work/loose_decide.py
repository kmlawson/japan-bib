#!/usr/bin/env python3
"""Record hand verdicts for the first N lines of loose_review.tsv: loose_decide.py N y-index [y-index ...]
(every other line among the first N is recorded as 'n'). Then re-run loose_classify.py."""
import sys
n, yes = int(sys.argv[1]), {int(x) for x in sys.argv[2:]}
rows = [l.rstrip("\n").split("\t") for l in open("loose_review.tsv", encoding="utf-8")][:n]
with open("loose_decisions.tsv", "a", encoding="utf-8") as f:
    for i, p in enumerate(rows):
        f.write("\t".join([p[0], p[1], "y" if i in yes else "n", p[3][:60] + " => " + p[4][:60]]) + "\n")
print("recorded", len(rows), "verdicts,", len(yes), "accepted")
