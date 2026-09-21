#!/usr/bin/env python3
"""Read the BNE Digital records listed in cards.txt, through Chrome.

The Biblioteca Nacional refuses scripts, so an ordinary Chrome window does the fetching (chrome.py).
Each line of cards.txt is a record's uuid and a short title for the eye; the card page gives the full
title, the author, the imprint and the year, and the same uuid opens the reader at
`/bd/es/viewer?id=<uuid>&page=1`, which is the link worth keeping.

    bne_cards.py [--delay 1]
"""
import argparse, json, os, re, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from chrome import Chrome  # noqa: E402

CARDS = os.path.join(HERE, "cards.txt")
OUT = os.path.join(HERE, "bne_cards.jsonl")
CARD = "https://bnedigital.bne.es/bd/es/card?id={uid}"
VIEWER = "https://bnedigital.bne.es/bd/es/viewer?id={uid}&page=1"
# the card lays its fields out as a list of label/value pairs
READ = """(function(){
  const t = document.body.innerText.replace(/\\r/g,'');
  const out = {};
  const want = ['Título','Autor','Autoría','Publicación','Editor','Fecha','Descripción física',
                'Tipo de documento','Lengua','Notas','Signatura','Materia'];
  const lines = t.split('\\n').map(s=>s.trim()).filter(Boolean);
  for (let i=0;i<lines.length;i++) {
    if (want.includes(lines[i]) && lines[i+1] && !want.includes(lines[i+1])) {
      out[lines[i]] = (out[lines[i]] ? out[lines[i]] + ' | ' : '') + lines[i+1];
    }
  }
  out._head = lines.slice(0, 70).join(' / ').slice(0, 2000);   // long titles push the imprint down the page
  return out;})()"""


def load():
    out = []
    for line in open(CARDS, encoding="utf-8"):
        if line.startswith("#") or not line.strip():
            continue
        p = line.rstrip("\n").split("\t")
        out.append((p[0].strip(), p[1].strip() if len(p) > 1 else ""))
    return out


def done():
    d = set()
    if os.path.exists(OUT):
        for line in open(OUT, encoding="utf-8"):
            try:
                d.add(json.loads(line)["uuid"])
            except Exception:
                pass
    return d


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--delay", type=float, default=1.0)
    args = ap.parse_args()
    have = done()
    todo = [(u, t) for u, t in load() if u not in have]
    print(f"{len(todo)} cards to read", flush=True)
    with Chrome() as c:
        for n, (uid, short) in enumerate(todo, 1):
            rec = {"uuid": uid, "short_title": short, "card": CARD.format(uid=uid),
                   "viewer": VIEWER.format(uid=uid)}
            try:
                # the page must really be this card before anything is read, or the last card's
                # fields get recorded again; two attempts, then it is put down as an error
                for attempt in range(2):
                    c.go(CARD.format(uid=uid))
                    for _ in range(15):
                        if uid in c.js("location.href"):
                            break
                        time.sleep(1)
                    if uid in c.js("location.href"):
                        break
                if uid not in c.js("location.href"):
                    raise RuntimeError("the browser did not reach this card")
                time.sleep(1.5)
                fields = c.json(READ) or {}
                if uid not in c.js("location.href"):
                    raise RuntimeError("the page changed while it was being read")
                rec["fields"] = fields
            except Exception as e:
                rec["error"] = repr(e)[:200]
            with open(OUT, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            got = rec.get("fields", {})
            print(f"{n}/{len(todo)} {short[:40]:40s} | {str(got.get('Publicación', ''))[:60]}", flush=True)
            time.sleep(args.delay)
    print("finished", flush=True)
