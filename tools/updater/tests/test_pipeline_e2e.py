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

    def test_corrupt_header_aborts(self):
        # Corrupt the sandbox carddata header; apply/preview must refuse.
        cd = self.repo.carddata
        text = cd.read_text(encoding="utf-8")
        lines = text.split("\n")
        lines[0] = "BOGUS\tHEADER"
        cd.write_text("\n".join(lines), encoding="utf-8")
        with self.assertRaises(pipeline.ValidationError):
            pipeline.apply(self.repo, "", version="2.3.2",
                           yymmdd="260530", message="x")

    def test_check_image_names_flags_unmatched(self):
        # A name that matches an existing card vs one that matches nothing.
        _, data = carddata.read_carddata(self.repo.carddata)
        from tools.updater import images
        existing = images.resolve(data[0].split("\t")[2])
        result = pipeline.check_image_names(
            self.repo, names=[existing, "totally-bogus.jpg"], pasted_text="")
        self.assertEqual(result["unmatched"], ["totally-bogus.jpg"])

    def test_check_image_names_honours_pasted_rows(self):
        # An image for a brand-new pasted card should NOT be flagged.
        result = pipeline.check_image_names(
            self.repo, names=["zzz-test.jpg"], pasted_text=self._new_card_row())
        self.assertEqual(result["unmatched"], [])


class TestRealSetReplay(unittest.TestCase):
    """End-to-end realism check: take the most recently added set off the LIVE
    carddata, then re-add those exact rows through the tool and prove it
    reproduces the real carddata.txt byte-for-byte with the real checksum. This
    replays an actual historical release and is the strongest correctness signal
    we have — if the merge, encoding, ordering, or checksum ever drift, it fails.
    """

    def _trailing_16col_block(self, data):
        """The longest suffix of consecutive 16-column rows (re-addable rows that
        sit at the end of the file). Skips over the known 30-column anomaly rows
        if they happen to be at the tail."""
        block = []
        for line in reversed(data):
            if line and len(line.split("\t")) == carddata.N_COLUMNS:
                block.append(line)
            else:
                break
        block.reverse()
        return block

    def test_readding_trailing_set_reproduces_live_carddata(self):
        from tools.updater import images
        header, data = carddata.read_carddata(paths.CARDDATA)
        block = self._trailing_16col_block(data)
        self.assertGreater(len(block), 0, "no re-addable trailing rows found")
        before = data[:len(data) - len(block)]

        tmp = tempfile.mkdtemp()
        repo = RepoFixture(tmp).repo
        # Roll carddata back to the pre-set state (no trailing newline, as live).
        repo.carddata.write_text("\n".join([header] + before), encoding="utf-8")

        # Re-add the exact set rows through the tool.
        pipeline.apply(repo, "\n".join(block), version="2.3.2",
                       yymmdd="260530", message="Redemption Plugin Version 2.3.2: replay")

        # carddata.txt must be byte-identical to the live file...
        self.assertEqual(repo.carddata.read_bytes(), paths.CARDDATA.read_bytes())
        # ...and the recomputed checksum must equal the live file's checksum...
        live_cs = checksum.checksum(paths.CARDDATA)
        self.assertEqual(checksum.checksum(repo.carddata), live_cs)
        # ...and the manifest must record that same checksum.
        ul = repo.updatelist.read_text(encoding="utf-8")
        cs_row = [l for l in ul.split("\n") if "sets/carddata.txt" in l][0]
        self.assertEqual(int(cs_row.split("\t")[2]), live_cs)

        # The set's images are recognized (none flagged as unmatched).
        names = [images.resolve(l.split("\t")[2]) for l in block]
        chk = pipeline.check_image_names(repo, names=names, pasted_text="\n".join(block))
        self.assertEqual(chk["unmatched"], [])


@unittest.skipUnless(
    __import__("importlib").util.find_spec("PIL") is not None,
    "Pillow not installed")
class TestCropAndSave(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.repo = RepoFixture(self.tmp).repo

    def _png(self, w, h):
        import io
        from PIL import Image
        buf = io.BytesIO()
        Image.new("RGB", (w, h), (1, 2, 3)).save(buf, "PNG")
        return buf.getvalue()

    def test_crop_and_save_writes_normalized_jpg(self):
        out = pipeline.crop_and_save(
            self.repo, filename="Abram, Abraham (Pa).png",
            preset="printer2", data=self._png(816, 1110))
        self.assertEqual(out, "Abram Abraham (Pa).jpg")
        saved = self.repo.images_dir / out
        self.assertTrue(saved.is_file())
        from PIL import Image
        with Image.open(saved) as im:
            self.assertEqual(im.size, (345, 495))

    def test_crop_and_save_bad_image_raises(self):
        with self.assertRaises(pipeline.cropper.CropError):
            pipeline.crop_and_save(self.repo, filename="x.png",
                                   preset="printer2", data=b"nope")
