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
