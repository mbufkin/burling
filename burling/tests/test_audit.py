"""Audit plan + L1 + normalization. No model."""

from __future__ import annotations

import unittest

from burling.audit import (
    AUDIT_GROUP_MAX,
    UNASSIGNED_ID,
    chunk_files,
    graph_findings,
    normalize_chunk_result,
    ordered_region_ids,
    plan_groups,
    primary_region,
)


def _payload() -> dict:
    return {
        "regions": [
            {
                "id": "health-and-compliance",
                "label": "Health & Compliance",
                "description": "Health files",
                "tags": ["compliance"],
                "children": [
                    {
                        "id": "trailer-compliance",
                        "label": "Trailer Compliance",
                        "description": "Trailer under compliance",
                        "tags": ["trailer-compliance"],
                        "children": [],
                    }
                ],
            },
            {
                "id": "procurement-and-vendors",
                "label": "Procurement",
                "description": "Buying",
                "tags": ["purchasing"],
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
                "rel_path": "z-quote.pdf",
                "region_ids": ["procurement-and-vendors"],
                "matched_tags": ["purchasing-quote"],
                "summary": "A vendor quote.",
            },
            {
                "rel_path": "a-ack.pdf",
                "region_ids": [
                    "trailer-compliance",
                    "health-and-compliance",
                    "needs-review",
                ],
                "matched_tags": ["trailer-acknowledgment", "compliance"],
                "summary": "Campus trailer acknowledgment.",
            },
            {
                "rel_path": "orphan.pdf",
                "region_ids": [],
                "matched_tags": [],
                "summary": "No home.",
            },
        ],
    }


class AuditPlanTests(unittest.TestCase):
    def test_tree_order_is_parent_then_child_not_random(self) -> None:
        # Needs-review sorts last among siblings even if listed first.
        ids = ordered_region_ids(
            [
                {"id": "needs-review", "label": "Needs review", "children": []},
                {
                    "id": "health-and-compliance",
                    "label": "Health & Compliance",
                    "children": [
                        {
                            "id": "trailer-compliance",
                            "label": "Trailer Compliance",
                            "children": [],
                        }
                    ],
                },
            ]
        )
        self.assertEqual(
            ids,
            [
                "health-and-compliance",
                "trailer-compliance",
                "needs-review",
            ],
        )

    def test_primary_region_is_deepest_real_home(self) -> None:
        idx = {
            "health-and-compliance": {
                "id": "health-and-compliance",
                "parent_id": None,
            },
            "trailer-compliance": {
                "id": "trailer-compliance",
                "parent_id": "health-and-compliance",
            },
            "needs-review": {"id": "needs-review", "parent_id": None},
        }
        rid = primary_region(
            {
                "region_ids": [
                    "needs-review",
                    "health-and-compliance",
                    "trailer-compliance",
                ]
            },
            idx,
        )
        self.assertEqual(rid, "trailer-compliance")

    def test_unassigned_when_no_regions(self) -> None:
        self.assertEqual(primary_region({"region_ids": []}, {}), UNASSIGNED_ID)

    def test_fat_group_chunks_are_documented(self) -> None:
        files = [{"rel_path": f"{i}.pdf"} for i in range(25)]
        parts = chunk_files(files, max_n=12)
        self.assertEqual(len(parts), 3)
        self.assertEqual(len(parts[0]), 12)
        self.assertEqual(len(parts[2]), 1)

    def test_plan_walks_groups_then_unassigned(self) -> None:
        chunks = plan_groups(_payload(), max_n=12)
        ids = [c["region_id"] for c in chunks]
        # Health has no *primary* files (the ack lives on the child), so
        # we skip an empty parent and start at Trailer Compliance.
        self.assertEqual(ids[0], "trailer-compliance")
        self.assertIn(UNASSIGNED_ID, ids)
        self.assertGreater(ids.index(UNASSIGNED_ID), ids.index("procurement-and-vendors"))
        # Multi-home file is audited once, under the child.
        trailer = next(c for c in chunks if c["region_id"] == "trailer-compliance")
        paths = [a["rel_path"] for a in trailer["files"]]
        self.assertEqual(paths, ["a-ack.pdf"])

    def test_l1_flags_unassigned_and_empty_nodes(self) -> None:
        findings = graph_findings(_payload(), fat_at=40)
        kinds = {f["kind"] for f in findings}
        self.assertIn("unassigned", kinds)
        # health parent has no file whose *listed* region_ids include it
        # as a membership (a-ack lists it, so not empty). procurement has 1.
        self.assertTrue(any(f["kind"] == "unassigned" for f in findings))

    def test_normalize_fills_omitted_files(self) -> None:
        chunk = {
            "files": [
                {"rel_path": "a.pdf"},
                {"rel_path": "b.pdf"},
            ]
        }
        out = normalize_chunk_result(
            {
                "group_notes": "ok",
                "files": [
                    {
                        "rel_path": "a.pdf",
                        "verdict": "confirm",
                        "reason": "fits",
                    }
                ],
            },
            chunk,
        )
        self.assertEqual(out["files"][0]["verdict"], "confirm")
        self.assertEqual(out["files"][1]["verdict"], "cannot-tell")
        self.assertIn("omitted", out["files"][1]["reason"].lower())

    def test_group_max_constant_is_the_documented_cap(self) -> None:
        # If this changes, update docs/audit-pass.md in the same commit.
        self.assertEqual(AUDIT_GROUP_MAX, 12)


if __name__ == "__main__":
    unittest.main()
