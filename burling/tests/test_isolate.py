"""GOLDEN RULE: one file must not kill the run. No model, no GPU."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from burling.isolate import OPERATOR_STOP, note_file_failure
from burling.ledger import load_ledger
from burling.pass1 import run_pass1
from burling.queue import build_queue


def _cfg(intake: Path, output: Path) -> dict:
    return {
        "paths": {"intake_dir": str(intake), "output_dir": str(output)},
        "policy": {"fail_closed_on_personal_tax": True},
        "chunking": {
            "threshold_chars": 12000,
            "chunk_chars": 10000,
            "overlap_chars": 400,
        },
    }


class IsolateTests(unittest.TestCase):
    def test_note_file_failure_stays_in_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = {"paths": {"output_dir": tmp}}
            ledger = {"documents": {}}
            row = note_file_failure(
                cfg,
                ledger,
                {"rel_path": "weird.pdf", "doc_id": "abc"},
                stage="pass1",
                exc=TimeoutError("ollama hung"),
            )
            self.assertEqual(row["queue_status"], "pass1_skipped")
            self.assertEqual(row["pass1"]["status"], "skipped")
            self.assertIn("abc", ledger["documents"])
            saved = load_ledger(cfg)
            self.assertEqual(saved["documents"]["abc"]["queue_status"], "pass1_skipped")

    def test_ctrl_c_is_not_a_bad_file(self) -> None:
        self.assertTrue(issubclass(KeyboardInterrupt, OPERATOR_STOP))
        self.assertTrue(issubclass(SystemExit, OPERATOR_STOP))
        self.assertFalse(issubclass(TimeoutError, OPERATOR_STOP))

    def test_middle_file_timeout_does_not_stop_pass1(self) -> None:
        """Best practice: isolate the failure, keep walking the dump."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            intake = root / "intake"
            output = root / "output"
            intake.mkdir()
            (intake / "a-lesson.txt").write_text("unit 1 lesson plan", encoding="utf-8")
            (intake / "b-hung.txt").write_text("this file will timeout", encoding="utf-8")
            (intake / "c-lesson.txt").write_text("unit 2 lesson plan", encoding="utf-8")
            cfg = _cfg(intake, output)
            build_queue(cfg, intake=intake)

            def fake_chat(_cfg, _messages, step=""):
                if "b-hung.txt" in step:
                    raise TimeoutError("ollama hung on one fat PDF")
                return {
                    "tags": ["curriculum_lesson"],
                    "primary_tag": "curriculum_lesson",
                    "custody": "work",
                    "work_related": True,
                    "summary": "A lesson plan.",
                    "confidence": "high",
                }

            with patch("burling.pass1.chat", fake_chat):
                done = run_pass1(cfg)
            self.assertEqual(done, 2)
            by_name = {r["rel_path"]: r for r in load_ledger(cfg)["documents"].values()}
            self.assertEqual(by_name["a-lesson.txt"]["queue_status"], "pass1_done")
            self.assertEqual(by_name["b-hung.txt"]["queue_status"], "pass1_skipped")
            self.assertEqual(by_name["c-lesson.txt"]["queue_status"], "pass1_done")
            self.assertIn("TimeoutError", by_name["b-hung.txt"]["pass1"]["error"])

    def test_ctrl_c_still_stops_the_run(self) -> None:
        """The operator is not a bad file. Ctrl+C must not be swallowed."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            intake = root / "intake"
            output = root / "output"
            intake.mkdir()
            (intake / "a-lesson.txt").write_text("unit 1", encoding="utf-8")
            (intake / "b-stop.txt").write_text("operator stop", encoding="utf-8")
            cfg = _cfg(intake, output)
            build_queue(cfg, intake=intake)

            def fake_chat(_cfg, _messages, step=""):
                if "b-stop.txt" in step:
                    raise KeyboardInterrupt()
                return {
                    "tags": ["curriculum_lesson"],
                    "primary_tag": "curriculum_lesson",
                    "custody": "work",
                    "work_related": True,
                    "summary": "A lesson plan.",
                    "confidence": "high",
                }

            with patch("burling.pass1.chat", fake_chat):
                with self.assertRaises(KeyboardInterrupt):
                    run_pass1(cfg)


if __name__ == "__main__":
    unittest.main()
