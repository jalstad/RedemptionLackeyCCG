# Redemption LackeyCCG Plugin Update Tool — Design Spec

**Date:** 2026-05-30
**Branch:** `card-set-ingestion-tooling`
**Status:** Approved design (pre-implementation)

## 1. Overview & Goals

Releasing a Redemption LackeyCCG plugin update today is a manual, error-prone
ritual: a maintainer resizes new card images, pastes new rows into a 5,400+ line
tab-separated `carddata.txt`, hand-recomputes a custom byte-sum checksum for every
changed file and rewrites `updatelist.txt`, and hand-bumps two version files. A
single stray byte (a trailing newline, a CRLF, an Excel "smart quote", a wrong
checksum) silently breaks the plugin for every downstream player, with no error
that points at the cause. Recent history shows this biting maintainers (e.g.
`30124e1 "Fixed Babylon Image File Name"`, `0a93942 "Shattered & Scorched Fix"`).

This tool is a **local web app** that walks a non-technical helper through one
release:

1. Paste tab-separated card rows (copied from Excel) → parse, validate, **merge**
   into `RedemptionQuick/sets/carddata.txt`.
2. Recompute checksums and rewrite `RedemptionQuick/updatelist.txt`.
3. Bump `RedemptionQuick/version.txt` and `RedemptionQuick/plugininfo.txt`.
4. Validate images (missing / orphaned) against
   `RedemptionQuick/sets/setimages/general/`.

The tool **writes files only**. It **never runs git**. After it finishes, the
maintainer reviews the diff in their normal git tooling and commits/pushes
manually — that manual review is the final human checkpoint and the safety net.

**Primary design driver: longevity.** The tool must run unchanged for years, on a
future machine, used by whoever maintains the plugin next. This dominates every
technical choice below: no build step, no package manager, no framework to
upgrade, no dependency tree that rots.

### Non-goals

- No git operations of any kind (status/add/commit/push).
- No image resizing or generation (a separate, in-progress resize script handles
  that). The tool only *validates* image presence.
- No authoring of `packdefinitions.xml`, `.dek` deck files, `formats.txt`, or
  `setlist.txt` content. The tool only *re-checksums* the manifest files that
  already exist if they changed on disk.
- No network access, no hosting, no authentication.

## 2. Tech Stack — Python 3 standard library only

**Decision: Python 3 stdlib backend (`http.server`) + a single static
`index.html` (vanilla JS/CSS). Zero third-party dependencies. No build step.**

Why Python, decided honestly against Node:

- **The checksum is canonical Python and byte-exactness is the entire point.**
  The reference algorithm relies on `int.from_bytes(b, signed=True)` per byte and
  `math.fmod` modulus semantics, plus a subtle `fp.peek()` priming and an
  `else: value -= 1` EOF branch (see §5 — that branch is **load-bearing**, not
  dead code). Reusing the function verbatim in a Python server removes an entire
  category of re-port risk. (During design, one independent draft "cleaned up"
  the algorithm in a reimplementation and produced values off by one — proof the
  quirk matters.)
- **The repo already ships Python helper scripts** (`scripts/convert.py`,
  `clean_dashes.py`, `get_references.py`, …). Maintainers already have Python.
- **Zero dependency rot.** `http.server` + `json` + `pathlib` are stdlib and
  stable across the Python 3 lifetime. No `pip install`, no lockfile, no
  `node_modules` to fail in 2031. A bundler/transpiler would itself be the rot.

**Rejected:** Flask (adds a dependency + virtualenv for ~5 routes); Node
(re-port risk for the checksum + `node_modules` maintenance burden).

### Concrete stack

- **Backend:** Python 3.8+ stdlib (`http.server.BaseHTTPRequestHandler`, `json`,
  `os`, `math`, `pathlib`, `tempfile`). Binds to `127.0.0.1` only.
- **Frontend:** one `index.html` with inline vanilla JS + CSS. No framework, no
  CDN (works offline). `fetch()` → local JSON API.
- **Launcher:** double-click `Start Update Tool.command` (macOS) /
  `Start Update Tool.bat` (Windows) that run `python3 tools/updater/server.py`
  and open `http://127.0.0.1:<port>`. A short maintainer README is the only doc;
  the launchers show a friendly "install Python 3 from python.org" message if no
  interpreter is found.

## 3. Architecture

Small, single-purpose, independently testable modules under a new `tools/updater/`
directory at the repo root. All file I/O is anchored to the repo root, resolved
from the script's own location (never the CWD).

```
tools/updater/
  server.py            # http.server glue: serves index.html + JSON API. No business logic.
  index.html           # entire GUI (HTML + CSS + vanilla JS, no deps)
  paths.py             # the ONE place defining repo paths + the gh-pages base URL; path-traversal guard
  checksum.py          # canonical byte-sum checksum, VERBATIM from the reference (pure)
  carddata.py          # parse paste, validate, merge, render carddata.txt (pure)
  updatelist.py        # rebuild updatelist.txt manifest (preserve header + trailer + order)
  version_bump.py      # rewrite version.txt + plugininfo.txt
  images.py            # missing / orphaned image report (pure given two filename lists)
  safe_write.py        # atomic write: temp file + os.replace
  tests/               # stdlib unittest; runnable via `python3 -m unittest`
  README-for-maintainers.txt
  Start Update Tool.command   # macOS double-click launcher
  Start Update Tool.bat       # Windows double-click launcher
```

### Data flow (paste → preview → write → manual review)

```
  Excel ──copy──► [ Paste box in browser ]
                      │ POST /api/preview {pasted_text, version fields}
                      ▼
   PARSE → VALIDATE → MERGE (in memory) → build diff/report      ← writes NOTHING
                      │  errors/warnings/diff returned as JSON
                      ▼
   UI shows: rows ADD/UPDATE, image report, new checksums, version diff
                      │  maintainer fixes paste/fields, re-previews freely
                      │ POST /api/apply {same payload}
                      ▼
   re-validate (authoritative) → compute all new bytes in memory →
   write each file atomically (temp + os.replace) → re-read & re-checksum to verify
                      ▼
   "Done. Review `git diff`, then commit + push yourself."  (tool never touches git)
```

**Key principle:** `/api/preview` is pure and side-effect-free (clickable
endlessly). Only `/api/apply` writes, and it re-runs full validation server-side
(defense in depth) and refuses if any hard error exists.

## 4. carddata.txt Merge Logic

### Verified file facts

- **Encoding:** UTF-8, **no BOM**.
- **Line endings:** **LF only** (`\n`). No CRLF, no lone CR.
- **Trailing newline:** **NONE** — the file ends with the last field of the last
  row. Must be preserved; adding a trailing newline changes the checksum.
- **Structure:** header row + data rows, tab-separated, **exactly 16 columns**
  (15 tabs/row). Empty fields (adjacent tabs) are normal and legal.

**Columns (exact header order):**

| # | Column | # | Column |
|---|--------|---|--------|
| 1 | `Name` | 9 | `Class` |
| 2 | `Set` | 10 | `Identifier` |
| 3 | `ImageFile` | 11 | `SpecialAbility` |
| 4 | `OfficialSet` | 12 | `Rarity` |
| 5 | `Type` | 13 | `Reference` |
| 6 | `Brigade` | 14 | `Sound` |
| 7 | `Strength` | 15 | `Alignment` |
| 8 | `Toughness` | 16 | `Legality` |

### Match / dedupe key: `(Name, Set)`

Columns 1 + 2, compared exact-case after trimming surrounding whitespace.
Verified empirically unique across all 5,461 data rows. `Name` alone is **not**
unique (a card recurs across printings, e.g. `Jephthah (J)` vs `Jephthah (Pa)`);
`ImageFile` is **not** unique (reprints share art). The composite key matches a
maintainer's notion of "the same card."

- New `(Name, Set)` → **ADD**.
- Existing `(Name, Set)` → **UPDATE** in place (overwrite columns 3–16; the
  preview shows a field-level before/after so a helper never silently clobbers).
- Duplicate `(Name, Set)` **within the same paste** → hard error (ambiguous).

> **Rename limitation (deferred):** changing a card's `Name` looks like an ADD
> plus an abandoned old row under this key. v1 treats it that way and *flags* it;
> no dedicated rename flow. (See §11.)

### Validation rules

Run on every pasted row during preview, before any write.

**Hard errors (block Apply):**

- **Column count must be exactly 16** (15 tabs). Wrong count → per-row error with
  the line number and count found ("Row 4 has 14 columns, expected 16 — Excel may
  have dropped trailing empty cells"). This is the single most likely paste
  mistake and the source of the existing 30-field anomaly rows.
- **Required non-empty:** `Name`, `Set`, `ImageFile`, `OfficialSet`, `Type`,
  `Alignment` (all 100% populated in the live file).
- **No embedded tab or newline inside a field.**
- **Duplicate `(Name, Set)` within the paste.**

**Warnings (allow Apply after explicit acknowledgement):**

- Controlled-vocabulary values not seen in the existing file's column
  distributions — computed from the live data, **no hardcoded enum to maintain**.
  Catches typos like `Goood` while allowing genuinely new sets/values. Applies to
  `Alignment` (observed Good/Evil/Neutral), `Rarity`, `Brigade`, `Type`,
  `Legality`, and `OfficialSet` (cross-checked against `setlist.txt`).
- `Strength`/`Toughness` non-numeric (real data contains `*`, `12(1)`, etc., so
  warn, never block).
- Leading/trailing whitespace in `Name`/`Set` (paste artifact that would corrupt
  the key).
- Non-ASCII characters in a new row (smart quotes / en-dashes). The existing file
  legitimately contains these, so **preserve bytes verbatim** but surface a notice
  so the helper can confirm intent.

### Excel paste hygiene

- Strip a single trailing `\r` per line when splitting the paste; an embedded
  mid-row `\r` is a hard error.
- Strip a leading BOM (U+FEFF) if present.
- Do **not** auto-trim field *content* (the data has intentional spacing) — only
  flag suspicious whitespace in key columns.

### Rewrite strategy (byte-exact)

- Read the file as bytes, decode UTF-8, split on `\n`.
- The header line is preserved verbatim; if it does not match the expected
  16-column header, **abort with an error** rather than overwrite.
- Untouched existing rows are passed through as their **original raw strings**,
  never reconstructed from parsed fields, so a round-trip cannot perturb them.
  (This also leaves the two pre-existing 30-tab anomaly rows alone.)
- Updated rows are re-serialized from the original key + new field values.
- **New rows are appended at the end**, in paste order (matches the real T2C-AB
  update in `46be41e`; avoids a massive re-sorted diff).
- Join with `\n`, **no trailing newline**, UTF-8, no BOM.
- Self-check in preview: re-serialized untouched regions must be byte-identical to
  what's on disk; any drift is reported as an internal error, never written.

## 5. updatelist.txt Regeneration

### Verified format (58 lines)

1. **Header (line 1):** `Redemption\t05-28-16` — a LackeyCCG plugin name + a fixed
   date stamp. **Preserved verbatim**; it is *not* the update date and has not
   changed across releases.
2. **Body rows:** `localpath \t url \t checksum`, e.g.
   `plugins/Redemption/sets/carddata.txt \t https://jalstad.github.io/RedemptionLackeyCCG/RedemptionQuick/sets/carddata.txt \t 3927115`.
   The on-disk file is `RedemptionQuick/<localpath minus "plugins/Redemption/">`.
3. **Trailer (last two lines):** preserved verbatim —
   ```
   CardGeneralURLs:
   https://jalstad.github.io/RedemptionLackeyCCG/RedemptionQuick/sets/setimages/general/
   ```
   This is the base URL for per-card images, which are **not** individually listed
   in the manifest.

### Rebuild strategy (surgical, not a crawl)

The manifest is a **curated, ordered list**, not a directory scan. Rebuild =
recompute checksums for the existing rows, in place:

1. Parse `updatelist.txt` into header / ordered body rows / trailer.
2. For each body row, map its path to the on-disk file and **recompute the
   checksum from the local file bytes**. For files being written in this same
   apply (carddata, version, plugininfo), checksum the **new in-memory content**
   so the manifest is consistent with what is written.
3. Replace only the checksum field. Paths, URLs, order untouched.
4. A listed file missing from disk → block with a clear error naming it; never
   silently drop a row.
5. A new on-disk file not in the manifest (e.g. a brand-new `packs/*.jpg`) →
   **warn only**; the tool cannot infer the canonical URL/order, so it does not
   auto-add. (Deferred — see §11.)
6. Re-emit header verbatim + body rows (refreshed checksums, original order) +
   trailer verbatim, preserving the file's existing trailing-newline convention.

### The checksum function — copy verbatim, do not refactor

```python
import math

def checksum(path):
    value = 0
    with open(path, "rb") as fp:
        char = fp.peek(1)
        while char:
            char = fp.read(1)
            if char in [b"\n", b"\r"]:
                continue
            if char:
                value += int.from_bytes(char, byteorder="big", signed=True)
            else:
                value -= 1
            value = int(math.fmod(value, 100000000))
    return value
```

Verified against the live repo (matches `updatelist.txt` exactly):
`version.txt`→**31658**, `plugininfo.txt`→**384808**, `setlist.txt`→**50843**,
`carddata.txt`→**3927115**.

**The `fp.peek()` priming and the `else: value -= 1` branch are load-bearing.**
The final empty `read(1)` at EOF fires `value -= 1` exactly once before the loop
condition (set by the prior `peek`) ends; removing it shifts every checksum by
one. A reimplementation that "cleans this up" produces wrong values. Provide a
companion `checksum_bytes(b: bytes)` with identical semantics so about-to-be-
written content can be checksummed without a temp file.

## 6. Version Bump

Two files, kept in sync from one set of form inputs.

### `version.txt` (LF, no trailing newline)

```
<version>

<lastupdateYYMMDD>260401</lastupdateYYMMDD>
<versionurl>https://jalstad.github.io/RedemptionLackeyCCG/RedemptionQuick/version.txt</versionurl>
<updateurl>https://jalstad.github.io/RedemptionLackeyCCG/RedemptionQuick/updatelist.txt</updateurl>
<message>Redemption Plugin Version 2.3.1: Fixed Babylon T2C AB image</message>

</version>
```

The tool edits **only**:
- `<lastupdateYYMMDD>` → today in `YYMMDD` (prefilled, editable).
- `<message>` → free text, prefilled with the convention
  `Redemption Plugin Version <X.Y.Z>: <summary>`.

Blank lines, both URLs, and the wrapper are preserved verbatim.

### `plugininfo.txt`

Only the text inside `<pluginversion>2.3.1</pluginversion>` changes; all other
lines are byte-identical.

### UI capture

- **Version** input, prefilled with the current value and one-click
  **+patch / +minor / +major** buttons (e.g. `2.3.1` → `2.3.2`). The chosen
  version flows into both `<pluginversion>` and the `<message>` template, so the
  two can never drift.
- **Date** field, prefilled to today's `YYMMDD`.
- **Message summary** field.
- Apply refuses if the new version is not greater than the current (guards against
  shipping a downgrade, which can block LackeyCCG's update check).

`version.txt` and `plugininfo.txt` are themselves manifest files, so their
checksums are recomputed in the same apply step (§5).

## 7. Image Validation

No resizing, no creation — **report only**. Compares the `ImageFile` column
(across the *merged* card set) against files in
`RedemptionQuick/sets/setimages/general/`.

**Filename resolution (verified):**
> expected filename = `ImageFile` if it already ends in `.jpg` (237 rows do),
> else `ImageFile + ".jpg"`. (Naive append would produce `X.jpg.jpg`.)

**Case sensitivity:** compare exact bytes (GitHub Pages / Linux hosting is
case-sensitive even though macOS local FS is not). A file present with different
casing is flagged as a distinct **case-mismatch** warning — exactly the class of
bug fixed in `30124e1`.

**Two reports (always shown, even at zero):**
- **MISSING** — a card references an image with no matching file. Warning (not a
  block) for cards added/updated *this session*; informational for pre-existing
  rows (the live file already has a baseline of gaps, so the tool doesn't refuse
  to run on day one).
- **ORPHANED** — an image file referenced by no card. Always informational; never
  auto-deleted (some orphans are intentional/legacy).

Reports list expected-vs-found filenames so a helper can see
"you uploaded `001-Adam.JPG` but the card says `001-Adam.jpg`."

## 8. UI Flow

Single page, one vertical wizard, plain language. Preview-first: nothing is
written until the maintainer clicks **Apply** on a screen showing exactly what
will change.

```
╔══════════════════════════════════════════════════════════════╗
║  Redemption Plugin Update Tool            (running locally)    ║
║  This tool only changes files on your computer. It will NOT    ║
║  touch git. When it finishes, review the changes and commit    ║
║  them yourself, just like always.                              ║
╠══════════════════════════════════════════════════════════════╣
║  STEP 1 — Paste new card rows                                  ║
║   Copy rows from Excel (all 16 columns, no header) and paste.  ║
║   Leave empty to only bump version / re-checksum.              ║
║   ┌────────────────────────────────────────────────────────┐  ║
║   │ (paste box)                                             │  ║
║   └────────────────────────────────────────────────────────┘  ║
╠══════════════════════════════════════════════════════════════╣
║  STEP 2 — Version & message                                    ║
║   Version: 2.3.1 → [2.3.2]  (+patch)(+minor)(+major)           ║
║   Date (YYMMDD): 260530   Message: Redemption Plugin Ver…      ║
║                                          [ Preview changes ]    ║
╠══════════════════════════════════════════════════════════════╣
║  STEP 3 — Review (NOTHING saved yet)                           ║
║   ✅ 3 cards ADD   ✎ 1 card UPDATE   ❌ 0 errors                ║
║   ⚠ 1 warning: unrecognized Brigade "Pruple"                   ║
║   🖼 Missing(new) 2  Missing(existing) 0  Case 0  Orphan 12     ║
║   Files that will change:                                      ║
║     ▸ sets/carddata.txt   (+3 rows, 1 changed)                 ║
║     ▸ updatelist.txt      (4 checksums updated)                ║
║     ▸ version.txt         (date, message)                      ║
║     ▸ plugininfo.txt      (2.3.1 → 2.3.2)                      ║
║   [ Fix errors ]                  [ Looks good — Apply ✅ ]     ║
╠══════════════════════════════════════════════════════════════╣
║  STEP 4 — Done                                                 ║
║   Files written. Nothing was committed.                        ║
║   Next, in your git tool: review the diff, then commit + push. ║
╚══════════════════════════════════════════════════════════════╝
```

Non-technical guardrails:
- **Apply is disabled while any hard error exists.** Helpers physically cannot
  ship a broken file.
- **Warnings require an explicit "I've reviewed these" check** before Apply
  enables — updates and missing images are never silent.
- **Plain-language errors** tie each problem to a line number and an actual-vs-
  expected explanation.
- **Preview is free and side-effect-free** — re-paste and re-check freely.
- A per-file line-level diff (computed in-tool, not via git) lets the helper sanity
  check before they ever open a terminal.

## 9. Error Handling & Safety

- **Validate before write, always.** `/api/preview` is read-only and runs the
  full parse/merge/validate. `/api/apply` re-validates authoritatively and refuses
  on any hard error (the frontend gate is convenience only).
- **Compute-all-then-write.** All new file contents (merged carddata, new
  checksums, new version/plugininfo) are built in memory first; if any computation
  raises, **nothing is written**.
- **Atomic writes.** Each file is written to a temp file in the same directory,
  then `os.replace()` — atomic on POSIX and Windows; no half-written files even on
  crash.
- **Write order:** data files first (carddata, version, plugininfo), then recompute
  checksums from the now-on-disk bytes, then `updatelist.txt` last, so the manifest
  always reflects final content.
- **Post-write self-verify.** Re-read each written file and confirm its recomputed
  checksum equals the value written into `updatelist.txt`. A mismatch is a loud,
  hard failure (catches any encoding/write drift) — closing the loop the manual
  process leaves open.
- **Safety net is git.** Per decision, the tool keeps **no `.bak` backups** and
  offers no in-tool undo; the maintainer's `git diff` / `git checkout` is the
  recovery path. The tool's job is to (a) never produce a half-written file and
  (b) emit a clean, minimal, reviewable diff. A crash between two atomic file
  swaps leaves a fully-old or fully-new version of each individual file, all
  recoverable via git.
- **Byte-fidelity guards.** Binary read/write; explicit UTF-8, no BOM ever written;
  split on `\n` / join on `\n` (CR never introduced); trailing-newline state of
  each file reproduced exactly (carddata and version.txt have none); a no-op apply
  produces a zero-byte diff.
- **Server hygiene.** Bind `127.0.0.1` only; reject any request path that escapes
  the repo root; writes go only through a fixed allow-list of target files; refuse
  to run if `RedemptionQuick/sets/carddata.txt` is not found (wrong directory).
- **Stale-file guard.** Capture a hash of each target file at preview time; if it
  changed on disk by apply time (someone hand-edited it), abort and ask to
  re-preview rather than clobber.

## 10. Testing Strategy

Stdlib `unittest` only (no test-runner dependency), runnable via
`python3 -m unittest`.

- **Checksum golden tests (highest priority).** Pin the live values:
  `version.txt`=31658, `plugininfo.txt`=384808, `setlist.txt`=50843,
  `carddata.txt`=3927115. Plus crafted byte strings exercising signed high bytes
  (≥0x80), multibyte UTF-8 (`’`, `–`), `\n`/`\r` skipping, and `fmod` wraparound
  near ±100000000. Assert the module equals a literal copy of the reference across
  a fuzz corpus.
- **carddata round-trip identity.** Parse the real file, merge an empty paste,
  re-render → **byte-identical** output (proves no-trailing-newline, encoding,
  pass-through fidelity, and that the 30-tab anomaly rows are preserved).
- **Merge unit tests.** ADD new key; UPDATE existing key (cols 3–16 change, key
  intact, order preserved); new rows append at end in paste order; reject
  15/17/30-column rows, empty Name/Set, duplicate keys in paste; untouched rows
  byte-identical.
- **Excel-hygiene tests.** BOM strip, trailing-`\r` strip, embedded-newline reject,
  smart-quote preservation, the real 30-field defect row flagged.
- **updatelist tests.** Rebuild on an unchanged repo → byte-identical (header,
  order, trailer, trailing-newline preserved); change one byte of a file → exactly
  that one checksum changes; row set identical before/after.
- **version/plugininfo tests.** Only the intended substrings change; downgrade
  rejected; date defaults to today.
- **image tests.** `.jpg`-already-present vs needs-`.jpg` resolution (the
  `X.jpg.jpg` trap); case-mismatch detection (the Babylon scenario); missing vs
  orphaned classification.
- **End-to-end fixture.** On a temp copy of the four files + a small image dir,
  replay a synthetic version of `46be41e` (add a set + update rows + bump version)
  and assert the outputs match golden bytes; post-write self-verify passes.

## 11. Open Questions / Risks (deferred per decisions)

1. **Rename handling — deferred.** Under the `(Name, Set)` key, renaming a card's
   `Name` reads as ADD + orphaned old row. v1 warns only; no rename flow. Revisit
   if renames prove common.
2. **New manifest files — deferred.** A routine update occasionally adds a new
   `packs/*.jpg` or `.dek`. The tool warns when an on-disk file is missing from
   `updatelist.txt` but does not auto-add it (can't infer URL/order). Adding to
   the manifest stays a manual edit for now.
3. **Pre-existing defects — report, don't auto-fix.** Two 30-tab `carddata.txt`
   rows and an `updatelist.txt` `Starter_4th.jpg`/`starter_4th.jpg` case duplicate
   exist in `master`. The tool surfaces these but leaves them untouched to keep
   diffs minimal.
4. **`ImageFile` `.jpg` inconsistency — tolerate, don't normalize.** 237 rows
   carry the extension, the rest don't; the resolver handles both. New pasted rows
   are stored exactly as pasted.
5. **Python on a future machine.** Lowest-rot option overall, but a fresh Windows
   box may lack Python; mitigated by a README note + launcher detection. A frozen
   PyInstaller executable is explicitly rejected (re-introduces build-step rot).
6. **`updatelist.txt` header date `05-28-16`** is not the update date and is never
   touched; locked by the round-trip golden test.
