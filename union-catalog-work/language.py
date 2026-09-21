#!/usr/bin/env python3
"""Work out the language of each entry from its title (and, where the source gives one, from the
language statement in `other`).

Japanese is deliberately not one of the answers. Most of the entries a rule would call Japanese are
English translations of Japanese classics ("... monogatari", "Nippon ...") or works catalogued by a
Japanese library whose text is English; the few that really are in Japanese are left undetermined ("")
rather than labelled wrongly.

The test is deliberately conservative: a title is called English unless there is positive evidence of
another language. Evidence is (a) letters that English does not use, and (b) function words and endings
that are common in one language and rare in the others. Every decision keeps a confidence, so the
doubtful ones can be looked at by hand; hand decisions live in language_fixes.tsv (id <TAB> language).
"""
import os, re, sys, unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
FIXES = os.path.join(HERE, "language_fixes.tsv")

# Markers: words that are ordinary in one language and (near enough) absent from English titles.
# Anything an English title might contain (art, notes, religion, empire, nature ...) is deliberately left out.
MARKERS = {
    "German": """der die das dem den und im zur zum nach ueber über unter aus mit von vom bei zwischen ein
        eine einer eines deutsche deutschen deutscher japanische japanischen japanisches japanischer
        geschichte beitrag beitraege beiträge jahrhundert gegenwart entwicklung wesen leben welt sprache
        lehre bilder reise reisen briefe gesellschaft handel staat krieg kaiser sammlung verzeichnis
        herausgegeben uebersetzt übersetzt erzählungen erzaehlungen maerchen märchen wörterbuch
        worterbuch grammatik einführung einfuhrung darstellung untersuchungen kunst wirtschaft japans
        seine ihre bis nebst zwei drei vier unserer heutige heutigen""".split(),
    "French": """le la les du des au aux et dans sur sous pour avec sans chez entre depuis japonais
        japonaise japonaises histoire histoires études etudes essai essais recueil mémoire mémoires
        memoires voyage voyages contes moeurs mœurs siècle siecle guerre paix pays peuple peuples
        traduit traduite traduction précédé precede dictionnaire grammaire religieuse religieuses
        ancien ancienne une cette leur notre lettres nouvelle nouvelles ouvrage etude étude
        illustrée illustre""".split(),
    "Italian": """il lo gli dei delle della degli nel nella nelle con sul sulla giappone giapponese
        giapponesi storia viaggio viaggi relazione relazioni lettere arte nostra questa""".split(),
    "Spanish": """el los las una unos unas por para del al japón japon japones japonés japonesa
        historia viaje viajes cartas relación relacion años ensayo edición edicion selección
        seleccion seguidos precedidos""".split(),
    "Portuguese": """uma umas dos japão japao japoneza japonesa japoneses história viagem relação
        século seculo escreve cidade reino""".split(),
    "Dutch": """het een van tot naar over japansche nederlandsche geschiedenis beschrijving reizen
        brieven verhandeling zijn uit onze""".split(),
    "Latin": """liber libri librum rerum scriptores commentarii epistolae epistola japonica japonicae
        japoniae japonicum synodi decreta praelectiones linguae latinae alumnorum seminarii
        societatis jesu anni annis apud""".split(),
    "Danish": "og til fra paa japansk japanske rejse skildringer".split(),
    "Swedish": "och att från fran japansk japanska resa öfversikt ofversikt".split(),
    "Norwegian": "og til fra paa japansk reise".split(),
    "Russian": """iaponiia iaponii yaponiya yaponii zhenshchina sbornik rasskazy ocherki puteshestvie
        voina izdanie izd perevod russkaia russkii sovetskaia""".split(),
}
# a word claimed by more than one language counts for none of them
_seen = {}
for _l, _ws in MARKERS.items():
    for _w in _ws:
        _seen[_w] = _seen.get(_w, 0) + 1
MARKERS = {l: {w for w in ws if _seen[w] == 1} for l, ws in MARKERS.items()}

# a single one of these settles the matter: nobody writes them in an English title
DECISIVE = {
    "German": "japanische japanischen japanisches japanischer geschichte jahrhundert wörterbuch worterbuch übersetzt uebersetzt märchen maerchen beiträge beitraege erzählungen erzaehlungen einführung einfuhrung gegenwart untersuchungen darstellung deutschen".split(),
    "French": "japonais japonaise japonaises études etudes mémoires memoires moeurs siècle siecle traduit traduite traduction dictionnaire précédé precede religieuse ouvrage".split(),
    "Italian": "giappone giapponese giapponesi viaggio viaggi relazioni".split(),
    "Spanish": "japonés japones japonesa edición edicion selección seleccion años ensayo".split(),
    "Portuguese": "japão japao japoneza japoneses história viagem relação século seculo".split(),
    "Dutch": "japansche nederlandsche geschiedenis beschrijving verhandeling".split(),
    "Latin": "japoniae japonica japonicae japonicum synodi praelectiones scriptores commentarii epistolae".split(),
    "Russian": "iaponiia iaponii yaponiya zhenshchina putevoditel sbornik rasskazy ocherki puteshestvie".split(),
    "Swedish": "öfversikt ofversikt japanska".split(),
    "Danish": "japanske skildringer".split(),
}
DECISIVE = {l: set(ws) for l, ws in DECISIVE.items()}

# words too common in English (or too ambiguous) to count as evidence
IGNORE = set("""a an the in of on to for and or at by no not with from as is it its his her their
    von van da de del della no ni ka wa ya ta sa ma ha na ne nu re ro ru shi chi tsu""".split())
STRONG = {"German": re.compile(r"[äöüßÄÖÜ]"), "French": re.compile(r"[àâçéèêëîïôùûœÀÂÇÉÈÊËÎÏÔÙÛŒ]"),
          "Spanish": re.compile(r"[ñ¿¡]"), "Portuguese": re.compile(r"[ãõÃÕ]"),
          "Italian": re.compile(r"[àèéìòù]"), "Danish": re.compile(r"[æøØÆ]"),
          "Swedish": re.compile(r"[åÅ]"), "Norwegian": re.compile(r"[æøØÆ]")}
CJK = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff]")
CYR = re.compile(r"[\u0400-\u04ff]")
STATED = re.compile(r"Language: ([A-Za-z]+)")
CODES = {"eng": "English", "english": "English", "ger": "German", "deu": "German", "german": "German",
         "fre": "French", "fra": "French", "french": "French", "jpn": "", "japanese": "",  # Japanese is not offered: see the note in the module docstring
         "ita": "Italian", "italian": "Italian", "spa": "Spanish", "spanish": "Spanish",
         "dut": "Dutch", "nld": "Dutch", "dutch": "Dutch", "rus": "Russian", "russian": "Russian",
         "lat": "Latin", "latin": "Latin", "por": "Portuguese", "portuguese": "Portuguese",
         "dan": "Danish", "danish": "Danish", "swe": "Swedish", "swedish": "Swedish",
         "nor": "Norwegian", "norwegian": "Norwegian", "chi": "Chinese", "zho": "Chinese",
         "san": "Sanskrit", "kor": "Korean", "cze": "Czech", "pol": "Polish", "hun": "Hungarian",
         "mul": "", "und": "", "": ""}


def words_of(title):
    t = unicodedata.normalize("NFC", title.lower())
    return [w for w in re.findall(r"[^\W\d_]+", t, re.UNICODE) if w not in IGNORE]


def guess(title, other=""):
    """(language, confidence 0-1, why). A title counts as English unless another language is positively
    indicated: by its own letters, or by at least two of its marker words (one is enough if it is a good
    part of a short title)."""
    m = STATED.search(other or "")
    if m:
        lang = CODES.get(m.group(1).lower(), m.group(1).title())
        if lang:
            return lang, 1.0, "stated by the source"
    if CJK.search(title):
        return "", 0.9, "Japanese script: language left undetermined"
    if CYR.search(title):
        return "Russian", 0.95, "Cyrillic script"
    ws = words_of(title)
    if not ws:
        return "English", 0.3, "no words to judge"
    hits = {l: [w for w in ws if w in mk] for l, mk in MARKERS.items()}
    hits = {l: h for l, h in hits.items() if h}
    letters = {l: rx.search(title) is not None for l, rx in STRONG.items()}
    score = {}
    for l in set(hits) | {l for l, v in letters.items() if v}:
        n = len(set(hits.get(l, [])))
        score[l] = n + (1.5 if letters.get(l) else 0) + (0.5 if n and len(hits[l]) / len(ws) >= 0.3 else 0)
    dec = {l: [w for w in ws if w in d] for l, d in DECISIVE.items()}
    dec = {l: h for l, h in dec.items() if h}
    if len(dec) == 1:
        l = next(iter(dec))
        return l, 0.85, f"{l}: {', '.join(sorted(set(dec[l]))[:4])}"
    if not score:
        return "English", 0.85, "no marker of another language"
    best = max(score, key=score.get)
    rest = sorted((v for k, v in score.items() if k != best), reverse=True)
    margin = score[best] - (rest[0] if rest else 0)
    if score[best] < 2:
        return "English", 0.5, f"only a weak sign of {best} ({', '.join(sorted(set(hits.get(best, []))))or 'letters'})"
    conf = min(0.95, 0.6 + margin / 4 + 0.05 * min(len(set(hits.get(best, []))), 4))
    return best, round(conf, 2), f"{best}: {', '.join(sorted(set(hits.get(best, [])))[:6])}{' + letters' if letters.get(best) else ''}"


def key(author, title, year):
    """The key a hand decision is filed under: author|title|year, folded to letters and digits. It does
    not move when rows are re-ordered, re-cased or added, which an id would."""
    from ia_lookup import norm
    return f"{norm(author or '')}|{norm(title or '')}|{norm(year or '')}"


def fixes():
    """{key: language} from language_fixes.tsv."""
    d = {}
    if os.path.exists(FIXES):
        for line in open(FIXES, encoding="utf-8"):
            if line.startswith("#"):
                continue
            p = line.rstrip("\n").split("\t")
            if len(p) >= 2 and p[0].strip():
                d[p[0].strip()] = p[1].strip()
    return d


def language_of(author, title, year, other=""):
    f = fixes()
    k = key(author, title, year)
    if k in f:
        return f[k], 1.0, "checked by hand"
    return guess(title, other)


if __name__ == "__main__":
    import sqlite3
    db = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "list.sqlite")
    con = sqlite3.connect(db)
    f, counts, doubtful = fixes(), {}, []
    for rid, author, title, year, other in con.execute("SELECT id, author, title, year, other FROM books"):
        k = key(author, title, year)
        lang, conf, why = (f[k], 1.0, "hand") if k in f else guess(title, other)
        counts[lang] = counts.get(lang, 0) + 1
        if conf < 0.75:
            doubtful.append((rid, lang, conf, why, title[:70]))
    print(sorted(counts.items(), key=lambda x: -x[1]))
    print("doubtful:", len(doubtful))
    for d in doubtful[:30]:
        print(" ", d)
