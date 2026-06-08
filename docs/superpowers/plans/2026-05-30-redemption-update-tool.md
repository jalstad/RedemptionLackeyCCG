# Redemption Plugin Update Tool — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local web app that lets a non-technical helper paste Excel card rows and produce a complete, byte-correct Redemption LackeyCCG plugin release (carddata merge + checksums + updatelist + version bump + image validation), writing files only — never touching git.

**Architecture:** Python 3 standard-library backend (`http.server`) made of small pure modules behind a thin HTTP layer, plus one static `index.html` (vanilla JS). Two endpoints: `/api/preview` (read-only validate/merge/report) and `/api/apply` (re-validate, then atomic writes + post-write checksum self-verify). The bytes previewed are the bytes written.

**Tech Stack:** Python 3.8+ standard library only (`http.server`, `json`, `pathlib`, `tempfile`, `math`, `re`, `unittest`). No third-party packages, no build step. Vanilla HTML/CSS/JS frontend.

**Reference spec:** `docs/superpowers/specs/2026-05-30-redemption-update-tool-design.md`

---

## File Structure

```
tools/updater/
  __init__.py          # marks package so `python3 -m unittest` discovery works
  paths.py             # repo-anchored paths + gh-pages URL prefix (Task 1)
  checksum.py          # verbatim byte-sum checksum + checksum_bytes (Task 2)
  carddata.py          # parse paste, validate, merge, render carddata.txt (Tasks 3-4)
  updatelist.py        # rebuild manifest checksums, preserve header+trailer+order (Task 5)
  version_bump.py      # rewrite version.txt + plugininfo.txt (Task 6)
  images.py            # missing / orphaned / case-mismatch report (Task 7)
  safe_write.py        # atomic temp-file + os.replace write (Task 8)
  pipeline.py          # orchestrate preview() and apply() over all modules (Task 9)
  server.py            # http.server: serve index.html + JSON API (Task 10)
  index.html           # the GUI (Task 11)
  README-for-maintainers.txt   # how to launch (Task 12)
  Start Update Tool.command    # macOS launcher (Task 12)
  Start Update Tool.bat        # Windows launcher (Task 12)
  tests/
    __init__.py
    test_checksum.py
    test_carddata.py
    test_updatelist.py
    test_version_bump.py
    test_images.py
    test_safe_write.py
    test_pipeline_e2e.py
```

All tests run from the repo root with `python3 -m unittest discover -s tools/updater/tests -v`.

---

## Task 1: Package scaffold + repo paths

**Files:**
- Create: `tools/updater/__init__.py`
- Create: `tools/updater/tests/__init__.py`
- Create: `tools/updater/paths.py`
- Test: `tools/updater/tests/test_paths.py`

- [ ] **Step 1: Create empty package markers**

Create `tools/updater/__init__.py` and `tools/updater/tests/__init__.py`, each empty (zero bytes).

- [ ] **Step 2: Write the failing test**

Create `tools/updater/tests/test_paths.py`:

```python
import unittest
from tools.updater import paths


class TestPaths(unittest.TestCase):
    def test_repo_root_contains_redemptionquick(self):
        self.assertTrue((paths.ROOT / "RedemptionQuick").is_dir())

    def test_known_files_exist(self):
        for p in (paths.CARDDATA, paths.UPDATELIST, paths.VERSION,
                  paths.PLUGININFO, paths.SETLIST):
            self.assertTrue(p.is_file(), f"missing {p}")
        self.assertTrue(paths.IMAGES_DIR.is_dir())

    def test_url_prefix(self):
        self.assertEqual(
            paths.URL_PREFIX,
            "https://jalstad.github.io/RedemptionLackeyCCG/RedemptionQuick/",
        )
        self.assertEqual(paths.MANIFEST_PATH_PREFIX, "plugins/Redemption/")
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd /Users/timestes/projects/lackey && python3 -m unittest tools.updater.tests.test_paths -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.updater.paths'`

- [ ] **Step 4: Write the implementation**

Create `tools/updater/paths.py`:

```python
"""Canonical, repo-anchored filesystem paths. Resolved from this file's
location, never the current working directory."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REDEMPTION = ROOT / "RedemptionQuick"

CARDDATA = REDEMPTION / "sets" / "carddata.txt"
UPDATELIST = REDEMPTION / "updatelist.txt"
VERSION = REDEMPTION / "version.txt"
PLUGININFO = REDEMPTION / "plugininfo.txt"
SETLIST = REDEMPTION / "setlist.txt"
IMAGES_DIR = REDEMPTION / "sets" / "setimages" / "general"

URL_PREFIX = "https://jalstad.github.io/RedemptionLackeyCCG/RedemptionQuick/"
MANIFEST_PATH_PREFIX = "plugins/Redemption/"
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /Users/timestes/projects/lackey && python3 -m unittest tools.updater.tests.test_paths -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
cd /Users/timestes/projects/lackey
git add tools/updater/__init__.py tools/updater/tests/__init__.py tools/updater/paths.py tools/updater/tests/test_paths.py
git commit -m "feat(updater): package scaffold and repo paths"
```

---

## Task 2: Checksum (verbatim algorithm + bytes variant)

**Files:**
- Create: `tools/updater/checksum.py`
- Test: `tools/updater/tests/test_checksum.py`

- [ ] **Step 1: Write the failing test**

Create `tools/updater/tests/test_checksum.py`:

```python
import io
import math
import os
import unittest

from tools.updater import checksum, paths


# A literal copy of the canonical reference, used as the oracle.
def _reference(data: bytes) -> int:
    value = 0
    fp = io.BufferedReader(io.BytesIO(data))
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


class TestChecksum(unittest.TestCase):
    def test_golden_live_values(self):
        # Verified against updatelist.txt on 2026-05-30.
        self.assertEqual(checksum.checksum(paths.VERSION), 31658)
        self.assertEqual(checksum.checksum(paths.PLUGININFO), 384808)
        self.assertEqual(checksum.checksum(paths.SETLIST), 50843)
        self.assertEqual(checksum.checksum(paths.CARDDATA), 3927115)

    def test_bytes_matches_file(self):
        data = paths.VERSION.read_bytes()
        self.assertEqual(checksum.checksum_bytes(data), 31658)
        self.assertEqual(checksum.checksum_bytes(data), checksum.checksum(paths.VERSION))

    def test_empty_input_is_zero(self):
        self.assertEqual(checksum.checksum_bytes(b""), 0)

    def test_eof_decrement_is_load_bearing(self):
        # The final empty read fires `value -= 1` exactly once.
        # "A" = 65; result must be 65 - 1 = 64, NOT 65.
        self.assertEqual(checksum.checksum_bytes(b"A"), 64)

    def test_high_bytes_are_signed(self):
        # 0x80 = -128 signed; plus the EOF -1.
        self.assertEqual(checksum.checksum_bytes(b"\x80"), -129)

    def test_newlines_skipped(self):
        self.assertEqual(checksum.checksum_bytes(b"A\r\nB"),
                         checksum.checksum_bytes(b"AB"))

    def test_matches_reference_on_fuzz(self):
        rng = [b"", b"A", b"\x80\x7f", b"hi\nthere\r\n", b"\xff" * 50,
               bytes(range(256)), "smart’quote–dash".encode("utf-8")]
        for data in rng:
            self.assertEqual(checksum.checksum_bytes(data), _reference(data), data)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/timestes/projects/lackey && python3 -m unittest tools.updater.tests.test_checksum -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.updater.checksum'`

- [ ] **Step 3: Write the implementation**

Create `tools/updater/checksum.py`:

```python
"""The plugin's custom byte-sum checksum.

COPIED VERBATIM from the canonical reference. Do NOT refactor: the
`fp.peek(1)` priming and the `else: value -= 1` branch look like dead code
but are load-bearing — the final empty read fires `value -= 1` exactly once,
which shifts every checksum by one if removed. Verified against the live
updatelist.txt (version.txt=31658, carddata.txt=3927115, ...).
"""
import io
import math


def _checksum_fp(fp) -> int:
    value = 0
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


def checksum(path) -> int:
    """Checksum of a file on disk."""
    with open(path, "rb") as fp:
        return _checksum_fp(fp)


def checksum_bytes(data: bytes) -> int:
    """Checksum of in-memory bytes (for content about to be written)."""
    return _checksum_fp(io.BufferedReader(io.BytesIO(data)))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/timestes/projects/lackey && python3 -m unittest tools.updater.tests.test_checksum -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
cd /Users/timestes/projects/lackey
git add tools/updater/checksum.py tools/updater/tests/test_checksum.py
git commit -m "feat(updater): verbatim checksum with golden + reference-fuzz tests"
```

---

## Task 3: carddata — read, split paste, parse & validate

**Files:**
- Create: `tools/updater/carddata.py`
- Test: `tools/updater/tests/test_carddata.py`

- [ ] **Step 1: Write the failing test**

Create `tools/updater/tests/test_carddata.py`:

```python
import unittest

from tools.updater import carddata


HEADER = "\t".join(carddata.COLUMNS)


def row(**kw):
    """Build a 16-field TSV line; unspecified columns are empty."""
    return "\t".join(kw.get(c, "") for c in carddata.COLUMNS)


class TestSplitPaste(unittest.TestCase):
    def test_strips_bom_and_cr_and_blank_trailing_lines(self):
        text = "﻿a\tb\r\nc\td\r\n\n"
        self.assertEqual(carddata.split_paste(text), ["a\tb", "c\td"])

    def test_embedded_cr_is_kept_for_validation(self):
        # a lone CR not at line end stays in the line so validation can reject it
        self.assertEqual(carddata.split_paste("a\rb"), ["a\rb"])


class TestParseValidate(unittest.TestCase):
    def setUp(self):
        self.existing = {("Adam", "Pat")}
        self.known = {"Alignment": {"Good", "Evil"}, "Brigade": {"Red"}}

    def parse(self, lines):
        return carddata.parse_and_validate(
            "\n".join(lines), existing_keys=self.existing, known_values=self.known)

    def test_new_key_is_add(self):
        rep = self.parse([row(Name="Eve", Set="Pat", ImageFile="Eve",
                              OfficialSet="Patriarchs", Type="Hero", Alignment="Good")])
        self.assertEqual(rep.rows[0].action, "ADD")
        self.assertEqual(rep.rows[0].errors, [])
        self.assertTrue(rep.ok)

    def test_existing_key_is_update(self):
        rep = self.parse([row(Name="Adam", Set="Pat", ImageFile="Adam",
                              OfficialSet="Patriarchs", Type="Hero", Alignment="Good")])
        self.assertEqual(rep.rows[0].action, "UPDATE")

    def test_wrong_column_count_is_error(self):
        rep = self.parse(["Eve\tPat\tEve"])  # 3 cols
        self.assertEqual(rep.rows[0].action, "ERROR")
        self.assertIn("16 columns", rep.rows[0].errors[0])
        self.assertFalse(rep.ok)

    def test_missing_required_field_is_error(self):
        rep = self.parse([row(Name="", Set="Pat", ImageFile="x",
                              OfficialSet="Patriarchs", Type="Hero", Alignment="Good")])
        self.assertEqual(rep.rows[0].action, "ERROR")
        self.assertFalse(rep.ok)

    def test_embedded_tab_or_newline_in_field_is_error(self):
        # 17 fields because a value itself contained a tab
        bad = row(Name="E\tve", Set="Pat", ImageFile="x",
                  OfficialSet="Patriarchs", Type="Hero", Alignment="Good")
        rep = self.parse([bad])
        self.assertEqual(rep.rows[0].action, "ERROR")

    def test_duplicate_key_in_paste_is_error(self):
        r = row(Name="Eve", Set="Pat", ImageFile="Eve",
                OfficialSet="Patriarchs", Type="Hero", Alignment="Good")
        rep = self.parse([r, r])
        self.assertTrue(any("duplicate" in e.lower()
                            for e in rep.rows[1].errors))
        self.assertFalse(rep.ok)

    def test_unknown_vocab_value_is_warning_not_error(self):
        rep = self.parse([row(Name="Eve", Set="Pat", ImageFile="Eve",
                              OfficialSet="Patriarchs", Type="Hero",
                              Brigade="Pruple", Alignment="Good")])
        self.assertEqual(rep.rows[0].action, "ADD")
        self.assertEqual(rep.rows[0].errors, [])
        self.assertTrue(any("Brigade" in w for w in rep.rows[0].warnings))

    def test_whitespace_in_key_is_warning(self):
        rep = self.parse([row(Name=" Eve ", Set="Pat", ImageFile="Eve",
                              OfficialSet="Patriarchs", Type="Hero", Alignment="Good")])
        self.assertTrue(any("whitespace" in w.lower() for w in rep.rows[0].warnings))


class TestKnownValues(unittest.TestCase):
    def test_collects_distinct_column_values(self):
        data_lines = [
            row(Name="Adam", Set="Pat", Brigade="Red", Alignment="Good"),
            row(Name="Cain", Set="Pat", Brigade="Black", Alignment="Evil"),
        ]
        known = carddata.collect_known_values(data_lines)
        self.assertEqual(known["Brigade"], {"Red", "Black"})
        self.assertEqual(known["Alignment"], {"Good", "Evil"})

    def test_existing_keys(self):
        data_lines = [row(Name="Adam", Set="Pat"), ""]  # blank line ignored
        self.assertEqual(carddata.existing_keys(data_lines), {("Adam", "Pat")})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/timestes/projects/lackey && python3 -m unittest tools.updater.tests.test_carddata -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.updater.carddata'`

- [ ] **Step 3: Write the implementation**

Create `tools/updater/carddata.py`:

```python
"""Parse, validate, merge and render carddata.txt (16-column, tab-separated,
UTF-8, LF-only, NO trailing newline). Match key is (Name, Set)."""
from dataclasses import dataclass, field
from typing import Optional

COLUMNS = [
    "Name", "Set", "ImageFile", "OfficialSet", "Type", "Brigade",
    "Strength", "Toughness", "Class", "Identifier", "SpecialAbility",
    "Rarity", "Reference", "Sound", "Alignment", "Legality",
]
N_COLUMNS = len(COLUMNS)  # 16
REQUIRED = ["Name", "Set", "ImageFile", "OfficialSet", "Type", "Alignment"]
# Columns whose values we warn about when previously unseen (typo guard).
VOCAB_COLUMNS = ["Type", "Brigade", "Rarity", "Alignment", "Legality", "OfficialSet"]


@dataclass
class RowResult:
    line_no: int
    raw: str
    fields: Optional[list] = None
    key: Optional[tuple] = None
    action: str = "ERROR"          # ADD | UPDATE | ERROR
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


@dataclass
class ParseReport:
    rows: list = field(default_factory=list)

    @property
    def ok(self):
        return all(not r.errors for r in self.rows)

    @property
    def adds(self):
        return [r for r in self.rows if r.action == "ADD"]

    @property
    def updates(self):
        return [r for r in self.rows if r.action == "UPDATE"]


def split_paste(text):
    """Strip BOM, split on \\n, strip a single trailing \\r per line, drop
    blank trailing lines. Embedded (mid-line) CRs are preserved so validation
    can reject them."""
    if text.startswith("﻿"):
        text = text[1:]
    lines = [ln[:-1] if ln.endswith("\r") else ln for ln in text.split("\n")]
    while lines and lines[-1] == "":
        lines.pop()
    return lines


def _split_data_line(line):
    parts = line.split("\t")
    name = parts[0].strip() if parts else ""
    set_ = parts[1].strip() if len(parts) > 1 else ""
    return parts, (name, set_)


def collect_known_values(data_lines):
    known = {c: set() for c in VOCAB_COLUMNS}
    for line in data_lines:
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < N_COLUMNS:
            continue
        for c in VOCAB_COLUMNS:
            val = parts[COLUMNS.index(c)]
            if val:
                known[c].add(val)
    return known


def existing_keys(data_lines):
    keys = set()
    for line in data_lines:
        if not line:
            continue
        _, key = _split_data_line(line)
        keys.add(key)
    return keys


def parse_and_validate(text, existing_keys, known_values):
    report = ParseReport()
    seen_in_paste = set()
    for i, raw in enumerate(split_paste(text), start=1):
        r = RowResult(line_no=i, raw=raw)
        parts = raw.split("\t")
        if "\r" in raw:
            r.errors.append("Row contains an embedded carriage return.")
        if len(parts) != N_COLUMNS:
            r.errors.append(
                f"Row has {len(parts)} columns, expected 16 — Excel may have "
                f"added or dropped trailing empty cells.")
            report.rows.append(r)
            continue
        r.fields = parts
        values = {c: parts[idx] for idx, c in enumerate(COLUMNS)}
        for c in REQUIRED:
            if not values[c].strip():
                r.errors.append(f"Required column '{c}' is empty.")
        key = (values["Name"].strip(), values["Set"].strip())
        r.key = key
        if values["Name"] != values["Name"].strip() or values["Set"] != values["Set"].strip():
            r.warnings.append("Leading/trailing whitespace in Name/Set (paste artifact?).")
        if key in seen_in_paste:
            r.errors.append(f"Duplicate (Name, Set) {key} appears earlier in this paste.")
        seen_in_paste.add(key)
        for c in VOCAB_COLUMNS:
            v = values[c]
            if v and v not in known_values.get(c, set()):
                r.warnings.append(f"Unrecognized {c} value: '{v}' (new — or a typo?).")
        if not r.errors:
            r.action = "UPDATE" if key in existing_keys else "ADD"
        report.rows.append(r)
    return report
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/timestes/projects/lackey && python3 -m unittest tools.updater.tests.test_carddata -v`
Expected: PASS (all tests in TestSplitPaste, TestParseValidate, TestKnownValues)

- [ ] **Step 5: Commit**

```bash
cd /Users/timestes/projects/lackey
git add tools/updater/carddata.py tools/updater/tests/test_carddata.py
git commit -m "feat(updater): carddata paste parsing and validation"
```

---

## Task 4: carddata — read file, merge & render (byte-exact)

**Files:**
- Modify: `tools/updater/carddata.py`
- Test: `tools/updater/tests/test_carddata.py` (add a class)

- [ ] **Step 1: Write the failing test**

Append to `tools/updater/tests/test_carddata.py`:

```python
from tools.updater import paths


class TestMerge(unittest.TestCase):
    def parse(self, lines, existing, known=None):
        return carddata.parse_and_validate(
            "\n".join(lines), existing_keys=existing, known_values=known or {})

    def test_read_carddata_splits_header_and_data(self):
        header, data = carddata.read_carddata(paths.CARDDATA)
        self.assertEqual(header, HEADER)
        self.assertGreater(len(data), 5000)
        self.assertNotEqual(data[-1], "")  # no trailing blank => no trailing newline

    def test_empty_paste_round_trips_byte_identical(self):
        header, data = carddata.read_carddata(paths.CARDDATA)
        rep = self.parse([], existing=set())
        merged = carddata.merge(header, data, rep)
        self.assertEqual(merged, paths.CARDDATA.read_text(encoding="utf-8"))

    def test_add_appends_at_end(self):
        header = HEADER
        data = [row(Name="Adam", Set="Pat", ImageFile="Adam",
                    OfficialSet="Patriarchs", Type="Hero", Alignment="Good")]
        rep = self.parse([row(Name="Eve", Set="Pat", ImageFile="Eve",
                              OfficialSet="Patriarchs", Type="Hero", Alignment="Good")],
                         existing={("Adam", "Pat")})
        merged = carddata.merge(header, data, rep)
        lines = merged.split("\n")
        self.assertEqual(lines[0], HEADER)
        self.assertTrue(lines[1].startswith("Adam\t"))
        self.assertTrue(lines[2].startswith("Eve\t"))
        self.assertFalse(merged.endswith("\n"))

    def test_update_replaces_in_place(self):
        header = HEADER
        data = [
            row(Name="Adam", Set="Pat", ImageFile="Adam", OfficialSet="Patriarchs",
                Type="Hero", Rarity="Common", Alignment="Good"),
            row(Name="Cain", Set="Pat", ImageFile="Cain", OfficialSet="Patriarchs",
                Type="Hero", Alignment="Evil"),
        ]
        rep = self.parse([row(Name="Adam", Set="Pat", ImageFile="Adam",
                              OfficialSet="Patriarchs", Type="Hero",
                              Rarity="Rare", Alignment="Good")],
                         existing={("Adam", "Pat"), ("Cain", "Pat")})
        merged = carddata.merge(header, data, rep)
        lines = merged.split("\n")
        self.assertEqual(len(lines), 3)  # header + 2 rows, no append
        self.assertIn("\tRare\t", lines[1])  # Adam updated in place
        self.assertTrue(lines[2].startswith("Cain\t"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/timestes/projects/lackey && python3 -m unittest tools.updater.tests.test_carddata.TestMerge -v`
Expected: FAIL — `AttributeError: module 'tools.updater.carddata' has no attribute 'read_carddata'`

- [ ] **Step 3: Write the implementation**

Append to `tools/updater/carddata.py`:

```python
def read_carddata(path):
    """Return (header_line, data_lines). Raw strings, split on \\n. The file has
    no trailing newline, so the last element is the last real row."""
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")
    return lines[0], lines[1:]


def merge(header, data_lines, report):
    """Return the full new carddata.txt content. UPDATE rows replace the matching
    existing line in place; ADD rows are appended at the end in paste order.
    Untouched lines pass through as their original strings (byte-exact)."""
    data_lines = list(data_lines)
    index = {}
    for i, line in enumerate(data_lines):
        if not line:
            continue
        parts = line.split("\t")
        index[(parts[0].strip(), parts[1].strip())] = i
    appended = []
    for r in report.rows:
        if r.action == "UPDATE":
            data_lines[index[r.key]] = "\t".join(r.fields)
        elif r.action == "ADD":
            appended.append("\t".join(r.fields))
    return "\n".join([header] + data_lines + appended)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/timestes/projects/lackey && python3 -m unittest tools.updater.tests.test_carddata -v`
Expected: PASS (all carddata tests, including byte-identical round-trip)

- [ ] **Step 5: Commit**

```bash
cd /Users/timestes/projects/lackey
git add tools/updater/carddata.py tools/updater/tests/test_carddata.py
git commit -m "feat(updater): byte-exact carddata merge and render"
```

---

## Task 5: updatelist — rebuild manifest checksums

**Files:**
- Create: `tools/updater/updatelist.py`
- Test: `tools/updater/tests/test_updatelist.py`

- [ ] **Step 1: Write the failing test**

Create `tools/updater/tests/test_updatelist.py`:

```python
import unittest

from tools.updater import updatelist, checksum, paths


class TestUpdatelist(unittest.TestCase):
    def test_rebuild_unchanged_is_byte_identical(self):
        text = paths.UPDATELIST.read_text(encoding="utf-8")

        def real_checksum(rel):
            return checksum.checksum(paths.REDEMPTION / rel)

        rebuilt = updatelist.rebuild(text, real_checksum)
        self.assertEqual(rebuilt, text)

    def test_header_and_trailer_preserved(self):
        text = paths.UPDATELIST.read_text(encoding="utf-8")
        rebuilt = updatelist.rebuild(text, lambda rel: 0)
        lines = rebuilt.split("\n")
        self.assertEqual(lines[0], "Redemption\t05-28-16")
        self.assertIn("CardGeneralURLs:", rebuilt)
        self.assertTrue(rebuilt.rstrip("\n").endswith(
            "/RedemptionQuick/sets/setimages/general/"))

    def test_only_checksum_field_changes(self):
        text = paths.UPDATELIST.read_text(encoding="utf-8")
        rebuilt = updatelist.rebuild(text, lambda rel: 42)
        # carddata row's checksum becomes 42; path and URL unchanged
        line = [l for l in rebuilt.split("\n") if "sets/carddata.txt" in l][0]
        path, url, cs = line.split("\t")
        self.assertEqual(path, "plugins/Redemption/sets/carddata.txt")
        self.assertEqual(cs, "42")

    def test_missing_file_raises(self):
        text = ("Redemption\t05-28-16\n"
                "plugins/Redemption/nope.txt\thttp://x/nope.txt\t1\n"
                "CardGeneralURLs:\nhttp://x/\n")

        def boom(rel):
            raise FileNotFoundError(rel)

        with self.assertRaises(updatelist.ManifestError):
            updatelist.rebuild(text, boom)

    def test_paths_to_rechecksum(self):
        text = paths.UPDATELIST.read_text(encoding="utf-8")
        rels = updatelist.manifest_rels(text)
        self.assertIn("sets/carddata.txt", rels)
        self.assertIn("version.txt", rels)
        self.assertNotIn("", rels)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/timestes/projects/lackey && python3 -m unittest tools.updater.tests.test_updatelist -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.updater.updatelist'`

- [ ] **Step 3: Write the implementation**

Create `tools/updater/updatelist.py`:

```python
"""Rebuild updatelist.txt checksums in place. The header line and the trailing
CardGeneralURLs: block are preserved verbatim; row set and order are never
changed (it is a curated manifest, not a directory crawl)."""
from .paths import MANIFEST_PATH_PREFIX


class ManifestError(Exception):
    pass


def _is_body_row(i, line):
    if i == 0:
        return False
    parts = line.split("\t")
    return len(parts) == 3 and parts[0].startswith(MANIFEST_PATH_PREFIX)


def manifest_rels(text):
    """The repo-relative paths (under RedemptionQuick/) listed in the manifest."""
    had_nl = text.endswith("\n")
    lines = text.split("\n")
    if had_nl:
        lines = lines[:-1]
    rels = []
    for i, line in enumerate(lines):
        if _is_body_row(i, line):
            rels.append(line.split("\t")[0][len(MANIFEST_PATH_PREFIX):])
    return rels


def rebuild(text, checksum_for_rel):
    """Return new updatelist.txt content. `checksum_for_rel(rel) -> int` supplies
    the checksum for each manifest path (repo-relative, under RedemptionQuick/)."""
    had_nl = text.endswith("\n")
    lines = text.split("\n")
    if had_nl:
        lines = lines[:-1]
    out = []
    for i, line in enumerate(lines):
        if not _is_body_row(i, line):
            out.append(line)
            continue
        path, url, _old = line.split("\t")
        rel = path[len(MANIFEST_PATH_PREFIX):]
        try:
            value = checksum_for_rel(rel)
        except FileNotFoundError as e:
            raise ManifestError(
                f"Manifest lists '{path}' but the file is missing: {e}") from e
        out.append("\t".join([path, url, str(value)]))
    result = "\n".join(out)
    if had_nl:
        result += "\n"
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/timestes/projects/lackey && python3 -m unittest tools.updater.tests.test_updatelist -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
cd /Users/timestes/projects/lackey
git add tools/updater/updatelist.py tools/updater/tests/test_updatelist.py
git commit -m "feat(updater): updatelist manifest rebuild preserving header/trailer/order"
```

---

## Task 6: version_bump — version.txt + plugininfo.txt

**Files:**
- Create: `tools/updater/version_bump.py`
- Test: `tools/updater/tests/test_version_bump.py`

- [ ] **Step 1: Write the failing test**

Create `tools/updater/tests/test_version_bump.py`:

```python
import unittest

from tools.updater import version_bump as vb, paths


class TestVersionBump(unittest.TestCase):
    def test_read_current_version(self):
        info = paths.PLUGININFO.read_text(encoding="utf-8")
        self.assertEqual(vb.read_current_version(info), "2.3.1")

    def test_bump_patch_minor_major(self):
        self.assertEqual(vb.bump("2.3.1", "patch"), "2.3.2")
        self.assertEqual(vb.bump("2.3.1", "minor"), "2.4.0")
        self.assertEqual(vb.bump("2.3.1", "major"), "3.0.0")

    def test_build_message(self):
        self.assertEqual(
            vb.build_message("2.3.2", "Added Foo set"),
            "Redemption Plugin Version 2.3.2: Added Foo set")

    def test_bump_plugininfo_changes_only_pluginversion(self):
        info = paths.PLUGININFO.read_text(encoding="utf-8")
        out = vb.bump_plugininfo(info, "2.3.2")
        self.assertIn("<pluginversion>2.3.2</pluginversion>", out)
        self.assertEqual(out.replace("2.3.2", "2.3.1"), info)  # nothing else moved

    def test_bump_version_txt_changes_only_date_and_message(self):
        ver = paths.VERSION.read_text(encoding="utf-8")
        out = vb.bump_version_txt(ver, yymmdd="260530",
                                  message="Redemption Plugin Version 2.3.2: x")
        self.assertIn("<lastupdateYYMMDD>260530</lastupdateYYMMDD>", out)
        self.assertIn("<message>Redemption Plugin Version 2.3.2: x</message>", out)
        # URLs and wrapper untouched
        self.assertIn("<versionurl>https://jalstad.github.io", out)
        self.assertTrue(out.startswith("<version>"))

    def test_message_with_special_regex_chars_is_literal(self):
        ver = paths.VERSION.read_text(encoding="utf-8")
        out = vb.bump_version_txt(ver, yymmdd="260530",
                                  message=r"fix \1 and 100% of $items")
        self.assertIn(r"<message>fix \1 and 100% of $items</message>", out)

    def test_is_newer(self):
        self.assertTrue(vb.is_newer("2.3.2", "2.3.1"))
        self.assertTrue(vb.is_newer("2.4.0", "2.3.9"))
        self.assertFalse(vb.is_newer("2.3.1", "2.3.1"))
        self.assertFalse(vb.is_newer("2.3.0", "2.3.1"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/timestes/projects/lackey && python3 -m unittest tools.updater.tests.test_version_bump -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.updater.version_bump'`

- [ ] **Step 3: Write the implementation**

Create `tools/updater/version_bump.py`:

```python
"""Bump version.txt (date + message) and plugininfo.txt (<pluginversion>).
Only the intended substrings change; everything else is byte-preserved.
Replacements use callables so version strings containing regex metachars
(\\1, $, %, etc.) are treated literally."""
import re

_PLUGINVERSION = re.compile(r"<pluginversion>.*?</pluginversion>", re.S)
_LASTUPDATE = re.compile(r"<lastupdateYYMMDD>.*?</lastupdateYYMMDD>", re.S)
_MESSAGE = re.compile(r"<message>.*?</message>", re.S)


def read_current_version(plugininfo_text):
    m = re.search(r"<pluginversion>(.*?)</pluginversion>", plugininfo_text, re.S)
    if not m:
        raise ValueError("No <pluginversion> found in plugininfo.txt")
    return m.group(1)


def bump(version, part):
    major, minor, patch = (int(x) for x in version.split("."))
    if part == "patch":
        patch += 1
    elif part == "minor":
        minor, patch = minor + 1, 0
    elif part == "major":
        major, minor, patch = major + 1, 0, 0
    else:
        raise ValueError(part)
    return f"{major}.{minor}.{patch}"


def is_newer(new, current):
    def parts(v):
        return tuple(int(x) for x in v.split("."))
    return parts(new) > parts(current)


def build_message(version, summary):
    return f"Redemption Plugin Version {version}: {summary}"


def bump_plugininfo(text, new_version):
    return _PLUGINVERSION.sub(
        lambda m: f"<pluginversion>{new_version}</pluginversion>", text, count=1)


def bump_version_txt(text, yymmdd, message):
    text = _LASTUPDATE.sub(
        lambda m: f"<lastupdateYYMMDD>{yymmdd}</lastupdateYYMMDD>", text, count=1)
    text = _MESSAGE.sub(
        lambda m: f"<message>{message}</message>", text, count=1)
    return text
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/timestes/projects/lackey && python3 -m unittest tools.updater.tests.test_version_bump -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
cd /Users/timestes/projects/lackey
git add tools/updater/version_bump.py tools/updater/tests/test_version_bump.py
git commit -m "feat(updater): version.txt and plugininfo.txt bump"
```

---

## Task 7: images — missing / orphaned / case-mismatch

**Files:**
- Create: `tools/updater/images.py`
- Test: `tools/updater/tests/test_images.py`

- [ ] **Step 1: Write the failing test**

Create `tools/updater/tests/test_images.py`:

```python
import unittest

from tools.updater import images


class TestResolve(unittest.TestCase):
    def test_appends_jpg_when_absent(self):
        self.assertEqual(images.resolve("A_Look_Back_(Wo)"), "A_Look_Back_(Wo).jpg")

    def test_keeps_existing_jpg(self):
        self.assertEqual(images.resolve("139-Abeyance.jpg"), "139-Abeyance.jpg")

    def test_existing_jpg_case_insensitive_suffix(self):
        self.assertEqual(images.resolve("X.JPG"), "X.JPG")


class TestValidate(unittest.TestCase):
    def test_missing_orphan_and_case(self):
        referenced = {"a.jpg", "b.jpg", "Babylon.jpg"}
        available = {"a.jpg", "c.jpg", "babylon.jpg"}
        rep = images.validate(referenced, available)
        self.assertEqual(rep["missing"], ["b.jpg"])
        self.assertEqual(rep["orphaned"], ["c.jpg"])
        self.assertEqual(rep["case_mismatch"], ["Babylon.jpg"])

    def test_referenced_from_rows(self):
        # rows are field-lists (index 2 == ImageFile)
        from tools.updater import carddata
        rows = [
            ["Eve", "Pat", "Eve", "Patriarchs", "Hero", "", "", "", "", "",
             "", "", "", "", "Good", ""],
            ["Cain", "Pat", "139-Abeyance.jpg", "Patriarchs", "Hero", "", "",
             "", "", "", "", "", "", "", "Evil", ""],
        ]
        refs = images.referenced_filenames(rows)
        self.assertEqual(refs, {"Eve.jpg", "139-Abeyance.jpg"})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/timestes/projects/lackey && python3 -m unittest tools.updater.tests.test_images -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.updater.images'`

- [ ] **Step 3: Write the implementation**

Create `tools/updater/images.py`:

```python
"""Validate card image references against files on disk. Report only — never
resizes, creates, or deletes. Comparison is case-sensitive (GitHub Pages is
case-sensitive); a present-but-differently-cased file is a distinct warning."""
import os

IMAGEFILE_COLUMN = 2  # index into a carddata field-list


def resolve(image_file):
    """Expected on-disk filename for an ImageFile value."""
    if image_file.lower().endswith(".jpg"):
        return image_file
    return image_file + ".jpg"


def referenced_filenames(rows):
    """rows: iterable of 16-field lists. Returns the set of expected filenames."""
    return {resolve(r[IMAGEFILE_COLUMN]) for r in rows if len(r) > IMAGEFILE_COLUMN}


def list_available(images_dir):
    return {name for name in os.listdir(images_dir)
            if name.lower().endswith(".jpg")}


def validate(referenced, available):
    avail_lower = {a.lower(): a for a in available}
    missing_all = referenced - available
    case_mismatch = sorted(f for f in missing_all if f.lower() in avail_lower)
    missing = sorted(f for f in missing_all if f.lower() not in avail_lower)
    orphaned = sorted(available - referenced)
    return {"missing": missing, "orphaned": orphaned, "case_mismatch": case_mismatch}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/timestes/projects/lackey && python3 -m unittest tools.updater.tests.test_images -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
cd /Users/timestes/projects/lackey
git add tools/updater/images.py tools/updater/tests/test_images.py
git commit -m "feat(updater): image presence validation"
```

---

## Task 8: safe_write — atomic writes

**Files:**
- Create: `tools/updater/safe_write.py`
- Test: `tools/updater/tests/test_safe_write.py`

- [ ] **Step 1: Write the failing test**

Create `tools/updater/tests/test_safe_write.py`:

```python
import os
import tempfile
import unittest

from tools.updater import safe_write


class TestSafeWrite(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "f.txt")

    def test_writes_exact_bytes(self):
        safe_write.atomic_write(self.path, b"hello\xff")
        with open(self.path, "rb") as f:
            self.assertEqual(f.read(), b"hello\xff")

    def test_overwrites_existing(self):
        with open(self.path, "wb") as f:
            f.write(b"old")
        safe_write.atomic_write(self.path, b"new")
        with open(self.path, "rb") as f:
            self.assertEqual(f.read(), b"new")

    def test_leaves_no_temp_files_on_success(self):
        safe_write.atomic_write(self.path, b"x")
        self.assertEqual(os.listdir(self.dir), ["f.txt"])

    def test_no_trailing_newline_added(self):
        safe_write.atomic_write(self.path, b"a\tb")
        with open(self.path, "rb") as f:
            self.assertEqual(f.read(), b"a\tb")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/timestes/projects/lackey && python3 -m unittest tools.updater.tests.test_safe_write -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.updater.safe_write'`

- [ ] **Step 3: Write the implementation**

Create `tools/updater/safe_write.py`:

```python
"""Atomic file writes: write a temp file in the same directory, then os.replace.
Writes exact bytes — never adds a trailing newline or transforms content."""
import os
import tempfile


def atomic_write(path, data: bytes):
    directory = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=directory)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/timestes/projects/lackey && python3 -m unittest tools.updater.tests.test_safe_write -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
cd /Users/timestes/projects/lackey
git add tools/updater/safe_write.py tools/updater/tests/test_safe_write.py
git commit -m "feat(updater): atomic file writes"
```

---

## Task 9: pipeline — orchestrate preview() and apply()

**Files:**
- Create: `tools/updater/pipeline.py`
- Test: `tools/updater/tests/test_pipeline_e2e.py`

This is the integration layer. `preview()` reads the live repo, runs the full validate/merge/report computation in memory and writes nothing. `apply()` re-runs it and writes the four files atomically, then re-checksums on disk to self-verify. To test against a sandbox, both accept an injectable `repo` object describing the file paths.

- [ ] **Step 1: Write the failing test**

Create `tools/updater/tests/test_pipeline_e2e.py`:

```python
import shutil
import tempfile
import unittest
from pathlib import Path

from tools.updater import pipeline, paths, checksum, carddata


class RepoFixture:
    """A throwaway copy of the four metadata files + a tiny image dir."""
    def __init__(self, root):
        self.root = Path(root)
        red = self.root / "RedemptionQuick"
        (red / "sets" / "setimages" / "general").mkdir(parents=True)
        shutil.copy(paths.CARDDATA, red / "sets" / "carddata.txt")
        shutil.copy(paths.UPDATELIST, red / "updatelist.txt")
        shutil.copy(paths.VERSION, red / "version.txt")
        shutil.copy(paths.PLUGININFO, red / "plugininfo.txt")
        shutil.copy(paths.SETLIST, red / "setlist.txt")
        self.repo = pipeline.Repo(red)


class TestPipeline(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.fix = RepoFixture(self.tmp)
        self.repo = self.fix.repo

    def _new_card_row(self):
        return "\t".join([
            "Zzz Test Card", "ZZZ", "zzz-test", "Test Set", "Hero",
            "", "", "", "", "", "Does nothing.", "Common", "", "", "Good", ""])

    def test_preview_writes_nothing(self):
        before = self.repo.carddata.read_bytes()
        result = pipeline.preview(self.repo, self._new_card_row(),
                                  version="2.3.2", yymmdd="260530",
                                  message="Redemption Plugin Version 2.3.2: test")
        self.assertTrue(result["ok"])
        self.assertEqual(result["counts"]["add"], 1)
        self.assertEqual(self.repo.carddata.read_bytes(), before)  # unchanged

    def test_apply_writes_correct_checksums(self):
        pipeline.apply(self.repo, self._new_card_row(),
                       version="2.3.2", yymmdd="260530",
                       message="Redemption Plugin Version 2.3.2: test")
        # The new card is appended
        text = self.repo.carddata.read_text(encoding="utf-8")
        self.assertTrue(text.rstrip("\n").endswith("Good\t"))
        self.assertFalse(text.endswith("\n"))
        # updatelist's carddata checksum matches the file actually on disk
        ul = self.repo.updatelist.read_text(encoding="utf-8")
        cs_line = [l for l in ul.split("\n") if "sets/carddata.txt" in l][0]
        recorded = int(cs_line.split("\t")[2])
        self.assertEqual(recorded, checksum.checksum(self.repo.carddata))
        # version + plugininfo bumped
        self.assertIn("<pluginversion>2.3.2</pluginversion>",
                      self.repo.plugininfo.read_text(encoding="utf-8"))
        self.assertIn("<lastupdateYYMMDD>260530</lastupdateYYMMDD>",
                      self.repo.version.read_text(encoding="utf-8"))

    def test_apply_refuses_on_error(self):
        with self.assertRaises(pipeline.ValidationError):
            pipeline.apply(self.repo, "too\tfew\tcols",
                           version="2.3.2", yymmdd="260530", message="x")

    def test_apply_refuses_downgrade(self):
        with self.assertRaises(pipeline.ValidationError):
            pipeline.apply(self.repo, "", version="2.3.1",
                           yymmdd="260530", message="x")

    def test_empty_paste_version_only_keeps_carddata_identical(self):
        before = self.repo.carddata.read_bytes()
        pipeline.apply(self.repo, "", version="2.3.2",
                       yymmdd="260530", message="Redemption Plugin Version 2.3.2: x")
        self.assertEqual(self.repo.carddata.read_bytes(), before)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/timestes/projects/lackey && python3 -m unittest tools.updater.tests.test_pipeline_e2e -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.updater.pipeline'`

- [ ] **Step 3: Write the implementation**

Create `tools/updater/pipeline.py`:

```python
"""Orchestrates preview (read-only) and apply (atomic write) across all modules.
The bytes computed in preview are exactly the bytes apply writes."""
from pathlib import Path

from . import carddata, updatelist, version_bump, images, checksum, safe_write


class ValidationError(Exception):
    pass


class Repo:
    """Bundles the file paths the pipeline operates on, so tests can point it at
    a sandbox copy. Defaults to the live RedemptionQuick directory."""
    def __init__(self, redemption_dir):
        d = Path(redemption_dir)
        self.redemption = d
        self.carddata = d / "sets" / "carddata.txt"
        self.updatelist = d / "updatelist.txt"
        self.version = d / "version.txt"
        self.plugininfo = d / "plugininfo.txt"
        self.images_dir = d / "sets" / "setimages" / "general"


def _live_repo():
    from . import paths
    return Repo(paths.REDEMPTION)


def _compute(repo, pasted_text, version, yymmdd, message):
    """Pure computation shared by preview and apply. Returns a dict of the new
    file contents (bytes) plus a report. Raises ValidationError on hard errors."""
    info_text = repo.plugininfo.read_text(encoding="utf-8")
    current = version_bump.read_current_version(info_text)
    if not version_bump.is_newer(version, current):
        raise ValidationError(
            f"New version {version} must be greater than current {current}.")

    header, data_lines = carddata.read_carddata(repo.carddata)
    known = carddata.collect_known_values(data_lines)
    existing = carddata.existing_keys(data_lines)
    report = carddata.parse_and_validate(pasted_text, existing, known)
    if not report.ok:
        bad = [f"line {r.line_no}: {'; '.join(r.errors)}"
               for r in report.rows if r.errors]
        raise ValidationError("Card data has errors:\n" + "\n".join(bad))

    new_carddata = carddata.merge(header, data_lines, report).encode("utf-8")
    new_version = version_bump.bump_version_txt(
        repo.version.read_text(encoding="utf-8"), yymmdd, message).encode("utf-8")
    new_plugininfo = version_bump.bump_plugininfo(info_text, version).encode("utf-8")

    in_memory = {
        "sets/carddata.txt": new_carddata,
        "version.txt": new_version,
        "plugininfo.txt": new_plugininfo,
    }

    def checksum_for_rel(rel):
        if rel in in_memory:
            return checksum.checksum_bytes(in_memory[rel])
        return checksum.checksum(repo.redemption / rel)

    new_updatelist = updatelist.rebuild(
        repo.updatelist.read_text(encoding="utf-8"), checksum_for_rel).encode("utf-8")

    # image report over the merged set
    merged_rows = ([ln.split("\t") for ln in data_lines if ln] +
                   [r.fields for r in report.adds] +
                   [r.fields for r in report.updates])
    referenced = images.referenced_filenames(merged_rows)
    available = images.list_available(repo.images_dir)
    new_refs = images.referenced_filenames(
        [r.fields for r in report.adds + report.updates])
    img = images.validate(referenced, available)
    img["missing_new"] = sorted(f for f in img["missing"] if f in new_refs)

    return {
        "report": report,
        "files": {
            repo.carddata: new_carddata,
            repo.version: new_version,
            repo.plugininfo: new_plugininfo,
            repo.updatelist: new_updatelist,
        },
        "images": img,
    }


def preview(repo=None, pasted_text="", *, version, yymmdd, message):
    repo = repo or _live_repo()
    try:
        c = _compute(repo, pasted_text, version, yymmdd, message)
    except ValidationError as e:
        return {"ok": False, "error": str(e)}
    r = c["report"]
    return {
        "ok": True,
        "counts": {"add": len(r.adds), "update": len(r.updates)},
        "warnings": [f"line {row.line_no}: {w}"
                     for row in r.rows for w in row.warnings],
        "images": c["images"],
    }


def apply(repo=None, pasted_text="", *, version, yymmdd, message):
    repo = repo or _live_repo()
    c = _compute(repo, pasted_text, version, yymmdd, message)  # re-validates
    # data files first, manifest already computed against in-memory bytes
    for path, data in c["files"].items():
        safe_write.atomic_write(str(path), data)
    # post-write self-verify: every manifest checksum must match disk
    ul = repo.updatelist.read_text(encoding="utf-8")
    for line in ul.split("\n"):
        parts = line.split("\t")
        if len(parts) == 3 and parts[0].startswith("plugins/Redemption/"):
            rel = parts[0][len("plugins/Redemption/"):]
            on_disk = checksum.checksum(repo.redemption / rel)
            if int(parts[2]) != on_disk:
                raise RuntimeError(
                    f"Self-verify failed for {rel}: manifest {parts[2]} "
                    f"!= disk {on_disk}")
    return {"ok": True, "images": c["images"]}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/timestes/projects/lackey && python3 -m unittest tools.updater.tests.test_pipeline_e2e -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Run the full suite**

Run: `cd /Users/timestes/projects/lackey && python3 -m unittest discover -s tools/updater/tests -v`
Expected: PASS (all tests across all modules)

- [ ] **Step 6: Commit**

```bash
cd /Users/timestes/projects/lackey
git add tools/updater/pipeline.py tools/updater/tests/test_pipeline_e2e.py
git commit -m "feat(updater): preview/apply pipeline with post-write self-verify"
```

---

## Task 10: server — http.server + JSON API

**Files:**
- Create: `tools/updater/server.py`
- Test: `tools/updater/tests/test_server.py`

- [ ] **Step 1: Write the failing test**

Create `tools/updater/tests/test_server.py`:

```python
import json
import threading
import unittest
import urllib.request
from http.server import HTTPServer

from tools.updater import server


class TestServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = HTTPServer(("127.0.0.1", 0), server.Handler)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()

    def _get(self, path):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}") as r:
            return r.status, r.read()

    def _post(self, path, payload):
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())

    def test_serves_index_html(self):
        status, body = self._get("/")
        self.assertEqual(status, 200)
        self.assertIn(b"<html", body.lower())

    def test_preview_endpoint_returns_current_version(self):
        status, data = self._post("/api/current", {})
        self.assertEqual(status, 200)
        self.assertEqual(data["version"], "2.3.1")

    def test_preview_invalid_paste_returns_ok_false(self):
        status, data = self._post("/api/preview", {
            "pasted_text": "too\tfew", "version": "2.3.2",
            "yymmdd": "260530", "message": "x"})
        self.assertEqual(status, 200)
        self.assertFalse(data["ok"])
        self.assertIn("error", data)
```

Note: `/api/current` and `/api/preview` operate on the LIVE repo (read-only), so these tests must not write. `apply` is exercised in the pipeline e2e test against a sandbox, so the server test deliberately avoids calling `/api/apply`.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/timestes/projects/lackey && python3 -m unittest tools.updater.tests.test_server -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.updater.server'`

- [ ] **Step 3: Write the implementation**

Create `tools/updater/server.py`:

```python
"""Thin localhost HTTP layer. Serves index.html and a small JSON API that
delegates to pipeline. Binds to 127.0.0.1 only. No business logic here."""
import json
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from . import pipeline, version_bump

_INDEX = Path(__file__).resolve().parent / "index.html"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # quiet

    def _send(self, status, body, content_type="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        if not length:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, _INDEX.read_bytes(), "text/html; charset=utf-8")
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        try:
            payload = self._read_json()
            if self.path == "/api/current":
                from . import paths
                info = paths.PLUGININFO.read_text(encoding="utf-8")
                cur = version_bump.read_current_version(info)
                self._send(200, {"version": cur,
                                 "suggested": version_bump.bump(cur, "patch")})
            elif self.path == "/api/preview":
                self._send(200, pipeline.preview(
                    pasted_text=payload.get("pasted_text", ""),
                    version=payload["version"], yymmdd=payload["yymmdd"],
                    message=payload["message"]))
            elif self.path == "/api/apply":
                try:
                    result = pipeline.apply(
                        pasted_text=payload.get("pasted_text", ""),
                        version=payload["version"], yymmdd=payload["yymmdd"],
                        message=payload["message"])
                    self._send(200, {"ok": True, "images": result["images"]})
                except pipeline.ValidationError as e:
                    self._send(400, {"ok": False, "error": str(e)})
            else:
                self._send(404, {"error": "not found"})
        except Exception as e:  # never leak a stack trace to the browser
            self._send(500, {"error": str(e)})


def main(port=8765):
    httpd = HTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}"
    print(f"Redemption Update Tool running at {url}  (Ctrl+C to stop)")
    try:
        webbrowser.open(url)
    except Exception:
        pass
    httpd.serve_forever()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Create a placeholder index.html so the server test can serve it**

Create `tools/updater/index.html` with minimal content (replaced fully in Task 11):

```html
<!doctype html>
<html><head><meta charset="utf-8"><title>Redemption Update Tool</title></head>
<body><h1>Redemption Update Tool</h1></body></html>
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /Users/timestes/projects/lackey && python3 -m unittest tools.updater.tests.test_server -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
cd /Users/timestes/projects/lackey
git add tools/updater/server.py tools/updater/index.html tools/updater/tests/test_server.py
git commit -m "feat(updater): localhost http.server JSON API"
```

---

## Task 11: index.html — the GUI

**Files:**
- Modify: `tools/updater/index.html`

This task has no unit test (it is UI); it ends with a manual smoke check. Replace the placeholder `index.html` with the full single-page wizard.

- [ ] **Step 1: Write the full index.html**

Replace the entire contents of `tools/updater/index.html`:

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Redemption Plugin Update Tool</title>
<style>
  body { font: 15px/1.5 system-ui, sans-serif; max-width: 880px; margin: 1.5rem auto;
         padding: 0 1rem; color: #1a1a1a; }
  h1 { font-size: 1.4rem; }
  .banner { background: #fff8e1; border: 1px solid #f0d000; padding: .6rem .9rem;
            border-radius: 6px; margin-bottom: 1rem; }
  fieldset { border: 1px solid #ccc; border-radius: 8px; margin: 1rem 0; padding: 1rem; }
  legend { font-weight: 600; padding: 0 .4rem; }
  textarea { width: 100%; height: 9rem; font-family: ui-monospace, monospace; }
  label { display: inline-block; min-width: 8rem; }
  input[type=text] { padding: .3rem; }
  button { font: inherit; padding: .5rem 1rem; border-radius: 6px; cursor: pointer; }
  button.primary { background: #2e7d32; color: #fff; border: none; }
  button:disabled { opacity: .5; cursor: not-allowed; }
  .err { color: #b00020; } .warn { color: #946200; } .ok { color: #2e7d32; }
  .counts span { margin-right: 1rem; font-weight: 600; }
  pre { background: #f5f5f5; padding: .6rem; border-radius: 6px; white-space: pre-wrap; }
  .hidden { display: none; }
  .cols { font-size: .85rem; color: #555; }
</style>
</head>
<body>
<h1>Redemption Plugin Update Tool</h1>
<div class="banner">
  This tool only changes files on your computer. It will <b>not</b> touch git.
  When it finishes, review the changes and commit them yourself, just like always.
</div>

<fieldset>
  <legend>Step 1 — Paste new card rows</legend>
  <p>Copy the rows from Excel (all 16 columns, <b>no header row</b>) and paste below.
     Leave empty to only bump the version / re-checksum.</p>
  <textarea id="paste" placeholder="Name⇥Set⇥ImageFile⇥…⇥Legality"></textarea>
  <p class="cols">Columns: Name · Set · ImageFile · OfficialSet · Type · Brigade ·
     Strength · Toughness · Class · Identifier · SpecialAbility · Rarity ·
     Reference · Sound · Alignment · Legality</p>
</fieldset>

<fieldset>
  <legend>Step 2 — Version &amp; message</legend>
  <p><label>Current version</label> <span id="current">…</span></p>
  <p><label>New version</label>
     <input type="text" id="version" size="10">
     <button type="button" onclick="bump('patch')">+patch</button>
     <button type="button" onclick="bump('minor')">+minor</button>
     <button type="button" onclick="bump('major')">+major</button></p>
  <p><label>Date (YYMMDD)</label> <input type="text" id="yymmdd" size="8"></p>
  <p><label>Message</label> <input type="text" id="message" size="60"></p>
  <button type="button" class="primary" onclick="preview()">Preview changes</button>
</fieldset>

<fieldset id="review" class="hidden">
  <legend>Step 3 — Review (nothing saved yet)</legend>
  <div id="result"></div>
  <p><label><input type="checkbox" id="ackwarn"> I have reviewed the warnings above.</label></p>
  <button type="button" class="primary" id="applybtn" onclick="apply()">Looks good — Apply</button>
</fieldset>

<fieldset id="done" class="hidden">
  <legend>Step 4 — Done</legend>
  <p class="ok">Files written. Nothing was committed.</p>
  <p>Next, in your git tool: review the diff, then commit &amp; push as usual.</p>
</fieldset>

<script>
let lastPreview = null;

async function api(path, payload) {
  const r = await fetch(path, {method: "POST",
    headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload || {})});
  return r.json();
}
function payload() {
  return {pasted_text: document.getElementById("paste").value,
          version: document.getElementById("version").value.trim(),
          yymmdd: document.getElementById("yymmdd").value.trim(),
          message: document.getElementById("message").value};
}
function bump(part) {
  const v = document.getElementById("version").value.trim().split(".").map(Number);
  if (v.length !== 3 || v.some(isNaN)) return;
  if (part === "patch") v[2]++;
  else if (part === "minor") { v[1]++; v[2] = 0; }
  else { v[0]++; v[1] = 0; v[2] = 0; }
  setVersion(v.join("."));
}
function setVersion(ver) {
  document.getElementById("version").value = ver;
  const m = document.getElementById("message");
  m.value = "Redemption Plugin Version " + ver + ": ";
}
async function preview() {
  const data = await api("/api/preview", payload());
  lastPreview = data;
  const el = document.getElementById("result");
  document.getElementById("review").classList.remove("hidden");
  if (!data.ok) {
    el.innerHTML = '<p class="err"><b>Cannot apply — fix these first:</b></p><pre class="err">'
      + escapeHtml(data.error) + '</pre>';
    enableApply(false);
    return;
  }
  let html = '<p class="counts"><span class="ok">' + data.counts.add + ' ADD</span>'
    + '<span>' + data.counts.update + ' UPDATE</span></p>';
  if (data.warnings.length) {
    html += '<p class="warn"><b>Warnings:</b></p><pre class="warn">'
      + data.warnings.map(escapeHtml).join("\n") + '</pre>';
  }
  const img = data.images;
  html += '<p>Images — missing (new cards): <b>' + img.missing_new.length
    + '</b>, case mismatches: <b>' + img.case_mismatch.length
    + '</b>, orphaned: ' + img.orphaned.length + '</p>';
  if (img.missing_new.length)
    html += '<pre class="warn">Missing for new cards:\n' + img.missing_new.join("\n") + '</pre>';
  if (img.case_mismatch.length)
    html += '<pre class="warn">Case mismatches:\n' + img.case_mismatch.join("\n") + '</pre>';
  el.innerHTML = html;
  enableApply(true);
}
function enableApply(ok) {
  document.getElementById("applybtn").disabled = !ok;
  document.getElementById("ackwarn").onchange = null;
}
async function apply() {
  const data = await api("/api/apply", payload());
  if (data.ok) {
    document.getElementById("review").classList.add("hidden");
    document.getElementById("done").classList.remove("hidden");
  } else {
    alert("Could not apply: " + data.error);
  }
}
function escapeHtml(s) {
  return s.replace(/[&<>]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
}
(async function init() {
  const cur = await api("/api/current", {});
  document.getElementById("current").textContent = cur.version;
  setVersion(cur.suggested);
  const now = new Date();
  const yy = String(now.getFullYear()).slice(2);
  const mm = String(now.getMonth() + 1).padStart(2, "0");
  const dd = String(now.getDate()).padStart(2, "0");
  document.getElementById("yymmdd").value = yy + mm + dd;
})();
</script>
</body>
</html>
```

- [ ] **Step 2: Manual smoke test**

Run: `cd /Users/timestes/projects/lackey && python3 -m tools.updater.server` (it prints a URL and opens the browser).

In the browser, verify:
1. Current version shows `2.3.1`; new version prefilled `2.3.2`; date prefilled to today's YYMMDD.
2. Paste a single valid new row, click **Preview** → see `1 ADD`, image "missing (new)" likely `1` (no image dropped in yet).
3. Paste a malformed row (e.g. `a\tb\tc`), Preview → red "Cannot apply" with a column-count error; Apply disabled.
4. Do **not** click Apply during the smoke test (it writes the live files). Stop the server with Ctrl+C.

Confirm `git status` shows no modified `RedemptionQuick/` files after the smoke test.

- [ ] **Step 3: Commit**

```bash
cd /Users/timestes/projects/lackey
git add tools/updater/index.html
git commit -m "feat(updater): single-page wizard GUI"
```

---

## Task 12: Launchers + maintainer README

**Files:**
- Create: `tools/updater/Start Update Tool.command`
- Create: `tools/updater/Start Update Tool.bat`
- Create: `tools/updater/README-for-maintainers.txt`

- [ ] **Step 1: Create the macOS launcher**

Create `tools/updater/Start Update Tool.command`:

```bash
#!/bin/bash
# Double-click to launch the Redemption Update Tool.
cd "$(dirname "$0")/../.." || exit 1
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is not installed. Please install it from https://www.python.org/downloads/"
  read -r -p "Press Enter to close."
  exit 1
fi
python3 -m tools.updater.server
```

- [ ] **Step 2: Make it executable**

Run: `chmod +x "tools/updater/Start Update Tool.command"`

- [ ] **Step 3: Create the Windows launcher**

Create `tools/updater/Start Update Tool.bat`:

```bat
@echo off
REM Double-click to launch the Redemption Update Tool.
cd /d "%~dp0\..\.."
where python >nul 2>nul
if errorlevel 1 (
  echo Python 3 is not installed. Please install it from https://www.python.org/downloads/
  pause
  exit /b 1
)
python -m tools.updater.server
pause
```

- [ ] **Step 4: Create the maintainer README**

Create `tools/updater/README-for-maintainers.txt`:

```
Redemption Plugin Update Tool
=============================

WHAT IT DOES
  Adds new cards and bumps the plugin version for a release. You paste card
  rows from Excel; the tool validates them, merges them into carddata.txt,
  recomputes all checksums, rewrites updatelist.txt, and updates the version
  files. It then stops. It NEVER commits to git — you review and commit
  yourself, exactly as before.

HOW TO RUN
  macOS:    double-click "Start Update Tool.command"
  Windows:  double-click "Start Update Tool.bat"
  Either way it opens http://127.0.0.1:8765 in your browser.
  (If it says Python is missing, install Python 3 from python.org and retry.)

STEPS
  1. Drop any new card images (.jpg) into
     RedemptionQuick/sets/setimages/general/  first.
  2. In the tool: paste the card rows (16 columns, NO header row).
  3. Set the new version number and a short message.
  4. Click "Preview changes" and read the summary. Fix any red errors.
  5. Click "Apply". The files are written.
  6. In your git tool, review the diff, then commit and push.

NOTES
  - Match key is (Name, Set). A row whose Name+Set already exists updates that
    card; otherwise it is added at the end.
  - "Missing (new cards)" images means you added a card but its .jpg isn't in
    the general/ folder yet. Add it and re-preview.
  - The tool changes only carddata.txt, updatelist.txt, version.txt, and
    plugininfo.txt. Anything else (new packs, decks, setlist) stays manual.
```

- [ ] **Step 5: Run the full test suite one last time**

Run: `cd /Users/timestes/projects/lackey && python3 -m unittest discover -s tools/updater/tests -v`
Expected: PASS (every test)

- [ ] **Step 6: Commit**

```bash
cd /Users/timestes/projects/lackey
git add "tools/updater/Start Update Tool.command" "tools/updater/Start Update Tool.bat" tools/updater/README-for-maintainers.txt
git commit -m "feat(updater): launchers and maintainer README"
```

---

## Self-Review (completed during planning)

**Spec coverage:**
- §2 Tech stack (Python stdlib, no deps) → Tasks 1–12 use only stdlib. ✓
- §3 Architecture (pure modules + thin HTTP + preview/apply) → Tasks 1–10. ✓
- §4 carddata merge ((Name,Set) key, append at end, byte-exact, validation) → Tasks 3–4. ✓
- §5 updatelist (verbatim header/trailer, in-place checksums, missing→error) → Task 5. ✓
- §5 checksum verbatim (load-bearing EOF branch, golden values) → Task 2. ✓
- §6 version bump (date+message+pluginversion, downgrade guard, literal replace) → Task 6. ✓
- §7 images (.jpg resolution, case-sensitive, missing/orphan/case) → Task 7. ✓
- §8 UI flow (paste→version→review→done, errors block, warnings ack) → Task 11. ✓
- §9 safety (validate-before-write, atomic, compute-then-write, post-write self-verify, 127.0.0.1) → Tasks 8, 9, 10. ✓
- §10 testing (golden, round-trip, merge, updatelist, version, images, e2e) → Tasks 2–9. ✓
- §11 deferred items (rename, new-manifest) → not implemented by design; warnings surfaced via vocab/missing reports. ✓

**Decisions honored:** git-only safety (no .bak module anywhere) ✓; append new rows at end (Task 4) ✓; rename + new-manifest deferred to warnings ✓.

**Placeholder scan:** Task 10 Step 4 creates a deliberately minimal index.html, fully replaced in Task 11 — this is sequenced, not a placeholder. No TODO/TBD left.

**Type/name consistency:** `Repo` fields (`carddata`, `updatelist`, `version`, `plugininfo`, `images_dir`, `redemption`) used identically in Task 9 impl and Task 9 tests; `pipeline.preview/apply` signatures match the server calls in Task 10; `carddata.parse_and_validate(text, existing_keys, known_values)` and `merge(header, data_lines, report)` consistent across Tasks 3, 4, 9; `images.referenced_filenames(rows)` / `validate(referenced, available)` consistent across Tasks 7, 9; `checksum.checksum`/`checksum_bytes` consistent across Tasks 2, 5, 9. ✓
