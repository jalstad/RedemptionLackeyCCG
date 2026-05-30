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
