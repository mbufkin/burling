"""Progress formatting. No model."""

from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path

from burling.progress import format_duration, format_tokens, print_status, record_tokens
from burling.queue import build_queue


class ProgressTests(unittest.TestCase):
    def test_duration_format(self) -> None:
        self.assertEqual(format_duration(12), "12s")
        self.assertEqual(format_duration(63), "1m03s")
        self.assertEqual(format_duration(3723), "1h02m")

    def test_token_counter_accumulates(self) -> None:
        self.assertEqual(format_tokens(0), "0  (0)")
        self.assertEqual(format_tokens(1_250_000), "1,250,000  (1.25M)")
        with tempfile.TemporaryDirectory() as tmp:
            cfg = {"paths": {"output_dir": tmp}}
            record_tokens(cfg, 100, 20, "pass1")
            record_tokens(cfg, 50, 10, "pass2")
            from burling.progress import load_json, tokens_file

            data = load_json(tokens_file(cfg), {})
            self.assertEqual(data["total_tokens"], 180)
            self.assertEqual(data["prompt_tokens"], 150)
            self.assertEqual(data["completion_tokens"], 30)
            self.assertEqual(data["calls"], 2)
            self.assertEqual(data["pass1_tokens"], 120)
            self.assertEqual(data["pass2_tokens"], 60)

    def test_console_safe_replaces_undisplayable(self) -> None:
        from burling.progress import console_safe

        class Cp1252:
            encoding = "cp1252"

        # U+2420 showed up in a Drive filename and killed the cp1252 console.
        out = console_safe("Team's Mission\u2420and Vision.pdf", Cp1252())
        self.assertNotIn("\u2420", out)

    def test_status_reads_ledger_from_second_terminal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            intake = root / "intake"
            output = root / "output"
            intake.mkdir()
            (intake / "lesson.md").write_text("CTE lesson plan.\n", encoding="utf-8")
            cfg = {
                "paths": {"intake_dir": str(intake), "output_dir": str(output)},
                "policy": {"fail_closed_on_personal_tax": True},
            }
            build_queue(cfg, intake=intake)
            buf = io.StringIO()
            print_status(cfg, stream=buf)
            text = buf.getvalue()
            self.assertIn("documents    1", text)
            self.assertIn("pass 1", text)
            self.assertIn("tokens", text)


if __name__ == "__main__":
    unittest.main()
