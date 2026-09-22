# Brief: Wenckstern, *A Bibliography of the Japanese Empire*, vol. II (1907)

You are transcribing entries from page scans of this printed bibliography (literature on Japan
published 1894–1906, with a supplement to Pagès and a list of Swedish literature). Page images
(JPEG, 190 dpi) are at

    /private/tmp/claude-501/-Users-kml-Library-CloudStorage-Dropbox-biblio/6954005a-94a5-4287-ba4e-b53dd18cc95f/scratchpad/wenck/w-NNN.jpg

NNN = the **PDF page number**, zero-padded to three digits (w-021.jpg …). Three parts of the book:

| part | PDF pages | printed page |
|---|---|---|
| the main bibliography, sections I–XXIII | 21–461 | PDF − 20 |
| Supplement to L. Pagès, *Bibliographie japonaise* | 509–536 | PDF − 508 |
| Palmgren, *Systematic List of the Literature in Swedish Language on the Empire of Japan* | 537–558 | PDF − 536 |

## Hard rule: read the scans with your own eyes

Open each JPEG with the Read tool and transcribe what YOU see. Do **not** use OCR, pdftotext, the PDF's
text layer, tesseract, the `apple-vision` or `llmimage` skills, or any other tool or service that reads
an image for you, and do not delegate to sub-agents. If a detail is too small, crop it at a higher
resolution with

    pdftoppm -r 300 -f N -l N -x .. -y .. -W .. -H .. -png \
      "/Users/kml/Library/CloudStorage/Dropbox/biblio/bibliographyofja0002frvo.pdf" <your-folder>/crop

into your OWN sub-folder of the scratchpad (e.g. `scratchpad/wenck021/`) and read that yourself.

A detail you cannot read is left **empty** with a `note` saying what was illegible — never guess a digit
or a name. Transcribe spellings and diacritics as printed.

## What the page looks like

The entries are **not numbered**. Each begins with the author's name in bold type, surname first, then
the title, the extent, the format, the place and the year, often a price in parentheses:

    Van Bergen, R.  A boy of Old Japan, 239 pp. with reproduction of eight
      Japanese colour prints, 8vo., Boston, 1901. ($1.25c.)
    Bujac, E.  La guerre sino-japonaise, 328 pp. with 18 maps and sketches,
      8vo., Paris, 1896. (fr. 5)

A journal article has the periodical in parentheses, with volume and pages:

    Wigmore, J. H.  Parliamentary affairs in Japan. (Nation, vol. 54, pp.
      85-...), New York, 1892.
    Bartlett, E. A.  The war between China and Japan. (Asiatic Quarterly
      Review, second Series, vol. IX., pp. 1-20) 8vo., Woking, 1895.

Other things to know:

- Under many entries is a remark in the same type, indented ("A story describing the political events
  of 1853 to 1864." / "Re-issued with a title page dated London 1897." / "Contents: Vol. I. …"). It is
  part of the entry above, not a new entry. Record only what is bibliographic — another edition, a
  translation, a language, a date supplied in brackets — briefly, in `note`. Do not copy contents
  lists or summaries.
- A subject heading joined to the author with a colon and dash, `Verbeck:—Griffis, Wm. E.`, is a
  heading: the author is Griffis. Put the heading in `note`. A corporate heading such as
  `United States:—Navy Department` is the author as printed.
- `B[oissonnade] G.` — square brackets are the compiler's completions; keep them.
- A date printed as `no date, (1896)` or `no date [1899]` is transcribed as printed in `year`
  (`no date [1896]`), with `year_num` 1896.
- An entry beginning with a dash instead of a name repeats **the author of the entry above**. Put that
  name in `author` and say so in `note`.
- Section headings (`e.—History of the War against China in 1894-95.`, `c.—Travels in Japan.`) and
  the parenthetical cross-references under them are not entries. The running head at the top of the
  page gives the chapter (`VIII: HISTORY`). Record `section` as chapter and nearest sub-heading, e.g.
  `VIII. History / e. History of the War against China in 1894-95`; look back a page when the
  sub-heading started before your range.
- `8vo.`, `4to.`, `fol.`, `16mo.` are formats; `pp.` pages; `l.` leaves; `pl.` plates.
- In the Supplement to Pagès most works are from the 16th–18th centuries and will be out of range;
  what matters there is the few dated 1850 or later.
- In the Swedish list many entries are newspaper and magazine articles (Svenska Dagbladet, Ymer …):
  articles as elsewhere. `Sur le Japon pp. …` under an entry is a cross-reference, put nothing down for it.

## What to record

**Books only.** Every separately published work — book, pamphlet, report, map, atlas, printed
calendar, dissertation, a translation of a Japanese text — that is **not in Russian** and published
**1850 or later** is written out in full. Everything else gets one short line.

For every entry on the page, decide which it is:

- a **book** as above → write it out in full, as below; a work with no date at all is still a book
  (leave `year` empty, `year_num` null) unless it is plainly older;
- an **article** in a periodical or newspaper, or a part of another work (`(In: Churchill, …, vol. I,
  pp. 412-417)`, a chapter, a paper in the proceedings of a society) → `"skip": "article"`;
- **Russian** (the entry is printed in Cyrillic, or is said to be in Russian) → `"skip": "russian"`,
  even when it is a book;
- published **before 1850** → `"skip": "out of range"`;
- anything you cannot place → transcribe it in full and say why in `note`.

The short lines matter: they are how the coverage of a page is checked, so every entry on the page
must appear in the file exactly once, in printed order, numbered `seq` 1, 2, 3 … from the top of the
page. An entry that began on the previous page and only ends on this one is **not** counted again:
it was recorded where it began; say so in the page summary's `note`.

## Output: one JSONL file per page

Write `/Users/kml/Library/CloudStorage/Dropbox/biblio/wenck-work/pages/pNNN.jsonl` (NNN = PDF page,
e.g. `p022.jsonl`) as soon as that page is done, before moving on. If the file already exists, skip
that page.

The **first line of every page file** is a summary:

```json
{"pdf_page": 22, "printed_page": 2, "entries_on_page": 11, "books": 6, "skipped": 5, "sections": ["I. General and Miscellaneous Works"], "note": ""}
```

Then one line per entry, in printed order. A book:

```json
{"pdf_page": 140, "seq": 2, "author": "Van Bergen, R.", "title": "A boy of Old Japan", "place": "Boston", "publisher": "", "year": "1901", "year_num": 1901, "extent": "239 pp., 8vo.", "edition": "", "series": "", "language": "English", "section": "VIII. History / d. Modern History of Japan from the Opening up until 1894", "note": "With reproduction of eight Japanese colour prints. Remark: a story describing the political events of 1853 to 1864."}
```

A skipped entry:

```json
{"pdf_page": 140, "seq": 5, "skip": "article"}
```

- `author`: surname first, as printed, with the forename or initials after the comma — "Bujac, E.",
  "Brinkley, F.", "Griffis, Wm. E.". A corporate or anonymous heading goes in as printed. Leave empty
  for a work entered under its title and say so in `note`. Two authors: "Eastlake, F. W. and Y. Yamada".
- `title`: as printed, without the final stop or comma. Keep a subtitle. Stop before the extent.
- `place`, `publisher`: as printed. Wenckstern rarely names a publisher; leave it empty then.
- `year`: as printed; `year_num`: the first year as an integer ("1901-2" → 1901; "no date [1896]" → 1896).
- `extent`: pagination and format, as printed ("239 pp., 8vo."; "2 vols., 4to."; "12 maps, fol.").
  Illustration statements may go in `note`.
- `edition`: "second edition", "2. Aufl.", else "".
- `series`: a series statement ("Forms No. 77 of the Neue Missionsschriften" → "Neue Missionsschriften, No. 77"), else "".
- `language`: the language **of the book**, judged from its title — English, German, French, Italian,
  Spanish, Dutch, Portuguese, Danish, Swedish, Norwegian, Latin, Japanese, Esperanto … If you cannot
  tell, leave it empty.
- `note`: the compiler's bibliographic remark, a heading, a resolved dash-entry, an oddity, anything illegible.

Write the files with the Write tool or a small Python script using `json.dumps(..., ensure_ascii=False)`.
After finishing your range run

    python3 /Users/kml/Library/CloudStorage/Dropbox/biblio/wenck-work/validate7.py START END

and fix whatever it reports.

## Final report

Reply briefly: pages done, entries seen, books written out, how many were skipped as articles / Russian /
out of range, and a list of every cell you could not read (page, seq, field).

## Two later instructions from the compiler

- **Books and standalone pamphlets or reports only.** An article gets a bare `{"pdf_page": N, "seq": k, "skip": "article"}` line, nothing more: do not spend time describing it.
- A chapter or section on a subject **not related to Japan or the Japanese empire** (e.g. XXI, works by
  Japanese on other subjects) is still transcribed page by page so the coverage check holds, but it is left
  out at the merge stage by `wenck_merge.py`; you need do nothing special beyond recording `section`.
