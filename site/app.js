(() => {
"use strict";
const $ = id => document.getElementById(id);
const fold = s => (s || "").normalize("NFKD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
const esc = s => (s || "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
let ALL = [], VIEW = [], page = 0, sortKey = null, sortDir = 1, cur = -1, byMatch = false;
let allTypes = false;   // books only, unless a link or the search box says otherwise

// theme
const th = (() => { try { return localStorage.getItem("jb-theme"); } catch (e) { return null; } })();
if (th) document.documentElement.dataset.theme = th;
$("theme").onclick = () => {
  const now = document.documentElement.dataset.theme || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  const nxt = now === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = nxt;
  try { localStorage.setItem("jb-theme", nxt); } catch (e) {}
};

async function load() {
  const SQL = await initSqlJs({ locateFile: f => "vendor/" + f });
  const buf = await (await fetch("list.sqlite", { cache: "no-cache" })).arrayBuffer();
  const db = new SQL.Database(new Uint8Array(buf));
  const cols = db.exec("PRAGMA table_info(books)")[0].values.map(v => v[1]);
  const res = db.exec("SELECT * FROM books ORDER BY id")[0];
  const ix = Object.fromEntries(res.columns.map((c, i) => [c, i]));
  ALL = res.values.map(v => {
    const r = {}; for (const c of res.columns) r[c] = v[ix[c]];
    r.source = r.source || ""; r.edition = r.edition || ""; r.volume = r.volume || ""; r.type = r.type || "book";
    r.linkList = (r.links || "").split("\n").filter(Boolean);
    r.nlinks = r.linkList.length; r.otherEd = r.other.includes("IA other editions: ") || r.other.includes("Gallica, other editions: ");
    r.access = r.access || ""; r.language = r.language || ""; r.accList = (r.links_access || "").split("\n"); r.chkList = (r.links_checked || "").split("\n"); r.checked = r.chkList[0] === "1";
    r.fa = fold(r.author); r.ft = fold(r.title); r.fs = fold(r.source); r.fo = fold(r.other + " " + r.edition + " " + r.volume + " " + r.year + " " + r.source + " " + r.language);
    r.fall = r.fa + " \u0001 " + r.ft + " \u0001 " + r.fo;
    return r;
  });
  db.close();
  const srcs = [...new Set(ALL.flatMap(r => r.source.split(/\s*;\s*/)).filter(Boolean))].sort();
  const langCount = {};
  for (const r of ALL) langCount[r.language] = (langCount[r.language] || 0) + 1;
  countLanguages();
  for (const l of Object.keys(langCount).filter(Boolean).sort((a, b) => langCount[b] - langCount[a])) {
    const o = document.createElement("option"); o.value = l; o.textContent = l; $("lang").appendChild(o);
  }
  const withIA = ALL.filter(r => r.nlinks).length, nOpen = ALL.filter(r => r.access === "open").length, nBor = ALL.filter(r => r.access === "borrow").length;
  $("foot").innerHTML = "The full data are in <a href=\"list.sqlite\">list.sqlite</a> (table <code>books</code>).";
  const wantId = parseInt(new URLSearchParams(location.hash.slice(1)).get("id")); readHash(); apply(false); openFromHash(wantId);
}

function parseQuery(q) {
  const terms = []; const re = /(-?)(?:(author|title|other|source|type):)?(?:"([^"]+)"|(\S+))/gi; let m;
  while ((m = re.exec(q))) { const t = fold(m[3] || m[4]); if (t) terms.push({ neg: !!m[1], field: (m[2] || "").toLowerCase(), t }); }
  return terms;
}
const OCR_WARN = ["Russian", "Hungarian", "Finnish", "Turkish", "Czech"];
function warning(lang) {
  const w = $("warn");
  if (OCR_WARN.includes(lang)) {
    w.textContent = `The OCR quality for the ${lang} language texts found in bibliographies is likely to have been poor. ` +
      `This has not been checked by a ${lang} speaker yet.`;
    w.hidden = false;
  } else w.hidden = true;
}
// How many entries each language has, worked out once at load: the total, and the number answering each
// Show and Type pair ("ia|book" and so on). The Language menu shows "shown/total" for the Show and Type
// in force - French (364/985) - and no number at all once a search, a year range or a host narrows things
// further, since those counts are not pre-computed.
const LANGN = {};
function countLanguages() {
  for (const r of ALL) {
    if (!r.language) continue;
    const e = LANGN[r.language] || (LANGN[r.language] = { total: 0, n: {} });
    e.total++;
    const shows = ["all"];
    if (r.nlinks) { shows.push("ia"); if (r.access === "open" || r.access === "borrow") shows.push(r.access); }
    else shows.push("noia");
    for (const sh of shows) for (const ty of ["", r.type]) e.n[sh + "|" + ty] = (e.n[sh + "|" + ty] || 0) + 1;
  }
}
// Which types the list is showing: books unless the search box says otherwise ("type:article",
// "type:periodical", "type:all"). A negated term ("-type:chapter") takes that type out instead.
function typeRule(terms) {
  const want = terms.filter(t => t.field === "type" && !t.neg).map(t => t.t);
  const not = terms.filter(t => t.field === "type" && t.neg).map(t => t.t);
  const all = allTypes || want.some(w => w === "all" || w === "any");
  return { want: want.filter(w => w !== "all" && w !== "any"), not, all };
}
function typeOk(r, rule) {
  if (rule.not.some(w => r.type.startsWith(w))) return false;
  if (rule.want.length) return rule.want.some(w => r.type.startsWith(w));
  return rule.all || r.type === "book";
}

function labelLanguages(rule) {
  const narrowed = !!($("q").value.replace(/(^|\s)-?type:\S+/g, "").trim() || $("y1").value || $("y2").value || $("host").value);
  const sh = $("show").value;
  const ty = rule.all || rule.not.length || rule.want.length > 1 ? "" : (rule.want[0] || "book");
  for (const o of $("lang").options) {
    const e = LANGN[o.value];
    if (!o.value || !e) continue;
    if (narrowed) { o.textContent = o.value; continue; }
    const n = e.n[sh + "|" + ty] || 0, total = e.total.toLocaleString();
    o.textContent = sh === "all" && !ty ? `${o.value} (${total})` : `${o.value} (${n.toLocaleString()}/${total})`;
  }
}

// How well an entry answers what was typed. The whole phrase in the title counts for most, then how
// many of the words are in the title, how close together they sit, and whether they fall on word
// boundaries; the author counts for less and the rest of the record for little. This ordering is used
// only while the search box has something in it and no column has been clicked.
const WORDCH = /[a-z0-9]/;
const wholeWord = (s, i, w) =>
  (i === 0 || !WORDCH.test(s[i - 1])) && (i + w.length === s.length || !WORDCH.test(s[i + w.length]));
function relevance(r, words, phrase) {
  const t = r.ft, a = r.fa, o = r.fo;
  let s = 0;
  if (phrase) {
    if (t === phrase) s += 400;                            // the title is exactly what was typed
    else if (t.startsWith(phrase)) s += 230;               // ... or starts with it
    else if (phrase.includes(" ") && t.includes(phrase)) s += 170;
    if (phrase.includes(" ")) { if (a.includes(phrase)) s += 90; else if (o.includes(phrase)) s += 30; }
  }
  const spans = []; let inTitle = 0, elsewhere = 0;
  for (const w of words) {
    const i = t.indexOf(w);
    if (i >= 0) { inTitle++; spans.push([i, i + w.length]); s += wholeWord(t, i, w) ? 20 : 11; if (i === 0) s += 8; }
    else {
      const j = a.indexOf(w);
      if (j >= 0) { elsewhere++; s += wholeWord(a, j, w) ? 14 : 8; }
      else if (o.includes(w)) { elsewhere++; s += 4; }
    }
  }
  if (words.length) {
    if (inTitle === words.length) s += 70;                 // every word in the title
    else if (inTitle + elsewhere === words.length) s += 25;
    if (spans.length > 1) {                                // and the closer together, the better
      const lo = Math.min(...spans.map(x => x[0])), hi = Math.max(...spans.map(x => x[1]));
      const ideal = words.reduce((n, w) => n + w.length, 0) + words.length - 1;
      s += Math.max(0, 45 - Math.round((hi - lo - ideal) / 3));
    }
  }
  s -= Math.min(25, t.length / 30);     // between two titles that both match, the shorter one is the better answer
  if (r.nlinks) s += 2;                 // tie-break only: something that can be opened now
  return s;
}
const searchPhrase = q => fold(q).replace(/(^|\s)-\S+/g, " ").replace(/\b(author|title|other|source):/g, " ")
  .replace(/["']/g, " ").replace(/\s+/g, " ").trim();

// The Host menu would be wide enough to push the row around, so while it is closed the chosen library
// shows as its short code (NDL, IA, ...); opening the menu puts the full names back.
function hostMenu(open) {
  for (const o of $("host").options) {
    if (!o.dataset.short) continue;
    if (!o.dataset.full) o.dataset.full = o.textContent;
    o.textContent = (open || o.value !== $("host").value) ? o.dataset.full : o.dataset.short;
  }
}

// who holds a copy, by the host of its URL: the short code shown in the link column and used by the Host filter
const HOLDER = [[/archive\.org\//, "IA"], [/gallica\.bnf\.fr\//, "G"], [/dl\.ndl\.go\.jp\//, "NDL"],
                [/bne\.es\//, "BNE"], [/europeana\.eu\//, "EU"], [/nb\.no\//, "NB"], [/alvin-portal\.org\//, "Alvin"],
                [/onlinebooks\.library\.upenn\.edu\//, "OB"], [/hathitrust\.org\//, "H"],
                [/gutenberg\.org\//, "PG"]];
const holder = u => (HOLDER.find(([rx]) => rx.test(u || "")) || [null, ""])[1];

function apply(resetPage = true) {
  hostMenu(false);
  const all = parseQuery($("q").value), fld = $("field").value;
  const rule = typeRule(all), terms = all.filter(t => t.field !== "type");
  labelLanguages(rule);
  const y1 = parseInt($("y1").value) || null, y2 = parseInt($("y2").value) || null;
  const shw = $("show").value, hst = $("host").value, lng = $("lang").value, und = $("undated").checked;
  const key = f => f === "author" ? "fa" : f === "title" ? "ft" : f === "other" ? "fo" : f === "source" ? "fs" : "fall";
  VIEW = ALL.filter(r => {
    if (r.year_num == null) { if (!und || y1 || y2) return false; }
    else { if (y1 && r.year_num < y1) return false; if (y2 && r.year_num > y2) return false; }
    if (hst && !r.linkList.some(u => holder(u) === hst)) return false;
    if (!typeOk(r, rule)) return false;
    if (lng && r.language !== lng) return false;
    if (shw === "noia" ? r.nlinks : shw !== "all" && !r.nlinks) return false;
    if ((shw === "open" || shw === "borrow") && r.access !== shw) return false;   // from an older link
    for (const t of terms) { const hit = r[key(t.field || fld)].includes(t.t); if (hit === t.neg) return false; }
    return true;
  });
  const words = terms.filter(t => !t.neg && t.field !== "source" && t.field !== "other").map(t => t.t);
  byMatch = !sortKey && words.length > 0;
  if (byMatch) {
    const phrase = searchPhrase($("q").value);
    for (const r of VIEW) r.rel = relevance(r, words, phrase);
    VIEW.sort((x, y) => y.rel - x.rel || (x.year_num || 9999) - (y.year_num || 9999) || x.id - y.id);
  }
  if (sortKey) {
    const k = sortKey, d = sortDir;
    VIEW.sort((a, b) => {
      let x = a[k], y = b[k];
      if (k === "author") { x = a.fa || "\uffff"; y = b.fa || "\uffff"; } else if (k === "title") { x = a.ft; y = b.ft; }
      if (x == null) return 1; if (y == null) return -1;
      return (x < y ? -1 : x > y ? 1 : a.id - b.id) * d;
    });
  }
  if (resetPage) page = 0;
  warning(lng);
  render(terms); writeHash();
}
function hl(text, terms) {
  let out = text; if (!terms.length) return esc(out);
  // highlight on the folded string, mapping positions back (fold keeps length for NFKD-stripped chars only approximately, so match per word)
  for (const t of terms) { if (t.neg || t.t.length < 2) continue;
    const parts = text.split(/(\s+)/); out = parts.map(w => fold(w).includes(t.t) ? "\u0002" + w + "\u0003" : w).join(""); text = out; }
  return esc(out).replace(/\u0002+/g, "<mark>").replace(/\u0003+/g, "</mark>");
}
function render(terms) {
  terms = terms || parseQuery($("q").value);
  const pp = parseInt($("pp").value) || Math.max(1, VIEW.length), pages = Math.max(1, Math.ceil(VIEW.length / pp));
  page = Math.min(page, pages - 1);
  const slice = VIEW.slice(page * pp, (page + 1) * pp);
  // edition and volume used to have columns of their own, which left a gulf between the columns
  // whenever they were empty; they now follow the title, quietly
  // "4" alone says nothing: a bare number is given the word it belongs to, while anything that already
  // names itself ("2d ed.", "2 v.", "Bd. 3") is left as the source has it
  const named = (v, word) => {
    const t = String(v || "").trim();
    return !t ? "" : /[A-Za-zÀ-ÿ]/.test(t) ? t : `${word} ${t}`;
  };
  const edvol = r => {
    const bits = [named(r.edition, "ed."), named(r.volume, "vol.")].filter(Boolean);
    return bits.length ? `<span class="edvol">${esc(bits.join(", "))}</span>` : "";
  };
  const badge = a => a ? `<span class="badge ${a}" title="${{open: "can be read freely online", borrow: "can be borrowed on archive.org (free account)", restricted: "only for print-disabled readers", unknown: "access not checked"}[a] || ""}">${a === "restricted" ? "limited" : a}</span>` : "";
  const typeChip = r => r.type !== "book" ? ` <span class="chip">${esc(r.type)}</span>` : "";
  $("rows").innerHTML = slice.map((r, i) => `<tr data-i="${page * pp + i}" class="acc-${r.access}">
    <td class="au">${hl(r.author, terms) || '<span class="chip">no author</span>'}</td>
    <td class="title">${hl(r.title.length > 220 ? r.title.slice(0, 220) + "…" : r.title, terms)}${edvol(r)}${typeChip(r)}${coins(r)}</td>
    <td class="year">${esc(r.year)}</td>
    <td class="ia">${r.nlinks ? `<a class="pill ${r.access}" href="${esc(r.linkList[0])}" target="_blank" rel="noopener" title="${r.access === "borrow" ? "can be borrowed on archive.org (free account)" : r.access === "open" ? "can be read freely online" : "online copy"}${r.checked ? " – link checked by hand" : " – automatic title match, not verified"}">${holder(r.linkList[0]) ? holder(r.linkList[0]) + ": " : ""}${r.access === "borrow" ? "borrow" : r.access === "open" ? "read" : "view"} ↗${r.checked ? " ✓" : ""}</a>${r.nlinks > 1 ? ` <span class="chip">+${r.nlinks - 1}</span>` : ""}` : (r.links === null ? '<span class="chip">not searched</span>' : r.otherEd ? '<span class="chip" title="archive.org has this title only in an edition dated more than 3 years away - see the entry">other ed.</span>' : "")}</td></tr>`).join("");
  $("empty").hidden = VIEW.length > 0;
  if ($("dlg").open) for (const el of document.querySelectorAll("tbody span.Z3988")) el.className = "Z3988off";
  zoteroLook();                      // the COinS in these rows are new to the page
  $("count").textContent = `${VIEW.length.toLocaleString()} of ${ALL.length.toLocaleString()} entries` + (byMatch ? " · best match first (click a column to sort instead)" : "");
  $("pageinfo").textContent = `Page ${page + 1} / ${pages}`; document.querySelector(".pager").hidden = pages === 1;
  $("prev").disabled = page === 0; $("next").disabled = page >= pages - 1;
  document.querySelectorAll("th").forEach(th => th.querySelector(".arrow").textContent = th.dataset.k === sortKey ? (sortDir > 0 ? "▲" : "▼") : "");
}
function citation(r) { return [r.author, r.title + (/[.?!]$/.test(r.title) ? "" : "."), r.edition, (r.other.match(/Imprint: ([^|]+)/) || [,""])[1].trim(), r.year].filter(Boolean).join(" ").replace(/\s+/g, " ") + "."; }
function show(i) {
  if (i < 0 || i >= VIEW.length) return; cur = i; const r = VIEW[i];
  $("dtitle").innerHTML = esc(r.title) + coins(r);   // the open entry carries its COinS too
  const other = r.other.split(" | ").map(p => { const j = p.indexOf(": "); return j > 0 && j < 22 ? [p.slice(0, j), p.slice(j + 2)] : ["Info", p]; });
  const bdg = a => a ? `<span class="badge ${a}">${a === "restricted" ? "limited" : a}</span>` : "";
  const links = r.nlinks ? r.linkList.map((u, j) => `<a href="${esc(u)}" target="_blank" rel="noopener">${esc(u.replace("https://archive.org/details/", "").replace("https://dl.ndl.go.jp/pid/", "National Diet Library, pid ").replace("https://gallica.bnf.fr/", "Gallica, "))}</a>${bdg(r.accList[j])}${r.chkList[j] === "1" ? ' <span class="chip" title="this link was checked by hand">✓ checked</span>' : ""}`).join("<br>")
    : (r.links === null ? "not searched (undated entry)" : "no copy found online");
  $("ddl").innerHTML = [["Author", esc(r.author) || "—"], ["Year", esc(r.year)], ["Edition", esc(r.edition)], ["Volume", esc(r.volume)],
    ...other.map(([k, v]) => [esc(k), esc(v).replace(/https:\/\/archive\.org\/details\/([^\s;|<]+)/g, '<a href="https://archive.org/details/$1" target="_blank" rel="noopener">$1</a>').replace(/https:\/\/gallica\.bnf\.fr\/([^\s;|<]+)/g, '<a href="https://gallica.bnf.fr/$1" target="_blank" rel="noopener">Gallica, $1</a>')]), ["Type", esc(r.type)], ["Language", esc(r.language) || "not determined"], ["Source", esc(r.source)], ["Online copy", links]]
    .filter(([, v]) => v).map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("");
  $("dsearch").href = "https://archive.org/search?query=" + encodeURIComponent(`title:(${r.title.split(/[.;:]/)[0]})` + (r.author ? ` AND creator:(${r.author.split(",")[0]})` : ""));
  $("dprev").disabled = i === 0; $("dnext").disabled = i === VIEW.length - 1;
  if (!$("dlg").open) $("dlg").showModal();
  coinsMode(true);                   // offer this entry alone while it is open
  history.replaceState(null, "", location.pathname + location.search + hashString(r.id));
}
function hashString(id) {
  const p = new URLSearchParams();
  const put = (k, v, d) => { if (v !== d && v !== "" && v != null) p.set(k, v); };
  put("q", $("q").value, ""); put("f", $("field").value, "all"); put("y1", $("y1").value, ""); put("y2", $("y2").value, "");
  put("host", $("host").value, ""); put("lang", $("lang").value, ""); put("show", $("show").value, "ia"); put("pp", $("pp").value, "1000");
  put("und", $("undated").checked ? "" : 0, ""); put("s", sortKey ? (sortDir < 0 ? "-" : "") + sortKey : "", ""); put("p", page || "", "");
  if (id) p.set("id", id);
  const s = p.toString(); return s ? "#" + s : "";
}
function writeHash() { history.replaceState(null, "", location.pathname + location.search + hashString()); }
// The menu offers Online or All; a link from before may ask for open, borrow or no-copy, which still
// works - the value is added to the menu so that it can be selected and written back.
function setShow(v) {
  if (!v) v = "ia";
  if (![...$("show").options].some(o => o.value === v)) {
    const o = document.createElement("option");
    o.value = v; o.textContent = { open: "Read freely", borrow: "Borrow only", noia: "No online copy" }[v] || v;
    $("show").appendChild(o);
  }
  $("show").value = v;
}

function readHash() {
  const p = new URLSearchParams(location.hash.slice(1));
  $("q").value = p.get("q") || ""; $("field").value = p.get("f") || "all"; $("y1").value = p.get("y1") || ""; $("y2").value = p.get("y2") || "";
  if (p.get("host")) $("host").value = p.get("host"); allTypes = p.get("type") === "all"; if (p.get("lang")) $("lang").value = p.get("lang"); setShow(p.get("show") || (p.get("noia") ? "noia" : "ia")); if (p.get("pp")) $("pp").value = p.get("pp");
  $("undated").checked = p.get("und") !== "0"; page = parseInt(p.get("p")) || 0;
  const s = p.get("s"); if (s) { sortDir = s[0] === "-" ? -1 : 1; sortKey = s.replace(/^-/, ""); }
}
function openFromHash(id) {
  if (!id) return;
  let i = VIEW.findIndex(r => r.id === id);
  if (i < 0 && ALL.some(r => r.id === id)) { $("show").value = "all"; allTypes = true; apply(false); i = VIEW.findIndex(r => r.id === id); }  // a linked entry outside the default filters
  if (i >= 0) { page = Math.floor(i / (parseInt($("pp").value) || Math.max(1, VIEW.length))); render(); show(i); }
}

// three quarters of a second after the last keystroke, so that typing a phrase does not re-filter on every letter;
// Enter searches at once
let tmr; const debounced = () => { clearTimeout(tmr); tmr = setTimeout(() => apply(), 750); };
$("q").addEventListener("input", debounced);
$("q").addEventListener("keydown", e => { if (e.key === "Enter") { clearTimeout(tmr); apply(); } });
for (const id of ["field", "y1", "y2", "host", "lang", "undated", "pp", "show"]) $(id).addEventListener("input", () => apply());
$("host").addEventListener("focus", () => hostMenu(true));
$("host").addEventListener("blur", () => hostMenu(false));
$("host").addEventListener("change", () => hostMenu(false));
function resetAll(focus) {
  $("q").value = ""; $("field").value = "all"; $("y1").value = $("y2").value = ""; $("host").value = "";
  allTypes = false; $("lang").value = ""; $("show").value = "ia"; $("pp").value = "1000";
  $("undated").checked = true; sortKey = null; sortDir = 1; page = 0; apply();
  if (focus) $("q").focus(); else scrollTo({ top: 0 });
}
$("reset").onclick = () => resetAll(true);
$("home").onclick = () => resetAll(false);   // the heading is the way back to the opening view
$("home").onkeydown = e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); resetAll(false); } };
$("prev").onclick = () => { page--; render(); writeHash(); scrollTo({ top: 0 }); };
$("next").onclick = () => { page++; render(); writeHash(); scrollTo({ top: 0 }); };
document.querySelectorAll("th").forEach(th => th.onclick = () => { const k = th.dataset.k; if (sortKey === k) { if (sortDir === 1) sortDir = -1; else { sortKey = null; sortDir = 1; } } else { sortKey = k; sortDir = 1; } apply(); });
$("rows").addEventListener("click", e => { if (e.target.closest("a")) return; const tr = e.target.closest("tr"); if (tr) show(parseInt(tr.dataset.i)); });
$("dclose").onclick = () => $("dlg").close();
$("dlg").addEventListener("close", () => coinsMode(false));   // the whole list again
$("dlg").addEventListener("close", writeHash);
$("dlg").addEventListener("click", e => { if (e.target === $("dlg")) $("dlg").close(); });
$("dprev").onclick = () => show(cur - 1); $("dnext").onclick = () => show(cur + 1);
const copy = (t, b) => navigator.clipboard.writeText(t).then(() => { const o = b.textContent; b.textContent = "Copied ✓"; setTimeout(() => b.textContent = o, 1200); });
$("dcopy").onclick = e => copy(citation(VIEW[cur]), e.target);
$("dlink").onclick = e => copy(location.origin + location.pathname + "#id=" + VIEW[cur].id, e.target);
document.addEventListener("keydown", e => { if ($("dlg").open) { if (e.key === "ArrowLeft") show(cur - 1); if (e.key === "ArrowRight") show(cur + 1); } else if (e.key === "/" && document.activeElement !== $("q")) { e.preventDefault(); $("q").focus(); } });
$("csv").onclick = () => {
  const cols = ["id", "author", "title", "year", "edition", "volume", "type", "language", "access", "links", "links_access", "links_checked", "other", "source"];
  const q = v => '"' + String(v == null ? "" : v).replace(/"/g, '""').replace(/\n/g, " ") + '"';
  const blob = new Blob(["\ufeff" + cols.join(",") + "\n" + VIEW.map(r => cols.map(c => q(r[c])).join(",")).join("\n")], { type: "text/csv" });
  const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = "japan-bib-results.csv"; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 2000);
};
// COinS (the Z3988 span) so that Zotero's connector can take an entry straight off the page: one in
// every row of the table and one in the open entry. Empty by design - everything is in the title.
// While an entry is open, the page should offer that one record rather than the whole list: Zotero
// prefers COinS over other metadata and takes every Z3988 span it finds, so the spans in the rows are
// set aside (their class changed) until the entry is closed again.
function coinsMode(single) {
  const off = single ? "Z3988" : "Z3988off", on = single ? "Z3988off" : "Z3988";
  for (const el of document.querySelectorAll("tbody span." + off)) el.className = on;
  zoteroLook();
}

function coins(r) {
  const { address, publisher, container } = imprintOf(r);
  const article = r.type === "article" || r.type === "chapter";
  const f = [["ctx_ver", "Z39.88-2004"],
             ["rft_val_fmt", article ? "info:ofi/fmt:kev:mtx:journal" : "info:ofi/fmt:kev:mtx:book"],
             ["rft.genre", r.type === "chapter" ? "bookitem" : r.type === "article" ? "article" : "book"],
             [article ? "rft.atitle" : "rft.btitle", r.title],
             ["rft.title", article ? container : r.title],
             ["rft.jtitle", r.type === "article" ? container : ""],
             ["rft.au", r.author], ["rft.date", r.year], ["rft.pub", publisher], ["rft.place", address],
             ["rft.edition", r.edition], ["rft.volume", r.volume], ["rft.language", r.language],
             ["rft_id", r.linkList[0] || ""]];
  const q = f.filter(([, v]) => v).map(([k, v]) => k + "=" + encodeURIComponent(v)).join("&");
  return `<span class="Z3988" title="${esc(q)}"></span>`;
}

// BibTeX for whatever the filters have left, so a result list can go straight into a reference manager.
// The fields are the ones the entry actually has; an imprint is split into publisher and address where
// the source wrote it as "Imprint: place, publisher".
const BIBTYPE = { article: "article", chapter: "incollection", periodical: "periodical", book: "book" };
const bibEsc = s => String(s == null ? "" : s).replace(/[{}]/g, "").replace(/\\/g, "").replace(/\s+/g, " ").trim();
function bibKey(r, used) {
  const sur = (r.author || "").split(",")[0].split(/\s+/).filter(Boolean).pop() || "anon";
  const word = (r.title || "").split(/\s+/).find(w => w.length > 3 && /^[A-Za-z]/.test(w)) || "";
  let k = (fold(sur) + (r.year_num || "nd") + fold(word)).replace(/[^a-z0-9]/g, "");
  if (used.has(k)) { let n = 2; while (used.has(k + n)) n++; k += n; }
  used.add(k);
  return k;
}
// "Tokyo, Maruzen" is place then publisher, but "Washington, D. C." and "Cambridge, Mass." are all place
const STATE = /^(?:[A-Z]\.?\s?[A-Z]\.?|D\.?\s?C\.?|Mass|Conn|Calif?|Ill|Pa|Va|Md|Mich|Minn|Wis|Ky|Tenn|Ore|Wash|Ont|Que|N\.?\s?[JYCHMD]|Vt|Ind|Iowa|Kan|Mo|Neb|Ohio|Okla|Tex|Utah|Colo)\.?$/i;
function imprintOf(r) {
  const other = r.other || "";
  const imprint = (other.match(/Imprint: ([^|]+)/) || [, ""])[1].trim();
  let bits = imprint.split(",").map(x => x.trim()).filter(Boolean), address = "";
  if (bits.length > 1 && STATE.test(bits[1])) { address = bits[0] + ", " + bits[1]; bits = bits.slice(2); }
  else if (bits.length > 1) { address = bits[0]; bits = bits.slice(1); }
  else if (bits.length === 1 && STATE.test(bits[0])) { address = bits[0]; bits = []; }   // "N. Y." alone is a place
  return { address, publisher: address ? bits.join(", ") : (bits[0] || ""),
           container: (other.match(/In: ([^|]+)/) || [, ""])[1].trim() };
}

function bibEntry(r, used) {
  const { address, publisher, container } = imprintOf(r);
  const f = [["author", r.author], ["title", r.title], ["year", r.year], ["publisher", publisher],
             ["address", address], ["edition", r.edition], ["volume", r.volume], ["language", r.language],
             [BIBTYPE[r.type] === "article" ? "journal" : "booktitle", container],
             ["url", r.linkList[0] || ""], ["note", r.source ? "Listed in " + r.source : ""]];
  const lines = f.filter(([, v]) => bibEsc(v)).map(([k, v]) => `  ${k} = {${bibEsc(v)}}`);
  return `@${BIBTYPE[r.type] || "book"}{${bibKey(r, used)},\n${lines.join(",\n")}\n}`;
}
$("bib").onclick = () => {
  const used = new Set();
  const text = "% " + VIEW.length + " entries from " + location.origin + location.pathname +
    " (" + new Date().toISOString().slice(0, 10) + ")\n\n" +
    VIEW.map(r => bibEntry(r, used)).join("\n\n") + "\n";
  const blob = new Blob([text], { type: "application/x-bibtex" });
  const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = "japan-bib-results.bib"; a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
};
// The rows - and the COinS spans in them - only exist once the database has loaded and the filters have
// run, which is after the connector has looked at the page. This is the event Zotero documents for that
// case: it makes the connector run detection again. Fired once at first paint, and at most every few
// seconds afterwards, since each one makes the connector re-scan the whole page.
let zoteroAt = 0, zoteroTmr;
function zoteroLook() {
  clearTimeout(zoteroTmr);
  const wait = Math.max(0, 3000 - (Date.now() - zoteroAt));
  zoteroTmr = setTimeout(() => {
    zoteroAt = Date.now();
    document.dispatchEvent(new Event("ZoteroItemUpdated", { bubbles: true, cancelable: true }));
  }, wait);
}

load().catch(err => { $("count").textContent = "Could not load the database: " + err; });
})();
