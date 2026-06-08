import unittest

from tools.updater import version_bump as vb, paths


class TestVersionBump(unittest.TestCase):
    def test_read_current_version(self):
        info = paths.PLUGININFO.read_text(encoding="utf-8")
        self.assertEqual(vb.read_current_version(info), "2.3.1")

    def test_bump_patch_minor_major(self):
        self.assertEqual(vb.bump("2.3.1", "patch"), "2.3.2")
        self.assertEqual(vb.bump("2.3.1", "minor"), "2.4.0")
        self.assertEqual(vb.bump("2.3.1", "major"), "3.0.0")

    def test_build_message(self):
        self.assertEqual(
            vb.build_message("2.3.2", "Added Foo set"),
            "Redemption Plugin Version 2.3.2: Added Foo set")

    def test_bump_plugininfo_changes_only_pluginversion(self):
        info = paths.PLUGININFO.read_text(encoding="utf-8")
        out = vb.bump_plugininfo(info, "2.3.2")
        self.assertIn("<pluginversion>2.3.2</pluginversion>", out)
        self.assertEqual(out.replace("2.3.2", "2.3.1"), info)  # nothing else moved

    def test_bump_version_txt_changes_only_date_and_message(self):
        ver = paths.VERSION.read_text(encoding="utf-8")
        out = vb.bump_version_txt(ver, yymmdd="260530",
                                  message="Redemption Plugin Version 2.3.2: x")
        self.assertIn("<lastupdateYYMMDD>260530</lastupdateYYMMDD>", out)
        self.assertIn("<message>Redemption Plugin Version 2.3.2: x</message>", out)
        # URLs and wrapper untouched
        self.assertIn("<versionurl>https://jalstad.github.io", out)
        self.assertTrue(out.startswith("<version>"))

    def test_message_with_special_regex_chars_is_literal(self):
        ver = paths.VERSION.read_text(encoding="utf-8")
        out = vb.bump_version_txt(ver, yymmdd="260530",
                                  message=r"fix \1 and 100% of $items")
        self.assertIn(r"<message>fix \1 and 100% of $items</message>", out)

    def test_is_newer(self):
        self.assertTrue(vb.is_newer("2.3.2", "2.3.1"))
        self.assertTrue(vb.is_newer("2.4.0", "2.3.9"))
        self.assertFalse(vb.is_newer("2.3.1", "2.3.1"))
        self.assertFalse(vb.is_newer("2.3.0", "2.3.1"))
