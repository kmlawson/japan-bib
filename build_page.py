#!/usr/bin/env python3
"""Build index.html: the Primary Sources page, with the bibliography search on it.

    build_page.py [--md page/modern-japan.md] [--out index.html]
    build_page.py --from "/path/to/modern-japan.md"     copy that file into page/ first, then build

The page is made of four things, none of which this script edits by hand:

    page/modern-japan.md   the list itself. Edit it and run this script again.
    site/page.css          the look of the page around the search (serif, same white/blue/grey palette)
    site/app.css/.html/.js the search, exactly as it is - cut out of the old standalone page
    vendor/sql-wasm.*      the SQLite engine the search runs on

Each `# heading` in the markdown becomes a section of the page with a button of its own at the top,
in the order they are written; a last button leads to the search. Nothing but the buttons and the
search is shown when the page opens: pressing a button reveals that section, pressing it again - or
clicking the section's own heading - hides it. The first `# heading` is the page title; the list of
sections underneath it is left out, since the buttons say the same thing, and the "See also" links
after it are set as one line under the title.
"""
import argparse, html, os, re, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
MD = os.path.join(HERE, "page", "modern-japan.md")
OUT = os.path.join(HERE, "index.html")
SITE = os.path.join(HERE, "site")
SEARCH_LABEL = "Digitized Books"
SEARCH_BLURB = ("A searchable database of Western-language books on Japan published 1850-1955, drawn from "
                "printed bibliographies, library catalogues and my own reading, with links to copies online.")


# ---------------------------------------------------------------- markdown
LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
BARE = re.compile(r"(?<![\"'=(>])\bhttps?://[^\s<>)\]]+")
BOLD = re.compile(r"\*\*([^*]+)\*\*")
ITAL = re.compile(r"(?<!\*)\*([^*]+)\*(?!\*)")
CODE = re.compile(r"`([^`]+)`")


def inline(text):
    """One line of markdown to HTML: links (plain or bare), bold, italic, code."""
    out, last = [], 0
    for m in LINK.finditer(text):
        out.append(esc_runs(text[last:m.start()]))
        out.append(f'<a href="{html.escape(m.group(2), quote=True)}" target="_blank" rel="noopener">'
                   f'{esc_runs(m.group(1))}</a>')
        last = m.end()
    out.append(esc_runs(text[last:]))
    return "".join(out)


def esc_runs(text):
    """Escape, then mark up what is left: bare URLs become links, *word* italic, **word** bold."""
    t = html.escape(text)
    t = BARE.sub(lambda m: f'<a href="{m.group(0)}" target="_blank" rel="noopener">{m.group(0)}</a>', t)
    t = CODE.sub(r"<code>\1</code>", t)
    t = BOLD.sub(r"<strong>\1</strong>", t)
    t = ITAL.sub(r"<em>\1</em>", t)
    return t


PILL = re.compile(r"^(.*?)(\s+[-–—]\s+.*)?$", re.S)


def pill_item(text):
    """A nested item under a heading that ends in a colon: the link becomes a small bubble, and
    whatever the line says after it stays beside the bubble as a quiet note."""
    m = LINK.match(text.strip())
    if not m:
        return "<li>" + inline(text) + "</li>"
    rest = text.strip()[m.end():].lstrip(" -–—\u2013")
    note = f'<span class="pill-note">{inline(rest)}</span>' if rest.strip() else ""
    return (f'<li><a class="pill-link" href="{html.escape(m.group(2), quote=True)}" target="_blank" '
            f'rel="noopener">{esc_runs(m.group(1))}</a>{note}</li>')


def render(lines):
    """A section's body: bullet lists (one level of nesting), sub-headings and paragraphs.

    A bullet that ends in a colon and is followed by indented bullets is taken as a heading for them:
    those become a row of small bubbles (ul.pills) rather than an ordinary list."""
    out, stack, para = [], 0, []
    pills = False

    def close_para():
        if para:
            out.append("<p>" + inline(" ".join(para).strip()) + "</p>")
            para.clear()

    def close_lists(to=0):
        nonlocal stack
        while stack > to:
            out.append("</ul>")
            stack -= 1
            if stack:                      # the nested list lives inside its parent item
                out.append("</li>")

    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            close_para()
            continue
        m = re.match(r"^(\s*)[-*+]\s+(.*)$", line)
        if m:
            close_para()
            depth = 1 + (len(m.group(1).expandtabs(4)) >= 2)
            text = m.group(2)
            if depth == 1:
                pills = text.rstrip().endswith(":")
            while stack < depth:
                if stack and out and out[-1].endswith("</li>"):
                    out[-1] = out[-1][:-len("</li>")]   # reopen the item this list belongs to
                out.append('<ul class="pills">' if (depth == 2 and pills) else "<ul>")
                stack += 1
            close_lists(depth)
            out.append(pill_item(text) if (depth == 2 and pills) else "<li>" + inline(text) + "</li>")
            continue
        m = re.match(r"^(#{2,6})\s+(.*)$", line)
        if m:
            close_para(); close_lists()
            out.append(f"<h3>{inline(m.group(2))}</h3>")
            continue
        close_lists()
        para.append(line.strip())
    close_para(); close_lists()
    return "\n".join(out)


def sections(md):
    """[(heading, [lines]), ...] - the first one is the page title and whatever follows it."""
    out, head, body = [], None, []
    for line in md.splitlines():
        m = re.match(r"^#\s+(.*)$", line)
        if m:
            if head is not None or body:
                out.append((head, body))
            head, body = m.group(1).strip(), []
        else:
            body.append(line)
    if head is not None or body:
        out.append((head, body))
    return out


def slug(s):
    return "s-" + re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def also_line(lines):
    """The "See also:" list under the title, as one line of links for the head of the page."""
    label, links = "", []
    for line in lines:
        t = line.strip()
        if not t:
            continue
        m = re.match(r"^[-*+]\s+(.*)$", t)
        if m:
            links.append(inline(m.group(1)))
        elif not label:
            label = t.rstrip(":")
    if not links:
        return ""
    return (f'<p class="also"><span class="also-label">{html.escape(label) or "See also"}:</span> '
            + ' <span class="sep">·</span> '.join(links) + "</p>")


def split_intro(lines):
    """The title section: its leading bullet list repeats the buttons, so it is dropped; the rest
    (the "See also" links) is kept for the foot of the page."""
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    while i < len(lines) and re.match(r"^\s*[-*+]\s+", lines[i]):
        i += 1
    return lines[i:]


# ----------------------------------------------------------------- the page
def build(md_path, out_path):
    md = open(md_path, encoding="utf-8").read()
    secs = sections(md)
    title = secs[0][0] or "Primary Sources"
    rest = split_intro(secs[0][1])
    body = secs[1:]

    part = lambda name: open(os.path.join(SITE, name), encoding="utf-8").read()
    app_html = part("app.html")
    # the page has one h1 of its own, so the search keeps its heading as an h2
    app_html = app_html.replace('<h1 id="home"', '<h2 id="home"').replace("</h1>", "</h2>", 1)
    app_html = app_html.replace('<script src="vendor/sql-wasm.js"></script>', "").strip()
    app_html = app_html.replace(" autofocus", "")   # the page should open at the top, not at the search box

    buttons = ['<button type="button" class="jump openall" data-target="all" aria-expanded="false">Open All</button>']
    buttons += [f'<button type="button" class="jump" data-target="{slug(h)}" aria-expanded="false">{html.escape(h)}</button>'
                for h, _ in body]
    buttons.append(f'<button type="button" class="jump search" data-target="search">{SEARCH_LABEL}</button>')

    parts = [f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(SEARCH_BLURB)}">
<style>
{part("app.css").strip()}
{part("page.css").strip()}
</style>
</head>
<body class="page">
<div class="wrap">
  <header class="site">
    <h1>{html.escape(title)}</h1>
    <p class="lede">A list of primary sources for the study of modern Japanese history, with a searchable
      database of digitized books. Choose a heading to open it.</p>
    {also_line(rest)}
  </header>
  <nav class="jumps">
    <div class="sections">
      {"\n      ".join(buttons[:-1])}
    </div>
    {buttons[-1]}
  </nav>''']

    for h, lines in body:
        parts.append(f'''  <section class="md" id="{slug(h)}" hidden>
    <h2 tabindex="0" role="button" title="Hide this section">{html.escape(h)}</h2>
    <div class="body">
{render(lines)}
    </div>
  </section>''')

    parts.append(f'''  <section id="search">
{app_html}
  </section>''')

    parts.append('''  <footer class="credit">
    <p>The code and design for the website was created with Anthropic Claude Opus 5.1 with Konrad M. Lawson
      at the prompt. Opus was also used in extracting candidates for bibliographic entries from some of the
      sources.</p>
  </footer>
</div>
<script src="vendor/sql-wasm.js"></script>
<script>
// Each button opens or closes its section; a section's own heading closes it. The search is always
// on the page, so its button only scrolls to it.
const openAll = document.querySelector("nav.jumps button.openall");
function setOpen(sec, open) {
  sec.hidden = !open;
  const b = document.querySelector(`nav.jumps button[data-target="${sec.id}"]`);
  if (b) b.setAttribute("aria-expanded", open ? "true" : "false");
}
function syncOpenAll() {
  const secs = [...document.querySelectorAll("section.md")];
  const all = secs.every(s => !s.hidden);
  openAll.textContent = all ? "Close All" : "Open All";
  openAll.setAttribute("aria-expanded", all ? "true" : "false");
}
openAll.addEventListener("click", () => {
  const secs = [...document.querySelectorAll("section.md")];
  const open = secs.some(s => s.hidden);
  for (const s of secs) setOpen(s, open);
  syncOpenAll();
  if (open) secs[0].scrollIntoView({ behavior: "smooth", block: "start" });
});
for (const b of document.querySelectorAll("nav.jumps button:not(.openall)")) {
  b.addEventListener("click", () => {
    const sec = document.getElementById(b.dataset.target);
    if (!sec) return;
    if (b.dataset.target === "search") { sec.scrollIntoView({ behavior: "smooth", block: "start" }); return; }
    const open = sec.hidden;
    setOpen(sec, open);
    syncOpenAll();
    if (open) sec.scrollIntoView({ behavior: "smooth", block: "start" });
  });
}
for (const h of document.querySelectorAll("section.md > h2")) {
  const close = () => {
    const sec = h.parentElement;
    setOpen(sec, false);
    syncOpenAll();
    const b = document.querySelector(`nav.jumps button[data-target="${sec.id}"]`);
    if (b) b.scrollIntoView({ behavior: "smooth", block: "center" });
  };
  h.addEventListener("click", close);
  h.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); close(); } });
}
</script>
<script>
''' + part("app.js").strip() + '''
</script>
</body>
</html>
''')
    open(out_path, "w", encoding="utf-8").write("\n".join(parts))
    return title, [h for h, _ in body]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--md", default=MD)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--from", dest="src", help="copy this markdown into page/ before building")
    args = ap.parse_args()
    if args.src:
        os.makedirs(os.path.dirname(MD), exist_ok=True)
        shutil.copyfile(args.src, MD)
        print("copied", args.src, "->", os.path.relpath(MD, HERE))
    title, heads = build(args.md, args.out)
    print(f"{os.path.relpath(args.out, HERE)}: {title!r} with {len(heads)} sections + the search")
    for h in heads:
        print("   ", h)
