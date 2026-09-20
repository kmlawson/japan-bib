# japan-bib

A browsable database of Western-language works on Japan published 1850–1960, compiled from printed
bibliographies, with candidate links to scans on archive.org.

**Browse:** open the GitHub Pages site for this repository (`index.html`) — search (diacritics ignored),
filter by year / source / type / archive.org availability, sort, open an entry for full details, export CSV.

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
| `type` | `book`, `periodical`, `article` (in a journal) or `chapter` (part of a book) |

`books_fts` is an FTS5 index over author, title and other.

Sources so far:

1. *Union Catalog of Books on Japan in Western Languages* (ed. Naomi Fukuda) — book entries dated 1850–1955.
2. Hugh Borton et al., *A Selected List of Books and Articles on Japan in English, French and German*
   (rev. ed., 1954) — all numbered entries dated 1850–1960: books, journal articles and chapters, with
   Borton's annotations.
3. The bibliography of Kenneth Henshall, *Historical Dictionary of Japan to 1945* (2014) — works first
   published 1850–1960 (including those cited from a modern reprint).

Scanned sources were transcribed by eye from page images (no OCR); unreadable details are left blank and
noted. Henshall's bibliography is a born-digital text and was parsed from it.

**Duplicates.** Before a record from a later source is added it is compared with what is already in the
database: same author surname, same title proper, and publication years no more than three years apart
count as the same book. Such a record does not get a new row — the existing row gains the source name and
an "Also in …" cross-reference (with Borton's annotation) in `other`.

**archive.org links** are title/author matches found with the `ia` command-line tool — candidates, not
verified identical editions. For the two later sources a match dated within three years of the printed
year is linked as the same book; matches further away are listed in `other` as other editions. Only
books are looked up, not articles or chapters.

The scans themselves and the per-page transcription files are not part of this repository.
