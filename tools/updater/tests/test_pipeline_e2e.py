import shutil
import tempfile
import unittest
from pathlib import Path

from tools.updater import pipeline, paths, checksum, carddata


class RepoFixture:
    """A throwaway copy of the four metadata files + a tiny image dir."""
    def __init__(self, root):
        self.root = Path(root)
        red = self.root / "RedemptionQuick"
        (red / "sets" / "setimages" / "general").mkdir(parents=True)
        # Copy every file the manifest references, preserving relative paths,
        # so updatelist.rebuild and the post-write self-verify can checksum them.
        from tools.updater import updatelist
        manifest_text = paths.UPDATELIST.read_text(encoding="utf-8")
        for rel in updatelist.manifest_rels(manifest_text):
            src = paths.REDEMPTION / rel
            dst = red / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(src, dst)
        # updatelist.txt is not in the manifest itself but must exist in the sandbox.
        shutil.copy(paths.UPDATELIST, red / "updatelist.txt")
        self.repo = pipeline.Repo(red)


class TestPipeline(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.fix = RepoFixture(self.tmp)
        self.repo = self.fix.repo

    def _new_card_row(self):
        return "\t".join([
            "Zzz Test Card", "ZZZ", "zzz-test", "Test Set", "Hero",
            "", "", "", "", "", "Does nothing.", "Common", "", "", "Good", ""])

    def test_preview_writes_nothing(self):
        before = self.repo.carddata.read_bytes()
        result = pipeline.preview(self.repo, self._new_card_row(),
                                  version="2.3.2", yymmdd="260530",
                                  message="Redemption Plugin Version 2.3.2: test")
        self.assertTrue(result["ok"])
        self.assertEqual(result["counts"]["add"], 1)
        self.assertEqual(self.repo.carddata.read_bytes(), before)  # unchanged

    def test_apply_writes_correct_checksums(self):
        pipeline.apply(self.repo, self._new_card_row(),
                       version="2.3.2", yymmdd="260530",
                       message="Redemption Plugin Version 2.3.2: test")
        # The new card is appended
        text = self.repo.carddata.read_text(encoding="utf-8")
        self.assertTrue(text.rstrip("\n").endswith("Good\t"))
        self.assertFalse(text.endswith("\n"))
        # updatelist's carddata checksum matches the file actually on disk
        ul = self.repo.updatelist.read_text(encoding="utf-8")
        cs_line = [l for l in ul.split("\n") if "sets/carddata.txt" in l][0]
        recorded = int(cs_line.split("\t")[2])
        self.assertEqual(recorded, checksum.checksum(self.repo.carddata))
        # version + plugininfo bumped
        self.assertIn("<pluginversion>2.3.2</pluginversion>",
                      self.repo.plugininfo.read_text(encoding="utf-8"))
        self.assertIn("<lastupdateYYMMDD>260530</lastupdateYYMMDD>",
                      self.repo.version.read_text(encoding="utf-8"))

    def test_apply_refuses_on_error(self):
        with self.assertRaises(pipeline.ValidationError):
            pipeline.apply(self.repo, "too\tfew\tcols",
                           version="2.3.2", yymmdd="260530", message="x")

    def test_apply_refuses_downgrade(self):
        with self.assertRaises(pipeline.ValidationError):
            pipeline.apply(self.repo, "", version="2.3.1",
                           yymmdd="260530", message="x")

    def test_empty_paste_version_only_keeps_carddata_identical(self):
        before = self.repo.carddata.read_bytes()
        pipeline.apply(self.repo, "", version="2.3.2",
                       yymmdd="260530", message="Redemption Plugin Version 2.3.2: x")
        self.assertEqual(self.repo.carddata.read_bytes(), before)
