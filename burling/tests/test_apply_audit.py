"""Apply-audit + RALP stop rules. No model."""

from __future__ import annotations

import unittest

from burling.apply_audit import apply_audit_to_payload, flag_rate, should_stop_ralp
from burling.ralp import _apply_revise, _mixed_groups, dissolve_singularities


def _payload() -> dict:
    return {
        "regions": [
            {
                "id": "transport",
                "label": "Transport",
                "description": "Moving people and goods",
                "tags": ["rail"],
                "children": [],
            },
            {
                "id": "health",
                "label": "Health",
                "description": "Clinics and vaccines",
                "tags": ["clinic"],
                "children": [],
            },
            {
                "id": "needs-review",
                "label": "Needs review",
                "description": "Leftovers",
                "tags": [],
                "children": [],
            },
        ],
        "assignments": [
            {
                "rel_path": "rail.txt",
                "region_ids": ["health"],
                "summary": "A timetable.",
            },
            {
                "rel_path": "clinic.txt",
                "region_ids": ["health"],
                "summary": "Walk-in hours.",
            },
            {
                "rel_path": "orphan.txt",
                "region_ids": ["needs-review"],
                "summary": "Unclear scan.",
            },
        ],
    }


def _state() -> dict:
    return {
        "chunks": {
            "health#00": {
                "status": "done",
                "files": [
                    {
                        "rel_path": "rail.txt",
                        "verdict": "wrong-parent",
                        "better_home": "transport",
                        "reason": "Timetable is transport.",
                    },
                    {
                        "rel_path": "clinic.txt",
                        "verdict": "confirm",
                        "better_home": "",
                        "reason": "Clinic hours belong here.",
                    },
                    {
                        "rel_path": "clinic.txt",
                        "verdict": "missing-parent",
                        "better_home": "ghost-node",
                        "reason": "Invalid home must be skipped.",
                    },
                ],
            },
            "needs-review#00": {
                "status": "done",
                "files": [
                    {
                        "rel_path": "orphan.txt",
                        "verdict": "leftover-should-place",
                        "better_home": "health",
                        "reason": "Looks like a clinic flyer.",
                    }
                ],
            },
        }
    }


class ApplyAuditTests(unittest.TestCase):
    def test_wrong_parent_moves_primary(self) -> None:
        out = apply_audit_to_payload(_payload(), _state())
        by = {a["rel_path"]: a["region_ids"] for a in out["payload"]["assignments"]}
        self.assertEqual(by["rail.txt"][0], "transport")
        self.assertEqual(by["clinic.txt"], ["health"])
        self.assertEqual(by["orphan.txt"], ["health"])
        self.assertEqual(len(out["applied"]), 2)
        self.assertTrue(any(s["skip"] == "invalid-home" for s in out["skipped"]))

    def test_confirm_does_not_move(self) -> None:
        out = apply_audit_to_payload(_payload(), _state())
        clinic = next(
            a for a in out["payload"]["assignments"] if a["rel_path"] == "clinic.txt"
        )
        self.assertEqual(clinic["region_ids"], ["health"])

    def test_flag_rate_ignores_confirms(self) -> None:
        self.assertAlmostEqual(flag_rate(_state()), 0.75)

    def test_stop_when_yield_drops(self) -> None:
        self.assertEqual(
            should_stop_ralp(
                applied_n=0, rate=0.4, round_i=1, max_rounds=3
            ),
            "no-applies",
        )
        self.assertEqual(
            should_stop_ralp(
                applied_n=4, rate=0.05, round_i=1, max_rounds=3
            ),
            "flag-rate",
        )
        self.assertEqual(
            should_stop_ralp(
                applied_n=4, rate=0.4, round_i=3, max_rounds=3
            ),
            "max-rounds",
        )
        self.assertIsNone(
            should_stop_ralp(
                applied_n=4, rate=0.4, round_i=1, max_rounds=3
            )
        )
        self.assertEqual(
            should_stop_ralp(
                applied_n=4,
                rate=0.56,
                round_i=2,
                max_rounds=3,
                prev_rate=0.33,
            ),
            "flags-rose",
        )
        self.assertIsNone(
            should_stop_ralp(
                applied_n=4,
                rate=0.33,
                round_i=2,
                max_rounds=3,
                prev_rate=0.33,
            )
        )

    def test_mixed_groups_any_wrong_parent(self) -> None:
        state = {
            "chunks": {
                "transport#00": {
                    "status": "done",
                    "files": [
                        {"verdict": "wrong-parent"},
                        {"verdict": "wrong-parent"},
                        {"verdict": "confirm"},
                    ],
                },
                "health#00": {
                    "status": "done",
                    "files": [
                        {"verdict": "wrong-parent"},
                        {"verdict": "wrong-parent"},
                        {"verdict": "wrong-parent"},
                    ],
                },
            }
        }
        self.assertEqual(_mixed_groups(state), ["health", "transport"])
        self.assertEqual(_mixed_groups(state, min_wrong=3), ["health"])

    def test_dissolve_folds_one_file_child(self) -> None:
        payload = {
            "regions": [
                {
                    "id": "transport",
                    "label": "Transport",
                    "description": "Moving people and goods",
                    "tags": [],
                    "children": [
                        {
                            "id": "transport-rail",
                            "label": "Rail",
                            "description": "Timetables",
                            "tags": [],
                            "children": [],
                        },
                        {
                            "id": "transport-harbor",
                            "label": "Harbor",
                            "description": "Ports",
                            "tags": [],
                            "children": [],
                        },
                    ],
                }
            ],
            "assignments": [
                {"rel_path": "rail.txt", "region_ids": ["transport-rail"]},
                {
                    "rel_path": "harbor-a.txt",
                    "region_ids": ["transport-harbor"],
                },
                {
                    "rel_path": "harbor-b.txt",
                    "region_ids": ["transport-harbor"],
                },
            ],
        }
        notes = dissolve_singularities(payload)
        self.assertTrue(any("transport-rail" in n for n in notes))
        ids = {n["id"] for n in payload["regions"][0]["children"]}
        self.assertNotIn("transport-rail", ids)
        self.assertIn("transport-harbor", ids)
        by = {a["rel_path"]: a["region_ids"] for a in payload["assignments"]}
        self.assertEqual(by["rail.txt"], ["transport"])
        self.assertEqual(by["harbor-a.txt"], ["transport-harbor"])

    def test_split_revise_rewrites_members(self) -> None:
        payload = _payload()
        edit = {
            "action": "split",
            "description": "Transport stays the parent.",
            "children": [
                {
                    "id": "rail",
                    "label": "Rail",
                    "description": "Timetables and platforms.",
                    "member_paths": ["rail.txt"],
                },
                {
                    "id": "roads",
                    "label": "Roads",
                    "description": "Bike lanes and streets.",
                    "member_paths": ["clinic.txt"],
                },
            ],
        }
        # Pretend both files currently sit on transport so split is visible.
        for a in payload["assignments"]:
            if a["rel_path"] in {"rail.txt", "clinic.txt"}:
                a["region_ids"] = ["transport"]
        note = _apply_revise(payload, "transport", edit)
        self.assertIn("split", note)
        by = {a["rel_path"]: a["region_ids"][0] for a in payload["assignments"]}
        self.assertEqual(by["rail.txt"], "rail")
        self.assertEqual(by["clinic.txt"], "roads")


if __name__ == "__main__":
    unittest.main()
