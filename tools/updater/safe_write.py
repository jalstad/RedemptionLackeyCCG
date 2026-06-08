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
