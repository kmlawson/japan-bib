# Brief: Wenckstern / Nachod, *A Bibliography of the Japanese Empire 1906–1926*

You are transcribing entries from page scans of this printed bibliography. Page images (JPEG, 190 dpi)
are at

    /private/tmp/claude-501/-Users-kml-Library-CloudStorage-Dropbox-biblio/aa42cad6-59e9-4e2f-a4a3-05a3900b8cdc/scratchpad/bje/b-NNN.jpg

NNN = the **PDF page number**, zero-padded to three digits (b-001.jpg …). **Printed page = PDF page + 149**
(PDF p. 1 is printed p. 150).

## Hard rule: read the scans with your own eyes

Open each JPEG with the Read tool and transcribe what YOU see. Do **not** use OCR, pdftotext, the PDF's
text layer, tesseract, the `apple-vision` or `llmimage` skills, or any other tool or service that reads
an image for you, and do not delegate to sub-agents. If a detail is too small, crop it at a higher
resolution with

    pdftoppm -r 300 -f N -l N -x .. -y .. -W .. -H .. -png \
      "/Users/kml/Library/CloudStorage/Dropbox/biblio/Bibliography of the Japanese Empire 1906-1926.pdf" <your-folder>/crop

into your OWN sub-folder of the scratchpad (e.g. `scratchpad/bje001/`) and read that yourself.

A detail you cannot read is left **empty** with a `note` saying what was illegible — never guess a digit
or a name. Transcribe spellings and diacritics as printed.

## What the page looks like

Numbered entries, the author's surname in small capitals, the apparatus in German. Two kinds:

**A book** — place, publisher, year, extent, sometimes a price or format:

    141 ANDERSON, J. The spell of Japan. Boston, Page. 1914. 414 S. Abb. Krtn. 2.50 $.
    145 BALLARD, G. A. The influence of the sea on the political history of Japan. London, Murray.
        1921. XIX, 311 S. Krtn. 18 Sh.

**An article** — a periodical, a volume (Bd.), a year and pages (S. 344—350):

    707 FRANCONIE, J. Le Japon en 1906. Bulletin du Comité de l'Asie Française. 1906. S. 344—350.
    713 FUKUCHI, H. The Satsuma Rebellion. The Japan Magazine. Bd. 7, 1916/17. S. 41—44.

Other things to know:

- An entry beginning with a dash (`— Okuma and the New Era…`) repeats **the author of the entry
  above**. Put that author's name in `author` and say so in `note`.
- Smaller type under an entry is the compiler's remark (a biography of the author, a note on contents).
  Record it only when it says something bibliographic — a language, a translation, another edition,
  "In russischer Sprache" — and then only that part, in `note`. Do not copy the biographical dates.
- Headings ("II. HISTORY", "B. Works on the different periods", "1. Prehistory…") are not entries.
  Record the section on each entry in `section` as the nearest heading (e.g. `II. HISTORY / A. General works`);
  look back a page if the section starts before your range.
- `S.` is *Seiten*, pages. `Bd.` is a volume of a periodical. `Abb.` illustrations, `Krtn.` maps.

## What to record

**Books only.** The compiler wants books, not journal articles, and no Russian-language material.

For every entry on the page, decide which it is:

- a **book** (or pamphlet, report, atlas, separately published work) **not in Russian** and published
  **1850 or later** → write it out in full, as below;
- an **article** in a periodical → one short line: `{"pdf_page": 1, "entry_no": 707, "skip": "article"}`
- **Russian** (the entry is printed in Cyrillic, or the remark says "In russischer Sprache") → one short
  line with `"skip": "russian"` — even when it is a book;
- published **before 1850**, or no date at all and plainly older → `"skip": "out of range"`;
- anything you cannot place → transcribe it in full and say why in `note`.

The short lines matter: they are how the coverage of a page is checked, so every entry number on the
page must appear in the file exactly once, in printed order.

## Output: one JSONL file per page

Write `/Users/kml/Library/CloudStorage/Dropbox/biblio/bje-work/pages/pNNN.jsonl` (NNN = PDF page, e.g.
`p007.jsonl`) as soon as that page is done, before moving on. If the file already exists, skip that page.

The **first line of every page file** is a summary:

```json
{"pdf_page": 7, "printed_page": 156, "entries_on_page": 15, "books": 6, "skipped": 9, "sections": ["II. HISTORY / A. General works"], "note": ""}
```

Then one line per entry, in printed order. A book:

```json
{"pdf_page": 7, "entry_no": 141, "author": "Anderson, J.", "title": "The spell of Japan", "place": "Boston", "publisher": "Page", "year": "1914", "year_num": 1914, "extent": "414 S.", "edition": "", "series": "", "language": "English", "section": "II. HISTORY / A. General works", "note": ""}
```

A skipped entry:

```json
{"pdf_page": 7, "entry_no": 707, "skip": "article"}
```

- `author`: surname first, as printed, with the forename or initials after a comma — "Anderson, J.",
  "Brandt, M. v.". A corporate or anonymous heading goes in as printed; an entry printed as
  `(ANEKI, SHIGENO)` keeps its brackets. Leave empty for a work with no author and say so in `note`.
- `title`: as printed, without the final full stop. Keep a subtitle after the colon.
- `place`, `publisher`: as printed ("Boston", "Page"; "Leipzig", "O. Wigand"). Empty if not printed
  ("Ohne Ort" means no place: leave empty and note it).
- `year`: as printed; `year_num`: the year as an integer (for "1912/13" use 1912; for "um 1907" use 1907
  and note it).
- `extent`: "414 S.", "XIX, 311 S.", "2 Bde." and so on, as printed.
- `edition`: "2. Auflage", "6th edition", else "".
- `series`: what follows `=` in the entry (a series statement), else "".
- `language`: the language **of the book**, judged from its title — English, German, French, Italian,
  Spanish, Dutch, Portuguese, Danish, Swedish, Norwegian, Polish, Czech, Hungarian, Latin, Japanese …
  If you cannot tell, leave it empty.
- `note`: the compiler's bibliographic remark, a resolved dash-entry, an oddity, anything illegible.

Write the files with the Write tool or a small Python script using `json.dumps(..., ensure_ascii=False)`.
After finishing your range run

    python3 /Users/kml/Library/CloudStorage/Dropbox/biblio/bje-work/validate5.py START END

and fix whatever it reports.

## Final report

Reply briefly: pages done, entries seen, books written out, how many were skipped as articles / Russian /
out of range, and a list of every cell you could not read (page, entry, field).
