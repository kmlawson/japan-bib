# japan-bib

A browsable database of Western-language works on Japan published 1850–1950, compiled from printed
bibliographies, with candidate links to scans on archive.org.

**Browse:** open the GitHub Pages site for this repository (`index.html`) — search (diacritics ignored),
filter by year / source / type / archive.org availability (the list opens on the entries that have an
archive.org copy, with `open` and `borrow` badges; choose *Show: All entries* for everything), sort, open an entry for full details, export CSV.

## Data

`list.sqlite`, table `books`:

| column | content |
|---|---|
| `author`, `title` | as printed in the source bibliography |
| `year` | as printed (`1874-75`, `n.d.`); `year_num` = first year as an integer (NULL if undated) |
| `edition`, `volume` | edition statement; volume statement or designation |
| `links` | archive.org URLs, one per line (`''` = searched, none found; NULL = undated, not searched) |
| `other` | imprint, extent, series, library holdings, catalogue page, journal reference, the bibliographer's annotation, cross-references to the other bibliographies, transcription notes |
| `source` | the bibliographies that list the work, `; `-separated |
| `access` | how the best linked archive.org copy can be read: `open` (freely readable), `borrow` (controlled digital lending, free account), `''` (no link). Items that can be neither read nor borrowed (print-disabled readers only, or gone) are not linked at all. `links_access` gives the same flag for each URL in `links`, in the same order; open copies are listed first |
| `type` | `book`, `periodical`, `article` (in a journal) or `chapter` (part of a book) |

`books_fts` is an FTS5 index over author, title and other.

Sources so far:

1. *Union Catalog of Books on Japan in Western Languages* (ed. Naomi Fukuda) — book entries (transcribed to 1955).
2. Hugh Borton et al., *A Selected List of Books and Articles on Japan in English, French and German*
   (rev. ed., 1954) — all numbered entries (transcribed to 1960): books, journal articles and chapters, with
   Borton's annotations.
3. The bibliography of Kenneth Henshall, *Historical Dictionary of Japan to 1945* (2014) — works first
   published 1850–1950 (including those cited from a modern reprint).

Only works first published 1850–1950 (and undated ones) are in the database; later entries were
transcribed but are left out at build time.

Scanned sources were transcribed by eye from page images (no OCR); unreadable details are left blank and
noted. Henshall's bibliography is a born-digital text and was parsed from it.

**Duplicates.** Before a record from a later source is added it is compared with what is already in the
database: same author surname, same title proper, and publication years no more than three years apart
count as the same book. Such a record does not get a new row — the existing row gains the source name and
an "Also in …" cross-reference (with Borton's annotation) in `other`.

**archive.org links** are title/author matches found with the `ia` command-line tool — candidates, not
verified identical editions. An item dated within three years of the printed year is linked as the same
book (`links`); items with the same author and title but another date are listed in `other` as
`IA other editions`. Only books are looked up, not articles or chapters.
Entries with no candidate at all get a second, looser pass: key words of the title proper only, no author,
item dated within four years. Clear matches are taken automatically; edge cases (short titles, another
creator) were judged by hand. Rows linked this way say `IA match: loose` in `other`.

The scans themselves and the per-page transcription files are not part of this repository.
