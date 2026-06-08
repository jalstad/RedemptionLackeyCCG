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
