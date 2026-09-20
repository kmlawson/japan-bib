# japan-bib

A browsable database of Western-language works on Japan published 1850–1960, compiled from printed
bibliographies, with candidate links to scans on archive.org.

**Browse:** open the GitHub Pages site for this repository (`index.html`) — search (diacritics ignored),
filter by year / source / archive.org availability, sort, open an entry for full details, export CSV.

## Data

`list.sqlite`, table `books`:

| column | content |
|---|---|
| `author`, `title` | as printed in the source bibliography |
| `year` | as printed (`1874-75`, `n.d.`); `year_num` = first year as an integer (NULL if undated) |
| `edition`, `volume` | edition statement; volume statement or designation |
| `links` | archive.org URLs, one per line (`''` = searched, none found; NULL = undated, not searched) |
| `other` | imprint, extent, series, library holdings, catalogue page, transcription notes |
| `source` | which bibliography the entry comes from |

`books_fts` is an FTS5 index over author, title and other.

Sources so far: *Union Catalog of Books on Japan in Western Languages* (ed. Naomi Fukuda), entries dated
1850–1955. Entries were transcribed by eye from page scans (no OCR); unreadable details are left blank and
noted. archive.org links are title/author matches found with the `ia` command-line tool — candidates, not
verified identical editions.

The scans themselves and the per-page transcription files are not part of this repository.
