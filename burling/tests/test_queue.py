"""Queue + ledger tests against a tiny synthetic dump. No model."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from burling.queue import build_queue
from burling.reports import write_reports


class QueueTests(unittest.TestCase):
    def test_priors_only_maps_and_flags_ssn(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            intake = root / "intake"
            output = root / "output"
            intake.mkdir()
            (intake / "unit1-lesson-plan.md").write_text(
                "# Day 1 Engage\nStudents label the urinary system.\n",
                encoding="utf-8",
            )
            (intake / "old-w2-notes.txt").write_text(
                "Leftover personal file.\nSSN 123-45-6789\n",
                encoding="utf-8",
            )
            cfg = {
                "paths": {
                    "intake_dir": str(intake),
                    "output_dir": str(output),
                },
                "policy": {"fail_closed_on_ssn": True},
            }
            queue = build_queue(cfg, intake=intake)
            self.assertEqual(queue["total"], 2)
            from burling.ledger import load_ledger

            ledger = load_ledger(cfg)
            by_name = {r["rel_path"]: r for r in ledger["documents"].values()}
            self.assertIn("ssn", by_name["old-w2-notes.txt"]["priors"])
            self.assertEqual(by_name["old-w2-notes.txt"]["prior_severity"], "high")
            self.assertNotIn("ssn", by_name["unit1-lesson-plan.md"]["priors"])
            stats = write_reports(cfg)
            self.assertEqual(stats["documents"], 2)
            self.assertTrue((output / "DOCUMENT-MAP.md").exists())
            self.assertTrue((output / "REVIEW-QUEUE.md").exists())
            map_text = (output / "DOCUMENT-MAP.md").read_text(encoding="utf-8")
            self.assertIn("unit1-lesson-plan.md", map_text)

    def test_pending_retries_skipped_files(self) -> None:
        from burling.queue import pending

        ledger = {
            "documents": {
                "a": {
                    "rel_path": "a.txt",
                    "extraction": {"ok": True},
                    "pass1": {"status": "done"},
                },
                "b": {
                    "rel_path": "b.txt",
                    "extraction": {"ok": True},
                    "pass1": {"status": "skipped", "error": "timeout"},
                },
                "c": {
                    "rel_path": "c.txt",
                    "extraction": {"ok": True},
                },
            }
        }
        todo = pending(ledger, "pass1")
        names = [r["rel_path"] for r in todo]
        self.assertEqual(names, ["b.txt", "c.txt"])


if __name__ == "__main__":
    unittest.main()
