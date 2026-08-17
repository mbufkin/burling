"""Search scoring and name parsing. No GPU, no real corpus."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from burling.search import (
    classify_hit,
    names_from_filename,
    normalize_text,
    redact_snippet,
    score_file,
    search_tree,
)


class NameParseTests(unittest.TestCase):
    def test_grant_packet_lastname(self) -> None:
        # LAST_EVENT is how TIVA/THOA packets were named in this dump.
        self.assertIn("Bautista", names_from_filename("BAUTISTA_TIVA GRANT TRAVEL DOCS.pdf"))
        self.assertIn("Cozart", names_from_filename("COZART_TIVA GRANT TRAVEL DOCS - signed (1).pdf"))

    def test_first_last_before_event(self) -> None:
        names = names_from_filename("Jeremy Spence_NAF Next 2026 Conference.pdf (SECURED).pdf")
        self.assertTrue(any("Jeremy Spence" in n for n in names), names)

    def test_glued_initial(self) -> None:
        names = names_from_filename("C.Seay- 2025 Certified Educator Conference - signed.pdf")
        self.assertTrue(any("Seay" in n for n in names), names)

    def test_trailing_initials_on_district_form(self) -> None:
        names = names_from_filename("DallasISDTravel - ACTE Best Practices - JS.pdf")
        self.assertIn("JS", names)

    def test_uber_receipt_surname(self) -> None:
        names = names_from_filename("Spence-Uber-NAF Conference.pdf")
        self.assertTrue(any("Spence" in n for n in names), names)

    def test_does_not_invent_a_person_from_an_agenda(self) -> None:
        self.assertEqual(names_from_filename("ACTE Vision 2025 Agenda.pdf"), [])


class ScoreTests(unittest.TestCase):
    def test_travel_form_outranks_tax_return(self) -> None:
        travel = score_file("A Goodson Travel form - signed.pdf", "Conference/Event name: ACTE")
        tax = score_file("2018_TaxReturn.pdf", "summer refund")
        self.assertGreater(travel, 10)
        self.assertLess(tax, 6)

    def test_local_summer_pd_is_not_travel(self) -> None:
        kind = classify_hit("PD Summer Schedule.pdf", "SUMMER PROFESSIONAL DEVELOPMENT 2026")
        self.assertEqual(kind, "local_pd")

    def test_hotel_plus_naf_is_pd_travel(self) -> None:
        kind = classify_hit("Hotel NAF Next .pdf", "Guest name: Example Person\nNAF Next 2026")
        self.assertEqual(kind, "pd_travel")

    def test_spaced_pdf_title_normalizes(self) -> None:
        raw = "S U M M E R  P R O F E S S I O N A L  D E V E L O P M E N T  2 0 2 6"
        self.assertIn("SUMMER", normalize_text(raw))
        self.assertIn("PROFESSIONAL", normalize_text(raw))

    def test_ssn_redacted_in_snippet(self) -> None:
        # 123-45-6789 is the SSA advertising example, not a real person.
        out = redact_snippet("Traveler SSN 123-45-6789 flew to the conference")
        self.assertNotIn("123-45-6789", out)
        self.assertIn("***-**-6789", out)


class TreeSearchTests(unittest.TestCase):
    def test_finds_traveler_and_skips_tax(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "A Goodson Travel form - signed.txt").write_text(
                "Traveler name: A Goodson\nConference/Event name: ACTE Best Practices\nJune 2026\n",
                encoding="utf-8",
            )
            (root / "2018_TaxReturn.txt").write_text(
                "Form 1040 summer refund SSN 123-45-6789\n",
                encoding="utf-8",
            )
            (root / "PD Summer Schedule.txt").write_text(
                "SUMMER PROFESSIONAL DEVELOPMENT 2026 campus rooms\n",
                encoding="utf-8",
            )
            rows = search_tree(root)
            by_name = {r["filename"]: r for r in rows}
            self.assertIn("A Goodson Travel form - signed.txt", by_name)
            self.assertEqual(by_name["A Goodson Travel form - signed.txt"]["kind"], "pd_travel")
            self.assertTrue(any("Goodson" in n for n in by_name["A Goodson Travel form - signed.txt"]["names"]))
            self.assertNotIn("2018_TaxReturn.txt", by_name)
            self.assertEqual(by_name["PD Summer Schedule.txt"]["kind"], "local_pd")


if __name__ == "__main__":
    unittest.main()
