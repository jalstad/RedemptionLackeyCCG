import unittest

from tools.updater import images


class TestResolve(unittest.TestCase):
    def test_appends_jpg_when_absent(self):
        self.assertEqual(images.resolve("A_Look_Back_(Wo)"), "A_Look_Back_(Wo).jpg")

    def test_keeps_existing_jpg(self):
        self.assertEqual(images.resolve("139-Abeyance.jpg"), "139-Abeyance.jpg")

    def test_existing_jpg_case_insensitive_suffix(self):
        self.assertEqual(images.resolve("X.JPG"), "X.JPG")


class TestValidate(unittest.TestCase):
    def test_missing_orphan_and_case(self):
        referenced = {"a.jpg", "b.jpg", "Babylon.jpg"}
        available = {"a.jpg", "c.jpg", "babylon.jpg"}
        rep = images.validate(referenced, available)
        self.assertEqual(rep["missing"], ["b.jpg"])
        self.assertEqual(rep["orphaned"], ["c.jpg"])
        self.assertEqual(rep["case_mismatch"], ["Babylon.jpg"])

    def test_referenced_from_rows(self):
        # rows are field-lists (index 2 == ImageFile)
        from tools.updater import carddata
        rows = [
            ["Eve", "Pat", "Eve", "Patriarchs", "Hero", "", "", "", "", "",
             "", "", "", "", "Good", ""],
            ["Cain", "Pat", "139-Abeyance.jpg", "Patriarchs", "Hero", "", "",
             "", "", "", "", "", "", "", "Evil", ""],
        ]
        refs = images.referenced_filenames(rows)
        self.assertEqual(refs, {"Eve.jpg", "139-Abeyance.jpg"})
