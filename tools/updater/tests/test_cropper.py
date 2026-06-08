import io
import unittest

from tools.updater import cropper, paths

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


def _png_bytes(w, h, color=(10, 20, 30)):
    im = Image.new("RGB", (w, h), color)
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


class TestOutputName(unittest.TestCase):
    def test_strips_extension_and_commas_adds_jpg(self):
        self.assertEqual(cropper.output_name("Abram, Abraham (Pa).png"),
                         "Abram Abraham (Pa).jpg")

    def test_already_named_base(self):
        self.assertEqual(cropper.output_name("001-Adam.tiff"), "001-Adam.jpg")

    def test_strips_directory(self):
        self.assertEqual(cropper.output_name("/some/dir/Eve.PNG"), "Eve.jpg")

    def test_empty_name_raises(self):
        with self.assertRaises(cropper.CropError):
            cropper.output_name("")


class TestPresets(unittest.TestCase):
    def test_presets_shape(self):
        self.assertIn("printer2", cropper.PRESETS)
        self.assertIn("printer1", cropper.PRESETS)
        self.assertIn("pack", cropper.PRESETS)
        self.assertEqual(cropper.DEFAULT_PRESET, "printer2")
        for cfg in cropper.PRESETS.values():
            self.assertEqual(len(cfg["box"]), 4)
            self.assertEqual(len(cfg["size"]), 2)

    def test_unknown_preset_raises(self):
        with self.assertRaises(cropper.CropError):
            cropper.crop_image_bytes(b"x", preset="nope")


@unittest.skipUnless(HAS_PIL, "Pillow not installed")
class TestCrop(unittest.TestCase):
    def test_printer2_outputs_345x495_jpeg(self):
        data = _png_bytes(816, 1110)  # big enough for the (46,43,769,1082) box
        out = cropper.crop_image_bytes(data, "printer2")
        im = Image.open(io.BytesIO(out))
        self.assertEqual(im.size, (345, 495))
        self.assertEqual(im.format, "JPEG")

    def test_printer1_outputs_345x495_jpeg(self):
        out = cropper.crop_image_bytes(_png_bytes(816, 1110), "printer1")
        im = Image.open(io.BytesIO(out))
        self.assertEqual(im.size, (345, 495))
        self.assertEqual(im.format, "JPEG")

    def test_pack_outputs_207x300(self):
        out = cropper.crop_image_bytes(_png_bytes(816, 1110), "pack")
        self.assertEqual(Image.open(io.BytesIO(out)).size, (207, 300))

    def test_too_small_image_raises_croperror(self):
        with self.assertRaises(cropper.CropError):
            cropper.crop_image_bytes(_png_bytes(100, 100), "printer2")

    def test_unreadable_bytes_raise_croperror(self):
        with self.assertRaises(cropper.CropError):
            cropper.crop_image_bytes(b"not an image", "printer2")


class TestNameMatching(unittest.TestCase):
    def test_card_image_names_includes_existing_and_pasted(self):
        # Pull a real existing ImageFile from the live carddata to assert membership.
        _, data = carddata_lines()
        first = data[0].split("\t")[2]
        from tools.updater import images
        expected = images.resolve(first)
        new_row = "\t".join(["New Card", "ZZZ", "zzz-new-card", "Test", "Hero",
                             "", "", "", "", "", "x", "Common", "", "", "Good", ""])
        names = cropper.card_image_names(paths.CARDDATA, pasted_text=new_row)
        self.assertIn(expected, names)
        self.assertIn("zzz-new-card.jpg", names)

    def test_unmatched_names(self):
        valid = {"a.jpg", "b.jpg"}
        cropped = ["a.jpg", "typo.jpg", "b.jpg"]
        self.assertEqual(cropper.unmatched_names(cropped, valid), ["typo.jpg"])


def carddata_lines():
    from tools.updater import carddata
    return carddata.read_carddata(paths.CARDDATA)


if __name__ == "__main__":
    unittest.main()
