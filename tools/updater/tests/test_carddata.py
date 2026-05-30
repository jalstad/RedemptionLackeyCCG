import unittest

from tools.updater import carddata


HEADER = "\t".join(carddata.COLUMNS)


def row(**kw):
    """Build a 16-field TSV line; unspecified columns are empty."""
    return "\t".join(kw.get(c, "") for c in carddata.COLUMNS)


class TestSplitPaste(unittest.TestCase):
    def test_strips_bom_and_cr_and_blank_trailing_lines(self):
        text = "﻿a\tb\r\nc\td\r\n\n"
        self.assertEqual(carddata.split_paste(text), ["a\tb", "c\td"])

    def test_embedded_cr_is_kept_for_validation(self):
        # a lone CR not at line end stays in the line so validation can reject it
        self.assertEqual(carddata.split_paste("a\rb"), ["a\rb"])


class TestParseValidate(unittest.TestCase):
    def setUp(self):
        self.existing = {("Adam", "Pat")}
        self.known = {"Alignment": {"Good", "Evil"}, "Brigade": {"Red"}}

    def parse(self, lines):
        return carddata.parse_and_validate(
            "\n".join(lines), existing_keys=self.existing, known_values=self.known)

    def test_new_key_is_add(self):
        rep = self.parse([row(Name="Eve", Set="Pat", ImageFile="Eve",
                              OfficialSet="Patriarchs", Type="Hero", Alignment="Good")])
        self.assertEqual(rep.rows[0].action, "ADD")
        self.assertEqual(rep.rows[0].errors, [])
        self.assertTrue(rep.ok)

    def test_existing_key_is_update(self):
        rep = self.parse([row(Name="Adam", Set="Pat", ImageFile="Adam",
                              OfficialSet="Patriarchs", Type="Hero", Alignment="Good")])
        self.assertEqual(rep.rows[0].action, "UPDATE")

    def test_wrong_column_count_is_error(self):
        rep = self.parse(["Eve\tPat\tEve"])  # 3 cols
        self.assertEqual(rep.rows[0].action, "ERROR")
        self.assertIn("16 columns", rep.rows[0].errors[0])
        self.assertFalse(rep.ok)

    def test_missing_required_field_is_error(self):
        rep = self.parse([row(Name="", Set="Pat", ImageFile="x",
                              OfficialSet="Patriarchs", Type="Hero", Alignment="Good")])
        self.assertEqual(rep.rows[0].action, "ERROR")
        self.assertFalse(rep.ok)

    def test_embedded_tab_or_newline_in_field_is_error(self):
        # 17 fields because a value itself contained a tab
        bad = row(Name="E\tve", Set="Pat", ImageFile="x",
                  OfficialSet="Patriarchs", Type="Hero", Alignment="Good")
        rep = self.parse([bad])
        self.assertEqual(rep.rows[0].action, "ERROR")

    def test_duplicate_key_in_paste_is_error(self):
        r = row(Name="Eve", Set="Pat", ImageFile="Eve",
                OfficialSet="Patriarchs", Type="Hero", Alignment="Good")
        rep = self.parse([r, r])
        self.assertTrue(any("duplicate" in e.lower()
                            for e in rep.rows[1].errors))
        self.assertFalse(rep.ok)

    def test_unknown_vocab_value_is_warning_not_error(self):
        rep = self.parse([row(Name="Eve", Set="Pat", ImageFile="Eve",
                              OfficialSet="Patriarchs", Type="Hero",
                              Brigade="Pruple", Alignment="Good")])
        self.assertEqual(rep.rows[0].action, "ADD")
        self.assertEqual(rep.rows[0].errors, [])
        self.assertTrue(any("Brigade" in w for w in rep.rows[0].warnings))

    def test_whitespace_in_key_is_warning(self):
        rep = self.parse([row(Name=" Eve ", Set="Pat", ImageFile="Eve",
                              OfficialSet="Patriarchs", Type="Hero", Alignment="Good")])
        self.assertTrue(any("whitespace" in w.lower() for w in rep.rows[0].warnings))


class TestKnownValues(unittest.TestCase):
    def test_collects_distinct_column_values(self):
        data_lines = [
            row(Name="Adam", Set="Pat", Brigade="Red", Alignment="Good"),
            row(Name="Cain", Set="Pat", Brigade="Black", Alignment="Evil"),
        ]
        known = carddata.collect_known_values(data_lines)
        self.assertEqual(known["Brigade"], {"Red", "Black"})
        self.assertEqual(known["Alignment"], {"Good", "Evil"})

    def test_existing_keys(self):
        data_lines = [row(Name="Adam", Set="Pat"), ""]  # blank line ignored
        self.assertEqual(carddata.existing_keys(data_lines), {("Adam", "Pat")})
