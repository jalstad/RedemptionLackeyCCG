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
                f"Row has {len(parts)} columns, expected 16 columns — Excel may have "
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
