import unittest

from tools.updater import updatelist, checksum, paths


class TestUpdatelist(unittest.TestCase):
    def test_rebuild_unchanged_is_byte_identical(self):
        text = paths.UPDATELIST.read_text(encoding="utf-8")

        def real_checksum(rel):
            return checksum.checksum(paths.REDEMPTION / rel)

        rebuilt = updatelist.rebuild(text, real_checksum)
        self.assertEqual(rebuilt, text)

    def test_header_and_trailer_preserved(self):
        text = paths.UPDATELIST.read_text(encoding="utf-8")
        rebuilt = updatelist.rebuild(text, lambda rel: 0)
        lines = rebuilt.split("\n")
        self.assertEqual(lines[0], "Redemption\t05-28-16")
        self.assertIn("CardGeneralURLs:", rebuilt)
        self.assertTrue(rebuilt.rstrip("\n").endswith(
            "/RedemptionQuick/sets/setimages/general/"))

    def test_only_checksum_field_changes(self):
        text = paths.UPDATELIST.read_text(encoding="utf-8")
        rebuilt = updatelist.rebuild(text, lambda rel: 42)
        # carddata row's checksum becomes 42; path and URL unchanged
        line = [l for l in rebuilt.split("\n") if "sets/carddata.txt" in l][0]
        path, url, cs = line.split("\t")
        self.assertEqual(path, "plugins/Redemption/sets/carddata.txt")
        self.assertEqual(cs, "42")

    def test_missing_file_raises(self):
        text = ("Redemption\t05-28-16\n"
                "plugins/Redemption/nope.txt\thttp://x/nope.txt\t1\n"
                "CardGeneralURLs:\nhttp://x/\n")

        def boom(rel):
            raise FileNotFoundError(rel)

        with self.assertRaises(updatelist.ManifestError):
            updatelist.rebuild(text, boom)

    def test_paths_to_rechecksum(self):
        text = paths.UPDATELIST.read_text(encoding="utf-8")
        rels = updatelist.manifest_rels(text)
        self.assertIn("sets/carddata.txt", rels)
        self.assertIn("version.txt", rels)
        self.assertNotIn("", rels)
