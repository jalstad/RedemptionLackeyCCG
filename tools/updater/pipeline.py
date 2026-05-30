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
    expected_header = "\t".join(carddata.COLUMNS)
    if header != expected_header:
        raise ValidationError(
            "carddata.txt header does not match the expected 16 columns — "
            "the file may be corrupt. Aborting to avoid writing bad data.")
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
