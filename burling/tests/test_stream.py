"""Drive stream policy. No rclone, no GPU."""

from __future__ import annotations

import unittest

from burling.stream import already_reviewed, should_trash_on_drive


class StreamPolicyTests(unittest.TestCase):
    def test_student_tb_is_never_trashed(self) -> None:
        row = {
            "rel_path": "Dallas ISD TB Results/ALEXIS GUERECA TB LAB RESULTS.pdf",
            "pass2": {"recommendation": "delete_candidate", "status": "done"},
        }
        self.assertFalse(should_trash_on_drive(row))

    def test_personal_tax_is_trashed(self) -> None:
        row = {
            "rel_path": "2018_TaxReturn.pdf",
            "pass2": {"recommendation": "delete_candidate", "status": "done"},
        }
        self.assertTrue(should_trash_on_drive(row))

    def test_work_keep_stays_on_drive(self) -> None:
        row = {
            "rel_path": "pacing-guide.pdf",
            "pass2": {"recommendation": "keep", "status": "done"},
        }
        self.assertFalse(should_trash_on_drive(row))

    def test_already_reviewed_skips_second_download(self) -> None:
        self.assertTrue(already_reviewed({"pass2": {"status": "done"}}))
        self.assertFalse(already_reviewed({"pass2": {"status": "skipped"}}))
        self.assertFalse(already_reviewed({"pass2": None}))
        self.assertFalse(already_reviewed(None))


if __name__ == "__main__":
    unittest.main()
