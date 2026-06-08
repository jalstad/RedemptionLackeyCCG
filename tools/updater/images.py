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
    ref_lower = {r.lower() for r in referenced}
    missing_all = referenced - available
    case_mismatch = sorted(f for f in missing_all if f.lower() in avail_lower)
    missing = sorted(f for f in missing_all if f.lower() not in avail_lower)
    orphaned = sorted(f for f in available - referenced if f.lower() not in ref_lower)
    return {"missing": missing, "orphaned": orphaned, "case_mismatch": case_mismatch}
