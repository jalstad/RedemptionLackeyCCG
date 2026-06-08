"""Crop and resize raw card scans to the plugin's image format.

This is the ONLY module that needs the third-party Pillow library. Pillow is
imported lazily (inside the functions that use it) so the rest of the tool —
the card-data/checksum/updatelist release flow — keeps running on the standard
library alone even when Pillow is not installed.

Crop presets come from the maintainer's existing crop script:
- printer2: regular print runs (less white bleed)   -> 345x495 card
- printer1: foils/promos/small runs (more bleed)     -> 345x495 card
- pack:     pack/set thumbnail image                 -> 207x300
"""
import io
import os

from . import images, carddata

# preset -> (crop box (left, upper, right, lower), output (w, h), human label)
PRESETS = {
    "printer2": {"box": (46, 43, 769, 1082), "size": (345, 495),
                 "label": "Printer 2 (regular runs)"},
    "printer1": {"box": (63, 60, 762, 1065), "size": (345, 495),
                 "label": "Printer 1 (foils / promos / small runs)"},
    "pack": {"box": (46, 43, 769, 1082), "size": (207, 300),
             "label": "Pack image"},
}
DEFAULT_PRESET = "printer2"


class PillowMissing(Exception):
    """Raised when a crop is attempted but Pillow is not installed."""


class CropError(Exception):
    """Raised when an image cannot be cropped (bad data, too small, etc.)."""


def _require_pillow():
    try:
        from PIL import Image
        return Image
    except ImportError as e:  # pragma: no cover - depends on environment
        raise PillowMissing(
            "Pillow is not installed, so images can't be cropped. Install it by "
            "running this in a terminal in the project folder:  "
            "python -m pip install Pillow   (on Windows, try 'py -m pip install "
            "Pillow' if 'python' isn't found). Then close this tool's window and "
            "start it again.") from e


def output_name(source_filename):
    """The on-disk filename a cropped image is saved under: the source name with
    its extension dropped and commas removed, plus a .jpg extension.

    Commas are stripped to match the maintainer's original crop script and the
    plugin's image-naming convention (card image filenames never contain commas,
    even though card *names* like "Abram, Abraham" do). os.path.basename also
    neutralizes any directory components in the supplied name.
    """
    base = os.path.splitext(os.path.basename(source_filename))[0].replace(",", "")
    if not base:
        raise CropError(f"Cannot derive an output filename from {source_filename!r}")
    return base + ".jpg"


def crop_image_bytes(data, preset=DEFAULT_PRESET):
    """Crop and resize raw image bytes per the named preset; return JPEG bytes.

    Raises PillowMissing if Pillow is unavailable, CropError if the bytes are not
    a readable image or are smaller than the preset's crop box.
    """
    if preset not in PRESETS:
        raise CropError(f"Unknown crop preset: {preset!r}")
    Image = _require_pillow()
    cfg = PRESETS[preset]
    try:
        im = Image.open(io.BytesIO(data))
        im = im.convert("RGB")
    except Exception as e:
        raise CropError(f"Could not read image: {e}") from e
    left, upper, right, lower = cfg["box"]
    if im.width < right or im.height < lower:
        raise CropError(
            f"Image is {im.width}x{im.height}, too small for the "
            f"{cfg['label']} crop box (needs at least {right}x{lower}). "
            f"Is this the right preset / a full-resolution scan?")
    out = io.BytesIO()
    # quality=100: preserve full scan fidelity — these images are distributed
    # with the plugin and re-compressing them lossily would degrade card art.
    im.crop(cfg["box"]).resize(cfg["size"], Image.LANCZOS).save(
        out, "JPEG", quality=100)
    return out.getvalue()


def card_image_names(carddata_path, pasted_text=""):
    """The set of expected image filenames for all known cards: every existing
    card's ImageFile plus any ImageFile in pasted new/edited rows, each resolved
    to its on-disk .jpg name. Used to flag cropped images that match no card."""
    _, data_lines = carddata.read_carddata(carddata_path)
    names = {images.resolve(line.split("\t")[carddata.COLUMNS.index("ImageFile")])
             for line in data_lines
             if line and len(line.split("\t")) > carddata.COLUMNS.index("ImageFile")}
    for raw in carddata.split_paste(pasted_text):
        parts = raw.split("\t")
        if len(parts) == carddata.N_COLUMNS:
            names.add(images.resolve(parts[carddata.COLUMNS.index("ImageFile")]))
    return names


def unmatched_names(cropped_names, valid_names):
    """Cropped output filenames that match no known card image name."""
    return sorted(set(cropped_names) - set(valid_names))
