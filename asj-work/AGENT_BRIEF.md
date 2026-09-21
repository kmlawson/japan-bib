# Brief: *Catalogue of the Books and Manuscripts in the Library of the Asiatic Society of Japan* (Tōkyō, 1888)

You are transcribing entries from page scans of this printed library catalogue. Page images (JPEG,
190 dpi) are at

    /private/tmp/claude-501/-Users-kml-Library-CloudStorage-Dropbox-biblio/aa42cad6-59e9-4e2f-a4a3-05a3900b8cdc/scratchpad/uiug/a-NN.jpg

NN = the **PDF page number**, zero-padded to two digits (a-05.jpg … a-34.jpg).

## Hard rule: read the scans with your own eyes

Open each JPEG with the Read tool and transcribe what YOU see. Do **not** use OCR, pdftotext, the
PDF's text layer, tesseract, the `apple-vision` or `llmimage` skills, or any other tool or service to
read the text, and do not delegate to sub-agents. If a detail is too small, make a higher-resolution
crop with

    pdftoppm -r 300 -f N -l N -x .. -y .. -W .. -H .. -png \
      "/Users/kml/Library/CloudStorage/Dropbox/biblio/uiug_30112087485733_3330.pdf" <your-folder>/crop

into your OWN sub-folder of the scratchpad (e.g. `scratchpad/asjNN/`) and read that yourself. Keep any
helper scripts in that same private folder.

A detail you cannot read is left **empty** with a `note` saying what was illegible — never guess a
digit or a name. Transcribe spellings and diacritics as printed (the catalogue prints "Maedchen",
"Tōkyō", "Yedo" and so on; keep them).

## Layout

The section is headed GENERAL CATALOGUE OF BOOKS (under authors' names in alphabetic order). A typical
entry is

    ADAMS (Arthur):—Travels of a Naturalist in Japan and Manchuria. London. 1870.
    ADAMS (Francis Ottiwell):—The History of Japan to 1864. 2 vols. London. 1874. Vol. II. missing.

that is: `AUTHOR (Forename):—Title. Place. Year.` sometimes followed by a number of volumes, a
remark by the compiler ("Vol. II. missing.", "Presented by ..."), a publisher or an issuing office.
Some entries have no year, no place, or no author (the heading is then a title or a body's name).
The running head at the top of the page is not an entry.

## What to record

**Every entry on the page**, in the order printed. Filtering happens afterwards, so do not leave
anything out — but do say what each entry is, with these fields:

- `kind`: `"book"` normally; `"periodical"` when the entry is a run or a number of a journal,
  magazine, newspaper, annual report or transactions ("Chrysanthemum, The. Vols. I-III."); `"manuscript"`
  when it says manuscript; `"map"` for a map or atlas.
- `japan`: `true` when the work is about Japan or partly about Japan (Japan in the title, the Japanese
  language, Japanese history, art, religion, law, flora, a voyage that takes in Japan, a work published
  in Japan about Japan); `false` when it is plainly about somewhere else only (China, Korea, Siam, India,
  Russia, a general work with no Japanese content); `"uncertain"` when the title does not say. Put your
  reason in `japan_why` in a few words. Do not agonise: the judgement is checked afterwards.

## Output: one JSONL file per page

Write `/Users/kml/Library/CloudStorage/Dropbox/biblio/asj-work/pages/pNN.jsonl` (NN = PDF page, e.g.
`p07.jsonl`) as soon as that page is done, before moving on. If a page file already exists, skip it.

The **first line of every page file** is a summary:

```json
{"pdf_page": 7, "entries_on_page": 11, "note": ""}
```

Then one line per entry, with exactly these keys:

```json
{"pdf_page": 7, "entry_no": 2, "author": "Adams (Arthur)", "title": "Travels of a Naturalist in Japan and Manchuria", "place": "London", "year": "1870", "year_num": 1870, "volumes": "", "kind": "book", "japan": true, "japan_why": "Japan in the title", "note": ""}
```

- `author`: as printed, surname first with the forename in brackets — "Adams (Arthur)". If the entry
  has no personal author, leave it empty and say so in `note`.
- `title`: as printed, without the final full stop. Keep a subtitle that follows a semicolon or colon.
- `place`, `year`: as printed; `year_num` the year as an integer, or `null` when none is printed.
- `volumes`: "2 vols." and the like, else "".
- `note`: the compiler's remark ("Vol. II. missing."), a publisher or office named in the entry, and
  anything you could not read.

Write the files with the Write tool or a small Python script using `json.dumps(..., ensure_ascii=False)`.
After finishing your range run

    python3 /Users/kml/Library/CloudStorage/Dropbox/biblio/asj-work/validate4.py START END

and fix anything it reports.

## Final report

Reply briefly: pages done, entries transcribed, how many you marked as Japan-related, and a list of
every cell you could not read (page, entry, field).
