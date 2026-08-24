"""Walk call log: decision context recorded, document text never stored."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from burling.walk_plan import _ask, _log_walk_call


class WalkLogTests(unittest.TestCase):
    def test_logs_context_and_raw_but_not_document_text(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cfg = {"paths": {"output_dir": td}}
            messages = [
                {"role": "system", "content": "sys"},
                {"role": "user", "content": (
                    "FILE: a.txt\nCURRENT FOLDER: finance\n\n"
                    "EXISTING CHILDREN:\n- invoices: 2\n\n"
                    "DOCUMENT TEXT:\nSECRET-BODY-SSN-123-45-6789"
                )},
            ]
            _log_walk_call(cfg, "walk-child:finance:a.txt", messages, {"action": "reuse"})
            lines = (Path(td) / "walk-decisions.jsonl").read_text().splitlines()
            rec = json.loads(lines[0])
        self.assertEqual(rec["step"], "walk-child:finance:a.txt")
        self.assertEqual(rec["raw"], {"action": "reuse"})
        self.assertIn("invoices: 2", rec["context"])
        self.assertNotIn("SECRET-BODY", rec["context"])
        self.assertNotIn("123-45-6789", json.dumps(rec))

    def test_failure_is_logged_with_error(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cfg = {"paths": {"output_dir": td}, "ollama": {"url": "http://127.0.0.1:1"}}
            raw = _ask(cfg, [{"role": "user", "content": "x"}], "walk-main:t")
            rec = json.loads(
                (Path(td) / "walk-decisions.jsonl").read_text().splitlines()[0]
            )
        self.assertEqual(raw, {})
        self.assertIn("error", rec)


if __name__ == "__main__":
    unittest.main()
