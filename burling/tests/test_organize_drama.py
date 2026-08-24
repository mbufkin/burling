"""Organize drama: the full walk story, scored against labels.json. No model.

Layer 3 of docs/test-corpus.md. A scripted "gold clerk" plays the model via
run_walk_plan's injected choosers (same seam test_walk_andon uses), so CI
never needs a GPU:

1. First pass: every doc files to its labeled home — until the high-severity
   unplaceable export garbage trips the andon and halts the line.
2. The operator assigns the kept file a home; resume clears the keep and
   files the rest.
3. Final state scores 1.0 against labels.json: all 13 mains, junk binned,
   empty left unmapped, personal lane intact, mixed drawer split.

Combine/rehome is proven separately on maintain_after_place.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from burling.file_plan import UNMAPPED_ID
from burling.queue import build_queue
from burling.score_placements import load_labels, score_run
from burling.walk_plan import ChildChoice, WalkState, load_walk_state, run_walk_plan
from burling.maintain_plan import maintain_after_place

FIXTURES = Path(__file__).resolve().parent / "fixtures"
DRAMA_DIR = FIXTURES / "organize-drama"
LABELS = load_labels(DRAMA_DIR / "labels.json")
ANDON_DOC = "special/legacy-export.txt"


def _gold_main(*, rel_path: str, text: str) -> dict:
    if rel_path not in LABELS:
        # labels.json itself gets queued; it is a fixture artifact, not drama.
        return {"main": UNMAPPED_ID, "reason": "fixture artifact"}
    if rel_path == ANDON_DOC:
        # No topical mission. A good clerk refuses to invent a series.
        return {"main": "", "reason": "no topical substance"}
    return {"main": LABELS[rel_path]["main"], "reason": "gold label"}


def _gold_main_after_operator_fix(*, rel_path: str, text: str) -> dict:
    if rel_path not in LABELS:
        return {"main": UNMAPPED_ID, "reason": "fixture artifact"}
    if rel_path == ANDON_DOC:
        # The operator decided this belongs with credentials handling.
        return {"main": "security", "reason": "operator assignment", "summary": ""}
    return {"main": LABELS[rel_path]["main"], "reason": "gold label"}


def _gold_child(*, rel_path: str, text: str, prefix: list[str], siblings: list) -> dict:
    sub = kebab_safe((LABELS.get(rel_path) or {}).get("sub") or "")
    if not sub:
        return {"action": "empty"}
    return {"name": sub}


def kebab_safe(raw: str) -> str:
    from burling.layer_plan import kebab

    return kebab(raw)


class DramaWalkTests(unittest.TestCase):
    """End-to-end: halt on the andon, operator fix, resume, score 1.0."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        intake = Path(cls._tmp.name) / "intake"
        output = Path(cls._tmp.name) / "output"
        shutil.copytree(DRAMA_DIR, intake)
        cls.cfg = {"paths": {"intake_dir": str(intake), "output_dir": str(output)}}
        build_queue(cls.cfg, intake=intake)

        # Pass 1: the line runs until the unplaceable file trips the andon.
        run_walk_plan(cls.cfg, choose_main=_gold_main, choose_child=_gold_child)
        halted = load_walk_state(cls.cfg)
        cls.halted_homes = dict(halted.homes)
        cls.halted_keeps = dict(halted.andon_keeps)

        # Operator resolves the keep by assigning it a home.
        run_walk_plan(
            cls.cfg,
            resume=True,
            choose_main=_gold_main_after_operator_fix,
            choose_child=_gold_child,
        )
        cls.final = load_walk_state(cls.cfg)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_pass1_trips_the_andon_and_halts(self) -> None:
        self.assertIn(ANDON_DOC, self.halted_keeps)
        rec = json.loads(json.dumps(self.halted_homes))  # sanity: homes is JSON-ish
        # The kept file is filed nowhere.
        self.assertNotIn(ANDON_DOC, self.halted_homes)
        # Docs sorting after the halt stayed unfiled (the line stopped).
        self.assertNotIn("training/plans/newhire-training-plan.txt", self.halted_homes)

    def test_resume_clears_keep_and_files_everything(self) -> None:
        self.assertEqual(self.final.andon_keeps, {})
        self.assertIn(ANDON_DOC, self.final.homes)
        self.assertEqual(
            self.final.homes[ANDON_DOC][:2], ["security", "credentials"]
        )
        # +1: labels.json itself gets queued and filed as an artifact.
        self.assertEqual(
            self.final.homes.keys() - LABELS.keys(), {"labels.json"}
        )
        self.assertEqual(len(self.final.homes), len(LABELS) + 1)

    def test_final_state_scores_perfect_against_labels(self) -> None:
        report = score_run(self.final.homes, LABELS)
        self.assertEqual(
            report["misses"], [], f"accuracy {report['accuracy']}: {report['misses']}"
        )
        self.assertEqual(report["matched"], report["total"])
        self.assertEqual(report["accuracy"], 1.0)

    def test_low_severity_junk_binned_not_kept(self) -> None:
        for rel in ("special/unsubscribe-confirmations.txt", "special/me-too-thread.txt"):
            self.assertEqual(self.final.homes.get(rel), [UNMAPPED_ID], rel)

    def test_empty_doc_is_unmapped_with_extract_missing_reason(self) -> None:
        rel = "scratch/empty-scratch.txt"
        self.assertEqual(self.final.homes.get(rel), [UNMAPPED_ID])
        self.assertEqual(self.final.records[rel]["reason"], "extract missing")

    def test_mixed_drawer_split_across_three_mains(self) -> None:
        mains = {
            "mixed/project-alpha-budget.txt": "finance",
            "mixed/project-alpha-roster.txt": "personnel",
            "mixed/project-alpha-press.txt": "communications",
        }
        for rel, main in mains.items():
            self.assertEqual((self.final.homes.get(rel) or [None])[0], main, rel)

    def test_personal_lane_files_normally(self) -> None:
        self.assertEqual(
            self.final.homes["personal/family/family-chili-recipe.txt"][:2],
            ["personal", "family"],
        )


class CombineTests(unittest.TestCase):
    """Near-duplicate pair rehoming: maintain merges over-split year drawers."""

    def test_vendor_pair_combines_into_one_drawer(self) -> None:
        state = WalkState()
        y24 = ChildChoice("invent", "vendor-payments-2024")
        y25 = ChildChoice("invent", "vendor-payments-2025")
        inv = ChildChoice("invent", "invoices")
        state.place("finance/vendor-payment-list-2024.txt",
                    main="finance", sub=y24, detail=ChildChoice("empty", ""))
        state.place("finance/vendor-payment-list-2025.txt",
                    main="finance", sub=y25, detail=ChildChoice("empty", ""))
        state.place("finance/invoice-acme-0042.txt",
                    main="finance", sub=inv, detail=ChildChoice("empty", ""))

        calls: list[list[str]] = []

        def fake_combine(**kw):
            calls.append(list(kw.get("prefix") or []))
            return {
                "groups": [
                    {
                        "merge": ["vendor-payments-2024", "vendor-payments-2025"],
                        "into": "vendors",
                    }
                ],
                "reasoning": "same roster split by year",
            }

        moved = maintain_after_place(
            state, ["finance"], choose_combine=fake_combine, fat_min=1
        )

        self.assertEqual(moved, 2)
        self.assertEqual(calls, [["finance"]])
        # rehome nests the old year drawers under the merged name when
        # depth allows: finance/vendors/vendor-payments-2024.
        self.assertEqual(
            state.homes["finance/vendor-payment-list-2024.txt"],
            ["finance", "vendors", "vendor-payments-2024"],
        )
        self.assertEqual(
            state.homes["finance/vendor-payment-list-2025.txt"],
            ["finance", "vendors", "vendor-payments-2025"],
        )
        self.assertEqual(state.combines[0]["into"], "vendors")
        # Leftover sibling stays put.
        self.assertEqual(state.homes["finance/invoice-acme-0042.txt"][1], "invoices")


if __name__ == "__main__":
    unittest.main()
