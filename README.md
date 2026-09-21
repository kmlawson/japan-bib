# japan-bib

A browsable database of Western-language works on Japan published 1850–1955, compiled from printed
bibliographies, with candidate links to scans on archive.org.

**Browse:** open the GitHub Pages site for this repository (`index.html`) — search (diacritics ignored),
filter by year / source / type / language / archive.org availability (the list opens on the entries that have an
archive.org copy, with `open` and `borrow` badges; choose *Show: All entries* for everything), sort, open an entry for full details, export CSV.

## Data

`list.sqlite`, table `books`:

| column | content |
|---|---|
| `author`, `title` | as printed in the source bibliography |
| `year` | as printed (`1874-75`, `n.d.`); `year_num` = first year as an integer (NULL if undated) |
| `edition`, `volume` | edition statement; volume statement or designation |
| `links` | URLs of online copies (archive.org, or dl.ndl.go.jp for items from source 5), one per line (`''` = searched, none found; NULL = undated, not searched) |
| `other` | imprint, extent, series, library holdings, catalogue page, journal reference, the bibliographer's annotation, cross-references to the other bibliographies, transcription notes |
| `source` | the bibliographies that list the work, `; `-separated |
| `access` | how the best linked copy can be read (National Diet Library items are freely readable): `open` (freely readable), `borrow` (controlled digital lending, free account), `''` (no link). Items that can be neither read nor borrowed (print-disabled readers only, or gone) are not linked at all. `links_access` gives the same flag for each URL in `links`, in the same order; open copies are listed first |
| `links_checked` | `1` for a link checked by hand or supplied directly (sources 4 and 5), else `0`, same order as `links`. Hand-checked links are always kept and listed first, with the access they were checked to have |
| `language` | language of the work: taken from the source's statement where there is one, otherwise worked out from the title (`union-catalog-work/language.py`; the decisions made by hand are in `language_fixes.tsv`) |
| `type` | `book`, `periodical`, `article` (in a journal) or `chapter` (part of a book) |

`books_fts` is an FTS5 index over author, title and other.

Latin and Vietnamese entries are left out of the published `list.sqlite` (Latin only for the time being);
the working copy keeps them, so the choice is reversible by editing `HIDE_LANGUAGES` in `build_db.py`.

The annotations written by the compilers of the printed bibliographies (Borton's comments on each work,
and the same text where it appears in an "Also in …" cross-reference) are **not published**: they are kept
in the working copy of the database but stripped from `list.sqlite` and from the site.

Sources so far:

1. *Union Catalog of Books on Japan in Western Languages* (ed. Naomi Fukuda) — book entries (transcribed to 1955).
2. Hugh Borton, Serge Elisséeff, William W. Lockwood and John C. Pelzel, *A Selected List of Books and
   Articles on Japan in English, French and German*
   (rev. ed., 1954) — all numbered entries (transcribed to 1960): books, journal articles and chapters, with
   Borton's annotations.
3. The bibliography of Kenneth Henshall, *Historical Dictionary of Japan to 1945* (2014) — works first
   published 1850–1955 (including those cited from a modern reprint).
4. *Japan Online*, a Zotero collection of books on Japan whose online copies (nearly all on archive.org) were
   checked by hand, exported in two parts: openly readable and borrow-only.
5. Items from the **National Diet Library** digital collections (dl.ndl.go.jp), supplied as a list of links
   and described from the NDL's own OAI-PMH metadata.

Only works first published 1850–1955 (and undated ones) are in the database; later entries were
transcribed but are left out at build time.

Scanned sources were transcribed by eye from page images (no OCR); unreadable details are left blank and
noted. Henshall's bibliography is a born-digital text and was parsed from it.

**Hand-checked links.** A Zotero item that is already in the database (its archive.org item is already linked
from an entry describing the same work, or same author and title with years within three) is merged into that
entry: the fuller of the two descriptions is shown, the other is kept as a note, and the hand-checked link goes
first. Where the hand-made record shows that an automatic link pointed at a different work, that link is removed.

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

## Gallica

`gallica-work/gallica_search.py` asks the BnF's SRU API for the French-language entries that have no copy yet (one query at a time, nothing identifying sent); `gallica_score.py` scores the candidates and `gallica_decisions.tsv` holds the verdicts made by hand. `gallica_merge.py` attaches the accepted copies when the database is built - they are public-domain scans, so they count as `open`.

## Dower & George

`dower-work/` holds the entries read by eye from Dower & George, *Japanese History and Culture from Ancient to Modern Times* (2nd ed., 1995), one JSONL file per page (kept local), the validator, and `dower_merge.py`, which puts them into the database. It runs after every other source so that existing row ids do not move; `ia_lookup3.py` looks the new books up on archive.org. Six pages of the scan are failed exposures and could not be read - see `dower-work/DOWER_NOTES.md`.

## The Online Books Page

`onlinebooks-work/ob_search.py` searches onlinebooks.library.upenn.edu for the entries that still have no copy (one search every five seconds, the Crawl-delay their robots.txt asks for; HathiTrust copies are not kept). `ob_score.py` scores the candidates, `ob_decisions.tsv` holds the verdicts made by hand, and `ob_merge.py` attaches the accepted copies when the database is built.

The published database is limited to works dated **1850-1955**, and that applies to every source, including items picked by hand (post-1950 books in the Zotero collection, one 1957 NDL title, Medhurst 1830): they stay in the working copy `union-catalog-work/list-full.sqlite` but are not published.

## Titles and dates

English titles are stored in title case and without the full stop the catalogues print at the end (`titlecase_en` / `trim_stop` in `build_db.py`); titles in other languages are left as the source has them. A title the source garbles can be corrected in `union-catalog-work/title_fixes.tsv`.

Rows dated later than `LAST_YEAR` are now deleted from the published database *after* the ids are given out, so moving the cut does not renumber anything. Hand decisions and the copies found on Gallica and The Online Books Page are keyed to author|title|year folded to letters and digits (`language.key`), not to the id, so they survive a rebuild.

## Items added by hand

`extra-work/ids.txt` lists archive.org items chosen by hand. `extra_fetch.py` fetches their metadata (plain HTTPS, nothing identifying sent), and `extra_merge.py` attaches each one to the entry it belongs to or adds a row for it, with source `KML Additions` and the link marked as checked by hand.
