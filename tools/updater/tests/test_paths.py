import unittest
from tools.updater import paths


class TestPaths(unittest.TestCase):
    def test_repo_root_contains_redemptionquick(self):
        self.assertTrue((paths.ROOT / "RedemptionQuick").is_dir())

    def test_known_files_exist(self):
        for p in (paths.CARDDATA, paths.UPDATELIST, paths.VERSION,
                  paths.PLUGININFO, paths.SETLIST):
            self.assertTrue(p.is_file(), f"missing {p}")
        self.assertTrue(paths.IMAGES_DIR.is_dir())

    def test_url_prefix(self):
        self.assertEqual(
            paths.URL_PREFIX,
            "https://jalstad.github.io/RedemptionLackeyCCG/RedemptionQuick/",
        )
        self.assertEqual(paths.MANIFEST_PATH_PREFIX, "plugins/Redemption/")
