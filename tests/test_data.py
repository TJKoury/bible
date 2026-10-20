import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from download_data import parse_vrs, book_id

DATA = ROOT / "public/data"


class SourceSemanticsTests(unittest.TestCase):
    def test_many_to_one_headings_are_preserved(self):
        result = parse_vrs("PSA 51:0 = PSA 51:1\nPSA 51:0 = PSA 51:2\nPSA 51:1-19 = PSA 51:3-21")
        self.assertEqual(result["19.51.0"], ["19.51.1", "19.51.2"])
        self.assertEqual(result["19.51.1"], ["19.51.3"])
        self.assertEqual(result["19.51.19"], ["19.51.21"])

    def test_cross_chapter_and_hebrew_numbering(self):
        mapping = json.loads((DATA / "verse-map.json").read_text())
        self.assertEqual(mapping["1.31.55"], ["1.32.1"])
        self.assertEqual(mapping["19.51.1"], ["19.51.3"])
        words = json.loads((DATA / "original/19/51.json").read_text())["3"]
        self.assertEqual(words[0]["strong"], "H2603")  # חנן, the plea for favor

    def test_original_languages_are_real_word_data(self):
        john = json.loads((DATA / "original/43/1.json").read_text())["1"]
        self.assertEqual(john[0]["text"], "Ἐν")
        self.assertEqual(sum(w["lemma"] == "λόγος" for w in john), 3)
        genesis = json.loads((DATA / "original/1/1.json").read_text())["1"]
        self.assertTrue(any(w["strong"] == "H1254" for w in genesis))
        self.assertTrue(all("morph" in w and "gloss" in w for w in genesis))

    def test_fixed_kjv_source_includes_romans_eight(self):
        romans = json.loads((DATA / "translations/KJV/45.json").read_text())
        self.assertIn("no condemnation", romans["8"]["1"])
        catalog = json.loads((DATA / "catalog.json").read_text())
        kjv = next(t for t in catalog["translations"] if t["id"] == "KJV")
        self.assertEqual(kjv["verses"], 31102)
        self.assertFalse(kjv["sourceGaps"])

    def test_web_poetic_lines_are_not_lost(self):
        psalms = json.loads((DATA / "translations/WEB/19.json").read_text())
        self.assertIn("shepherd", psalms["23"]["1"])
        self.assertGreater(len(psalms["119"]), 170)

    def test_names_and_canon_are_not_position_mapped(self):
        self.assertEqual(book_id("I Samuel"), 9)
        self.assertEqual(book_id("Tobit"), 67)
        self.assertEqual(book_id("Revelation of John"), 66)
        catalog = json.loads((DATA / "catalog.json").read_text())
        for code in ("DRC", "CPDV"):
            edition = next(t for t in catalog["translations"] if t["id"] == code)
            self.assertEqual(len(edition["books"]), 73)
            self.assertEqual(edition["numbering"], "native")


if __name__ == "__main__":
    unittest.main()
