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
