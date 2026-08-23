"""Andon stop: high-severity leftovers halt filing and force keep. No model.

Protocol from research ticket #37 (Toyota jidoka / poka-yoke applied to
filing):

1. A high-severity item the clerk cannot place is auto-kept in its
   current home — never binned in unmapped, never moved to a holding
   series.
2. Filing halts while the keep is unresolved.
3. Filing a mapped item completes normally; low-severity leftovers bin
   as before.

Pass = high-severity unmapped keeps + line stop; fail = silent bin or a
new holding folder.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from burling.file_plan import UNMAPPED_ID
from burling.walk_plan import (
    ChildChoice,
    WalkState,
    _severity_map,
    walk_one,
)


def _unmapped_chooser(**kw):
    return {"main": "unmapped", "reason": "unsubscribe request"}


def _mapped_chooser(**kw):
    return {"main": "operations", "reasoning": "project notes", "summary": ""}


def _noop_child(**kw):
    return {"action": "empty"}


class AndonKeepTests(unittest.TestCase):
    def test_high_severity_unmapped_is_kept_not_binned(self) -> None:
        state = WalkState()
        home = walk_one(
            state,
            rel_path="urgent.txt",
            text="please unsubscribe me from this list",
            choose_main=_unmapped_chooser,
            choose_child=_noop_child,
            severity="high",
        )
        self.assertEqual(home, [])
        # Current home is the intake folder — it must NOT enter the tree,
        # and it must not land in an unmapped/holding series either.
        self.assertNotIn("urgent.txt", state.homes)
        rec = state.records["urgent.txt"]
        self.assertEqual(rec["status"], "andon-keep")
        self.assertIn("andon", rec["reason"])
        self.assertIn("urgent.txt", state.andon_keeps)

    def test_high_severity_missing_extract_is_kept_too(self) -> None:
        # OCR-recover case: extraction failed on a scan that matters.
        state = WalkState()
        walk_one(
            state,
            rel_path="scan.pdf",
            text="   ",
            choose_main=_mapped_chooser,
            choose_child=_noop_child,
            severity="high",
        )
        self.assertNotIn("scan.pdf", state.homes)
        self.assertEqual(state.records["scan.pdf"]["status"], "andon-keep")

    def test_low_severity_unmapped_still_bins(self) -> None:
        state = WalkState()
        home = walk_one(
            state,
            rel_path="me-too.txt",
            text="please unsubscribe me from this list",
            choose_main=_unmapped_chooser,
            choose_child=_noop_child,
            severity="low",
        )
        self.assertEqual(home, [UNMAPPED_ID])
        self.assertNotIn("me-too.txt", state.andon_keeps)
        self.assertEqual(state.records["me-too.txt"]["status"], "done")

    def test_medium_severity_unmapped_bins(self) -> None:
        # Only HIGH stops the line (protocol step 5).
        state = WalkState()
        walk_one(
            state,
            rel_path="sig.txt",
            text="please unsubscribe me from this list",
            choose_main=_unmapped_chooser,
            choose_child=_noop_child,
            severity="medium",
        )
        self.assertNotIn("sig.txt", state.andon_keeps)
        self.assertEqual(state.homes.get("sig.txt"), [UNMAPPED_ID])

    def test_mapped_high_severity_files_normally(self) -> None:
        # Protocol step 4: filing the high-severity item into a mapped
        # series completes without any halt.
        state = WalkState()
        home = walk_one(
            state,
            rel_path="urgent2.txt",
            text="Q3 project plan for the roof repair.",
            choose_main=_mapped_chooser,
            choose_child=_noop_child,
            severity="high",
        )
        self.assertEqual(home[0], "operations")
        self.assertNotIn("urgent2.txt", state.andon_keeps)
        self.assertEqual(state.records["urgent2.txt"]["status"], "done")


class AndonResumeTests(unittest.TestCase):
    def test_refile_clears_the_keep(self) -> None:
        state = WalkState()
        walk_one(
            state,
            rel_path="stuck.txt",
            text="please unsubscribe me from this list",
            choose_main=_unmapped_chooser,
            choose_child=_noop_child,
            severity="high",
        )
        self.assertIn("stuck.txt", state.andon_keeps)
        # Operator fixed the cause; resume re-files the kept document.
        walk_one(
            state,
            rel_path="stuck.txt",
            text="Budget approval for the new server rack.",
            choose_main=_mapped_chooser,
            choose_child=_noop_child,
            severity="high",
        )
        self.assertNotIn("stuck.txt", state.andon_keeps)
        self.assertEqual(state.records["stuck.txt"]["status"], "done")
        self.assertEqual(state.homes["stuck.txt"][0], "operations")


class SeverityMapTests(unittest.TestCase):
    def test_reads_prior_severity_from_queue_json(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            qp = root / "queue.json"
            qp.write_text(
                json.dumps(
                    {
                        "documents": {
                            "a": {"rel_path": "hot.txt", "prior_severity": "high"},
                            "b": {"rel_path": "cold.txt", "prior_severity": "low"},
                        }
                    }
                ),
                encoding="utf-8",
            )
            cfg = {"paths": {"output_dir": str(root)}}
            sevs = _severity_map(cfg)
        self.assertEqual(sevs.get("hot.txt"), "high")
        self.assertEqual(sevs.get("cold.txt"), "low")
        self.assertEqual(sevs.get("absent.txt"), None)

    def test_missing_queue_file_means_no_severities(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cfg = {"paths": {"output_dir": td}}
            self.assertEqual(_severity_map(cfg), {})


if __name__ == "__main__":
    unittest.main()
