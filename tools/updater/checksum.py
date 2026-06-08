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
