# japan-bib

A searchable database of Western-language works on Japan published 1850–1955, compiled from printed
bibliographies and library catalogues, with links to copies that can be read online. It is published as
a static page — the browser loads SQLite and queries the database itself — at
<https://kmlawson.github.io/japan-bib/>, where it sits under a list of primary sources for modern
Japanese history.

As things stand: **10,917 entries, 4,042 with an online copy** (3,562 freely readable, 480 borrowable).

How to publish, and what the site actually needs, is in [DEPLOY.md](DEPLOY.md).

## Where the entries come from

| source | what was taken |
|---|---|
| *Union Catalog of Books on Japan in Western Languages*, ed. Naomi Fukuda (1968) | its book entries, transcribed to 1955 |
| Borton, Elisséeff, Lockwood and Pelzel, *A Selected List of Books and Articles on Japan* (1954) | every numbered entry to 1960: books, articles, chapters, with Borton's annotations |
| Dower with George, *Japanese History and Culture from Ancient to Modern Times* (2nd ed., 1995) | works first published 1850–1960 |
| Nachod, *Bibliography of the Japanese Empire 1906–1926* (1928) | its book entries; articles and Russian-language works were read but not kept |
| Asiatic Society of Japan, *Catalogue of the Books and Manuscripts in the Library* (1888) | its Japan-related books, periodicals excepted |
| Henshall, *Historical Dictionary of Japan to 1945* (2014) | works first published 1850–1955 |
| Nichibunken, 日本関係欧文図書目録 | the works it lists for 1850–1900 |
| National Diet Library digital collections | items supplied as a list of links, described from the NDL's own metadata |
| *Japan Online*, a Zotero collection | books whose online copies were checked by hand, open and borrow-only |
| Items chosen by hand | archive.org, the National Library of Norway, Europeana, Alvin, HathiTrust, the Wolfsonian, BNE Digital |

Copies were also looked for at **archive.org** (every book), **Gallica** (the French entries), **The
Online Books Page** (everything with no copy yet), **Hispana** and **BNE Digital** (the Spanish
entries).

Only works first published 1850–1955, and undated ones, are published; entries outside that range were
transcribed and are kept in the working copy. The compilers' own annotations are kept in the working
copy too, and stripped from what is published.

## How the sources were read

Every scanned bibliography was **transcribed by eye from page images** — no OCR, no PDF text layer, no
image-description service, for me or for the sub-agents who read parts of the ranges. A detail that
could not be read is left empty with a note saying so; a printed error is transcribed as printed and
flagged rather than corrected. Each page becomes one JSONL file, checked by a validator that also
makes sure every entry number on a page is accounted for. Henshall's bibliography is born-digital and
was parsed; the library catalogues answer machine interfaces and were read from those.

The page transcriptions, the scans and the lookup caches stay local: they are not in this repository.

## The database

`list.sqlite`, table `books`:

| column | content |
|---|---|
| `author`, `title` | as the source prints them. English titles are set in title case, without the catalogue's final stop |
| `year` | as printed (`1874-75`, `n.d.`); `year_num` is the first year as an integer, NULL when undated |
| `edition`, `volume` | edition statement; volume statement or designation |
| `links` | copies online, one URL per line (`''` = searched, nothing found; NULL = undated, not searched) |
| `access` | how the best copy can be read: `open`, `borrow` (controlled lending, free account), `''`. Copies that can be neither read nor borrowed are not linked at all. `links_access` gives the same for each URL, in order |
| `links_checked` | `1` for a link checked by hand, else `0`, in the same order; hand-checked links come first |
| `other` | imprint, extent, series, holdings, catalogue page, journal reference, cross-references to the other bibliographies, notes |
| `source` | the bibliographies and catalogues that list the work, `; `-separated |
| `language` | from the source's own statement where there is one, otherwise worked out from the title (`union-catalog-work/language.py`; hand decisions in `language_fixes.tsv`) |
| `type` | `book`, `periodical`, `article`, `chapter` |

`books_fts` is an FTS5 index over author, title and other. Latin and Vietnamese entries are left out of
the published copy (Latin for the time being); the working copy keeps them, so it is reversible by
editing `HIDE_LANGUAGES` in `build_db.py`.

**Duplicates.** A record from a later source is compared with what is already there — same surname,
matching title proper, years within three — and a match adds the source name and an "Also in …"
cross-reference rather than a new row.

**Links.** archive.org matches are found by title and author: a copy dated within three years of the
printed year is linked as the same book, others are noted in `other` as `IA other editions`. Entries
with no candidate get a looser second pass (title key words, no author, four years), with the doubtful
ones judged by hand. Links from Gallica, the Online Books Page, Hispana and the rest were scored the
same way, and every doubtful case was settled by hand in a decisions file beside the script that found
it. Hand decisions are keyed to author|title|year folded to letters and digits, not to a row id, so
they survive a rebuild.

## Building

    python3 union-catalog-work/build_db.py     # list.sqlite, and the working copy list-full.sqlite
    python3 union-catalog-work/build_list.py   # list.md and the working notes
    python3 next-bib-work/build_list2.py
    python3 build_page.py                      # index.html, and the two downloads with it

`build_page.py` assembles `index.html` from `page/modern-japan.md` (the list of primary sources) and
`site/app.html`, `site/app.css`, `site/app.js`, `site/page.css` (the search and the look of the page);
`--from PATH` copies in a newer markdown first, `--no-bump` leaves the version number alone, and
`--no-downloads` skips rebuilding `downloads/japan-bib.md` and `.pdf`. **`index.html` is generated —
edit the parts in `site/`, not the page.** A bullet ending in `<!--pills-->` turns its indented list,
or itself, into small link bubbles.

## The work folders

Each source has a folder with the scripts that read it, its validator, and the decisions made by hand:

- `union-catalog-work/` — the Union Catalog, the language rules, and `build_db.py`, which assembles everything
- `next-bib-work/` — Borton and Henshall, and the archive.org access classification
- `dower-work/`, `asj-work/`, `bje-work/` — Dower & George, the Asiatic Society catalogue, Nachod
- `zotero-work/`, `extra-work/`, `libraries-work/` — the collections and items chosen by hand
- `ndl-work/`, `nichibun-work/` — the National Diet Library, Nichibunken
- `gallica-work/`, `onlinebooks-work/`, `hispana-work/`, `bne-work/` — the searches for copies

`bne-work/chrome.py` drives an ordinary Chrome window through AppleScript, because the Biblioteca
Nacional de España refuses every script: curl, full browser headers and headless Chrome alike get 403.
It needs View ▸ Developer ▸ Allow JavaScript from Apple Events.

## Conventions

- Nothing identifying goes into the repository or into a request: the scripts send a plain descriptive
  User-Agent, with no contact address and no account.
- HathiTrust is not searched automatically — it answers scripts with 403 — and its links appear only
  where the compiler checked that the copy can be read outside the United States.
- A link that turns out to be wrong or unreadable is named in a decisions file with the reason, so a
  rebuild does not bring it back.
