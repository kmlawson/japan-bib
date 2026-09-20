# Brief: John W. Dower with Timothy S. George, *Japanese History and Culture from Ancient to Modern Times: Seven Basic Bibliographies* (2nd ed.)

You are transcribing entries from page scans of this bibliography. Page images (JPEG, 190 dpi) are at

    /private/tmp/claude-501/-Users-kml-Library-CloudStorage-Dropbox-biblio/aa42cad6-59e9-4e2f-a4a3-05a3900b8cdc/scratchpad/dower/d-NNN.jpg

NNN = zero-padded **PDF page number** (d-002.jpg … d-163.jpg). **Printed page = PDF page + 251**
(PDF p. 2 is printed p. 253; PDF p. 163 is printed p. 414).

## Hard rule: read the scans with your own eyes

Open each JPEG with the Read tool and transcribe what YOU see. Do NOT use OCR, pdftotext, the PDF's
text layer, tesseract, the `apple-vision` or `llmimage` skills, or any other tool or service to read the
text — the text layer of this PDF is machine OCR and is wrong in places. Do not delegate to sub-agents.
If a detail is too small, make a higher-resolution crop with
`pdftoppm -r 300 -f N -l N -x .. -y .. -W .. -H .. -png` on
`/Users/kml/Library/CloudStorage/Dropbox/biblio/Japanese history and culture from ancient to modern times _ -- Dower, John W_, George, Timothy.pdf`
into YOUR OWN sub-folder of the scratchpad (e.g. `scratchpad/dowerNNN/`) and read that yourself. Keep any
helper scripts in that same private sub-folder.

A detail you cannot read is left EMPTY with a `note` saying what was illegible — never guess a digit or a
name. Transcribe spellings and diacritics as printed.

## Layout

Single column, no entry numbers. A typical entry is

    Paul H. Clyde & Burton F. Beers.  THE FAR EAST: A HISTORY OF WESTERN IMPACTS AND
        EASTERN RESPONSES, 1830-1975.  6th edition.  1975; reprinted 1991: Waveland Press.

that is: `Author(s). TITLE IN CAPITALS. [edition.] YEAR: Publisher.` optionally followed by Dower's
comment in the same paragraph (a sentence or two, sometimes listing reviews).

- Journal articles: `Author. "Title," Journal Name 21.3-4 (1966), 333-345.`
- Chapters: `Author. "Title," in EDITOR, ed., BOOK TITLE (year: Publisher), pages.`
- `_____.` at the start of an entry means **the same author as the previous entry** — write that author's
  name in `author` and say so in `note`.
- Headings: the running head at the top of the page names the part (e.g. `JAPAN ABROAD`); bold headings
  inside the page name the section (e.g. `OVERVIEWS`, `THE PACIFIC WAR`). Record them together in
  `section` as `RUNNING HEAD / Section heading`. If your first page starts under a heading given on an
  earlier page, look back to find it.
- Lines like `[See also pp. 205-214]` are not entries.

## What to transcribe: only works first published 1850-1960

Judge by the **first (original) year** in the entry:

- `1975; reprinted 1991: Waveland Press.` → first published 1975 → **out of range, skip**.
- `1903; reprinted 1970: Tuttle.` → first published 1903 → **in range, transcribe**.
- `1930; 2nd edition 1965: X.` → 1930 → in range.
- An article dated `(1966)` → out of range. `(1959)` → in range.
- A work with no date at all → transcribe it with `"year": "n.d."`, `"year_start": null`, if it is
  plainly an older work; otherwise skip it and say so in the page summary note.

You still have to read every entry on the page to judge its date, but you only write out those in range.

## Output: one JSONL file per page

Write `/Users/kml/Library/CloudStorage/Dropbox/biblio/dower-work/pages/pNNN.jsonl` (NNN = PDF page, e.g.
`p045.jsonl`) as soon as that page is done, before moving on. If a page file already exists, skip it.

The **first line of every page file** is a summary, so that coverage can be checked later:

```json
{"pdf_page": 45, "printed_page": 296, "entries_on_page": 14, "in_range": 2, "sections": ["JAPAN ABROAD / THE PACIFIC WAR"], "note": ""}
```

Then one line per in-range entry, with exactly these keys:

```json
{"pdf_page": 45, "printed_page": 296, "entry_no": 1, "type": "book", "author": "Max Beloff", "title": "SOVIET POLICY IN THE FAR EAST, 1944-1951", "container": "", "edition": "", "publisher": "Oxford University Press", "year": "1953", "year_start": 1953, "section": "JAPAN ABROAD / THE SOVIET UNION", "annotation": "", "note": ""}
```

- `entry_no`: position of the entry on the page, counting **all** entries from 1 (so an in-range entry
  that is the fifth entry printed on the page has `entry_no` 5).
- `type`: `"book"`, `"article"` (in a journal), `"chapter"` (part of a book), or `"periodical"`.
- `author`: as printed, in the printed order ("Paul H. Clyde & Burton F. Beers"); keep `ed.`/`eds.`/`tr.`
  after the name if printed. Titles are printed in capitals — transcribe them **as printed** (capitals).
- `container`: journal or book reference for articles and chapters, as printed; "" for books.
- `edition`: e.g. "6th edition", "Revised edition"; else "".
- `publisher`: the publisher after the year; "" if none printed. Dower gives no place of publication.
- `year`: the whole date statement as printed (e.g. `"1903; reprinted 1970"`); `year_start`: the first
  year as an integer.
- `annotation`: Dower's comment, verbatim; "" if none.
- `note`: your own remarks — illegible cells, `_____.` resolved, oddities. "" otherwise.

Write the files with the Write tool or a small Python script using `json.dumps(..., ensure_ascii=False)`.
After finishing your range run

    python3 /Users/kml/Library/CloudStorage/Dropbox/biblio/dower-work/validate3.py START END

and fix anything it reports.

## Final report

Reply briefly: pages done, total entries seen, entries in range, and a list of every cell you could not
read (page, entry, field).
