# Deploying the site

The site is six static files. There is no server code, no database server and nothing to install at
the far end: the page loads SQLite into the browser and queries `list.sqlite` there.

| file | size | what it is |
|---|---|---|
| `index.html` | ~76 KB | the whole page — markup, styles and script are inlined when it is built |
| `list.sqlite` | ~7.3 MB | the bibliography, fetched by the page when it loads |
| `vendor/sql-wasm.js` | ~52 KB | the sql.js loader, the only `src=` on the page |
| `vendor/sql-wasm.wasm` | ~640 KB | the SQLite engine it loads |
| `downloads/japan-bib.md` | ~2.3 MB | the whole list as Markdown, behind the MD button |
| `downloads/japan-bib.pdf` | ~3 MB | the same list as a PDF, behind the PDF button |

`vendor/` and `downloads/` must stay folders beside `index.html`, and `list.sqlite` must sit next to it:
both are fetched by relative path (`fetch("list.sqlite")`), so the site works from any directory,
including a subdirectory such as `/japan-bib/`.

Everything else in the repository is source: the scripts that make those files, and the notes that
explain how. None of it is needed to serve the site.

## Publishing as it stands

The site is GitHub Pages, serving the root of `main` at <https://kmlawson.github.io/japan-bib/>.
Publishing is a push:

    git add -A
    git commit -m "..."
    git push origin main

Pages rebuilds in a minute or two. To be sure the new files are really out there, compare what is
live with what is local — the sizes can coincide, so compare hashes:

    python3 - <<'EOF'
    import hashlib, urllib.request
    for name in ("index.html", "list.sqlite"):
        loc = hashlib.sha256(open(name, "rb").read()).hexdigest()
        url = "https://kmlawson.github.io/japan-bib/" + (name if name != "index.html" else "")
        req = urllib.request.Request(url, headers={"User-Agent": "japan-bib/1.0 (deploy check)"})
        live = hashlib.sha256(urllib.request.urlopen(req).read()).hexdigest()
        print(name, "live matches local" if loc == live else "NOT YET LIVE")
    EOF

## Making the built files

**The page.** Edit `page/modern-japan.md` (or pass a newer copy with `--from`) and build:

    python3 build_page.py
    python3 build_page.py --from "/path/to/modern-japan.md"     # copy it in first, then build
    python3 build_page.py --no-bump                             # rebuild without a new version number

This writes `index.html` from the markdown, `site/app.html`, `site/app.css`, `site/app.js` (the
search) and `site/page.css` (everything around it), and raises the number in `page/version.txt`,
which appears at the foot of the page with the build date. It then runs `build_downloads.py`, which
writes `downloads/japan-bib.md` and `downloads/japan-bib.pdf` from the current `list.sqlite`, stamped
with the same version and date; `--no-downloads` leaves them alone, and `build_downloads.py --no-pdf`
writes only the Markdown. The PDF needs pandoc and xelatex (about 40 seconds for 500 pages); if it
cannot be made the script says so, and the page's PDF button would 404, so read what the build prints
before publishing. **`index.html` is generated — never edit it by hand**; edit the parts in `site/` and build again.

**The database.**

    python3 union-catalog-work/build_db.py

writes `list.sqlite` (published: without the bibliographers' annotations, without the languages
that are hidden, and only 1850-1955) and `union-catalog-work/list-full.sqlite` (the working copy,
which keeps everything and stays out of the repository). It draws on the transcriptions, caches and
hand decisions in the `*-work/` folders; the transcriptions and caches are local files that are not
in the repository, so a clean clone can rebuild the page but not the database.

After changing the database, also run the two list builders, which keep `list.md` and the working
notes in step:

    python3 union-catalog-work/build_list.py
    python3 next-bib-work/build_list2.py

## Somewhere other than GitHub Pages

Copy these files, keeping the folder shape:

    index.html
    list.sqlite
    vendor/sql-wasm.js
    vendor/sql-wasm.wasm
    downloads/japan-bib.md
    downloads/japan-bib.pdf

Two things a host has to get right:

- **`.wasm` must be served as `application/wasm`.** GitHub Pages does; some hosts and most "open the
  file in a browser" setups do not, and the page then fails to load the engine. (Opening
  `index.html` from `file://` does not work for the same reason, and because `fetch` is blocked.)
- **the two files in `downloads/` are big** (5 MB together). They are ordinary static files; nothing
  breaks if they are left out, but the PDF and MD buttons then lead nowhere.
- **`list.sqlite` must be served whole**, as a normal static file. The page asks for it with
  `cache: "no-cache"`, so a stale copy in a proxy or CDN shows yesterday's data until it expires;
  clear the cache after publishing a new database.

Anything static will do: S3 or another object store behind a CDN, Netlify, Cloudflare Pages, or a
plain Apache or nginx directory. For a leaner site than the repository root, publish only those
files — to a `gh-pages` branch, or into whatever directory the host serves.

## What not to publish

The whitelist in `.gitignore` already keeps these out, and they should stay out of any copy of the
site as well:

- `union-catalog-work/list-full.sqlite` — the working database, with the compilers' annotations and
  the withheld rows.
- the scanned PDFs and EPUBs of the source bibliographies, and the page transcriptions in
  `*/pages/`, which are copied from books still in copyright.
- the lookup caches (`ia_cache*.jsonl`, `gallica.jsonl`, `ob.jsonl`, `ndl.jsonl`, `lib.jsonl`,
  `extra.jsonl`) and the run logs.
- the Zotero RDF exports.

Nothing identifying belongs in the repository either — no account names, no email addresses, no
contact string in a User-Agent. The scripts all send a plain descriptive User-Agent, and the
`ia` command-line tool is used only where its access key goes to archive.org alone.
