# Dower & George (1995) — transcription notes

Source: John W. Dower with Timothy S. George, *Japanese History and Culture from Ancient to Modern
Times: Seven Basic Bibliographies*, second edition, revised and updated (Princeton: Markus Wiener
Publishers, 1995). The PDF in the parent folder is the archive.org scan
[`japanesehistoryc0000dowe`](https://archive.org/details/japanesehistoryc0000dowe) and covers the
title page plus printed pages 253–414 (PDF page = printed page − 251).

Every page was read by eye from the page images (190 dpi renders, higher-resolution crops where a
glyph was doubtful). The PDF's own text layer is machine OCR and was not used, here or by the
sub-agents who transcribed parts of the range; nothing was guessed. One JSONL file per page in
`pages/`, the first line of each being a summary of what is on that page.

    python3 validate3.py            # checks every page file; 162/162, 1,706 entries seen, 563 in range

Only works **first published 1850–1960** were written out (judged by the first year printed in the
entry); the database itself shows nothing later than 1950.

## Pages that could not be read

Six pages of this scan are failed exposures — they render as near-uniform grey, and the glyphs are
not in the file at all (checked at 190, 250 and 300 dpi, through a second renderer, and in the
page's own image layers). They are recorded as unreadable, with no entries:

| printed page | PDF page | section it falls in |
|---|---|---|
| 332 | 81 | JAPAN & THE CRISIS IN ASIA, 1931-1945 |
| 344 | 93 | JAPAN & THE CRISIS IN ASIA, 1931-1945 |
| 346 | 95 | JAPAN & THE CRISIS IN ASIA, 1931-1945 |
| 348 | 97 | JAPAN & THE CRISIS IN ASIA, 1931-1945 |
| 350 | 99 | JAPAN & THE CRISIS IN ASIA, 1931-1945 |
| 380 | 129 | OCCUPIED JAPAN & THE COLD WAR IN ASIA / GENERAL SOURCES |

Pages with no entries for another reason (part titles, contents pages, blank versos, a page wholly
taken up by the continuation of one entry) are recorded the same way, with the reason in the note.

archive.org has two scans of the **first edition** (1986: `japanesehistoryc0000dowe_u7x5`,
`japanesehistoryc0000dowe_a2h9`), which would cover most of what those six pages hold. Both are
lending-only, so filling the gaps would mean borrowing one of them on the account holder's own
archive.org account — not done.

## From the page files to the database

`dower_merge.py` puts the entries into the form the rest of the database uses (names inverted,
titles out of capitals), finds the ones already present (same surname, matching title proper, years
within three — the test used for Borton and Henshall) and hands the rest to `build_db.py` as new
rows. It runs **after every other source**, so the ids of the existing rows do not move: the
language fixes and the Gallica and Online Books results are keyed to them.

`ia_lookup3.py` looks the new books up on archive.org (cache `ia_cache3.jsonl`, resumable).
