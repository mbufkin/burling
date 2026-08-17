"""Flat decision sidecars. No model, no GPU."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from burling.pass2 import _force_personal_tax
from burling.queue import build_queue
from burling.reports import write_reports
from burling.trace import flatten_decision


class FlattenTests(unittest.TestCase):
    def test_one_level_keys_and_redacted_priors(self) -> None:
        row = {
            "doc_id": "abc123",
            "rel_path": "old-w2-notes.txt",
            "ext": ".txt",
            "size_bytes": 40,
            "char_count": 40,
            "content_hash": "deadbeef",
            "queue_status": "pass2_done",
            "queued_at": "2026-08-12T20:00:00+00:00",
            "filename_tags": ["tax_financial"],
            "prior_severity": "high",
            "extraction": {"ok": True, "method": "text", "error": None},
            "priors": {"ssn": {"count": 1, "redacted_samples": ["***-**-6789"]}},
            "pass1": {
                "status": "done",
                "at": "2026-08-12T20:01:00+00:00",
                "tags": ["tax_financial"],
                "primary_tag": "tax_financial",
                "custody": "personal",
                "work_related": False,
                "confidence": "high",
                "summary": "Leftover tax notes.",
                "chunk_count": 1,
                "chunk_custodies": "personal",
            },
            "pass2": {
                "status": "done",
                "at": "2026-08-12T20:02:00+00:00",
                "model_custody": "work",
                "model_recommendation": "keep",
                "model_reasons": ["keep_work_admin"],
                "rationale": "Model guessed work.",
                "confidence": "low",
                "code_override": "fail_closed_personal_tax_filename",
                "fail_closed": True,
                "custody": "personal",
                "recommendation": "delete_candidate",
                "reasons": ["personal_tax"],
            },
        }
        flat = flatten_decision(row)
        nested = [k for k, v in flat.items() if isinstance(v, dict)]
        self.assertEqual(nested, [], f"nested values under {nested}")
        self.assertEqual(flat["steps_done"], "extract,priors,pass1,pass2")
        self.assertEqual(flat["prior_ssn_samples"], "***-**-6789")
        self.assertNotIn("123-45-6789", json.dumps(flat))
        self.assertEqual(flat["pass2_model_recommendation"], "keep")
        self.assertEqual(flat["pass2_final_recommendation"], "delete_candidate")
        self.assertEqual(flat["pass2_code_override"], "fail_closed_personal_tax_filename")

    def test_sidecar_written_during_queue_build(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            intake = root / "intake"
            output = root / "output"
            intake.mkdir()
            (intake / "unit1-lesson-plan.md").write_text(
                "# Day 1 Engage\nStudents label the urinary system.\n",
                encoding="utf-8",
            )
            cfg = {
                "paths": {
                    "intake_dir": str(intake),
                    "output_dir": str(output),
                },
                "policy": {"fail_closed_on_personal_tax": True},
            }
            build_queue(cfg, intake=intake)
            sidecar = output / "decisions" / "unit1-lesson-plan.md.json"
            self.assertTrue(sidecar.exists(), sidecar)
            data = json.loads(sidecar.read_text(encoding="utf-8"))
            self.assertEqual(data["rel_path"], "unit1-lesson-plan.md")
            self.assertTrue(data["extract_ok"])
            self.assertEqual(data["steps_done"], "extract,priors")
            self.assertIsNone(data["pass1_status"])
            write_reports(cfg)
            index = json.loads((output / "DECISIONS.json").read_text(encoding="utf-8"))
            self.assertEqual(index["documents"], 1)

    def test_fail_closed_records_override(self) -> None:
        row = {"filename_tags": ["tax_financial"]}
        result = {
            "recommendation": "keep",
            "custody": "work",
            "reasons": ["keep_work_admin"],
        }
        cfg = {"policy": {"fail_closed_on_personal_tax": True}}
        out = _force_personal_tax(row, result, cfg)
        self.assertEqual(out["recommendation"], "delete_candidate")
        self.assertTrue(out["fail_closed"])


if __name__ == "__main__":
    unittest.main()
