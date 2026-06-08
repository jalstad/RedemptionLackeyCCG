import io
import math
import os
import unittest

from tools.updater import checksum, paths


# A literal copy of the canonical reference, used as the oracle.
def _reference(data: bytes) -> int:
    value = 0
    fp = io.BufferedReader(io.BytesIO(data))
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


class TestChecksum(unittest.TestCase):
    def test_golden_live_values(self):
        # Verified against updatelist.txt on 2026-05-30.
        self.assertEqual(checksum.checksum(paths.VERSION), 31658)
        self.assertEqual(checksum.checksum(paths.PLUGININFO), 384808)
        self.assertEqual(checksum.checksum(paths.SETLIST), 50843)
        self.assertEqual(checksum.checksum(paths.CARDDATA), 3927115)

    def test_bytes_matches_file(self):
        data = paths.VERSION.read_bytes()
        self.assertEqual(checksum.checksum_bytes(data), 31658)
        self.assertEqual(checksum.checksum_bytes(data), checksum.checksum(paths.VERSION))

    def test_empty_input_is_zero(self):
        self.assertEqual(checksum.checksum_bytes(b""), 0)

    def test_eof_decrement_is_load_bearing(self):
        # The final empty read fires `value -= 1` exactly once.
        # "A" = 65; result must be 65 - 1 = 64, NOT 65.
        self.assertEqual(checksum.checksum_bytes(b"A"), 64)

    def test_high_bytes_are_signed(self):
        # 0x80 = -128 signed; plus the EOF -1.
        self.assertEqual(checksum.checksum_bytes(b"\x80"), -129)

    def test_newlines_skipped(self):
        self.assertEqual(checksum.checksum_bytes(b"A\r\nB"),
                         checksum.checksum_bytes(b"AB"))

    def test_matches_reference_on_fuzz(self):
        rng = [b"", b"A", b"\x80\x7f", b"hi\nthere\r\n", b"\xff" * 50,
               bytes(range(256)), "smart'quote–dash".encode("utf-8")]
        for data in rng:
            self.assertEqual(checksum.checksum_bytes(data), _reference(data), data)
