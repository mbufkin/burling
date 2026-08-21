"""Method C browse graph: two parents only when justified."""

from __future__ import annotations

import unittest

from burling.browse_graph import induce_browse_graph
from burling.map_html import browse_sunburst_payload


def _payload(regions, assignments, records):
    return regions, {
        "regions": regions,
        "assignments": assignments,
    }, records


class BrowseGraphTests(unittest.TestCase):
    def test_second_parent_requires_token_overlap_and_enough_docs(self) -> None:
        # Trailer-compliance sits under both topics; PD overlap is ignored
        # (no shared content token) even if many PD files mention a trailer.
        regions = [
            {
                "id": "health-and-compliance",
                "label": "Health & Compliance",
                "tags": ["health", "compliance"],
                "children": [
                    {
                        "id": "lab-results",
                        "label": "Lab results",
                        "tags": ["lab-results"],
                        "children": [],
                    }
                ],
            },
            {
                "id": "professional-development",
                "label": "Professional Development",
                "tags": ["professional-development"],
                "children": [],
            },
        ]
        docs = [f"t{i}.pdf" for i in range(6)]
        pd_only = [f"pd{i}.pdf" for i in range(6)]
        assignments = []
        records = []
        for i, rel in enumerate(docs):
            assignments.append(
                {
                    "rel_path": rel,
                    "region_ids": ["health-and-compliance", "lab-results"],
                    "top_level_regions": ["health-and-compliance"],
                    "matched_tags": ["trailer-compliance", "lab-results"],
                }
            )
            records.append({"rel_path": rel, "tags": ["trailer-compliance", "lab-results"]})
        for rel in pd_only:
            assignments.append(
                {
                    "rel_path": rel,
                    "region_ids": ["professional-development"],
                    "top_level_regions": ["professional-development"],
                    "matched_tags": ["professional-development"],
                }
            )
            records.append({"rel_path": rel, "tags": ["professional-development"]})
        graph = induce_browse_graph(
            {"regions": regions, "assignments": assignments},
            tag_records=records,
            min_split=5,
        )
        by = {n.id: n for n in graph}
        self.assertIn("mobile-lab", by, "trailer family is a missing mental-model topic")
        compound = by.get("trailer-compliance") or next(
            (n for n in graph if "trailer" in n.id and n.kind != "topic"), None
        )
        self.assertIsNotNone(compound)
        self.assertIn("health-and-compliance", compound.broader)
        self.assertIn("mobile-lab", compound.broader)
        self.assertNotIn("professional-development", compound.broader)
        self.assertGreaterEqual(len(compound.docs), 5)

    def test_singularity_does_not_mint_a_child(self) -> None:
        regions = [
            {
                "id": "health-and-compliance",
                "label": "Health & Compliance",
                "tags": ["compliance"],
                "children": [],
            }
        ]
        assignments = [
            {
                "rel_path": "one.pdf",
                "region_ids": ["health-and-compliance"],
                "top_level_regions": ["health-and-compliance"],
                "matched_tags": ["trailer-compliance"],
            }
        ]
        records = [{"rel_path": "one.pdf", "tags": ["trailer-compliance"]}]
        graph = induce_browse_graph(
            {"regions": regions, "assignments": assignments},
            tag_records=records,
            min_split=5,
        )
        self.assertFalse(
            any(n.kind != "topic" and "trailer" in n.id for n in graph),
            "one file is a singularity — no Trailer compliance folder",
        )

    def test_sunburst_emits_two_paths_for_one_concept(self) -> None:
        from burling.browse_graph import GraphNode

        nodes = [
            GraphNode(id="compliance", label="Compliance", kind="topic", docs=frozenset({"a.pdf", "b.pdf"})),
            GraphNode(id="trailer", label="Trailer", kind="topic", docs=frozenset({"a.pdf", "b.pdf"})),
            GraphNode(
                id="trailer-compliance",
                label="Trailer compliance",
                kind="subtopic",
                broader=["compliance", "trailer"],
                docs=frozenset({"a.pdf", "b.pdf"}),
            ),
        ]
        fig = browse_sunburst_payload(nodes)
        self.assertIn("compliance/trailer-compliance", fig["ids"])
        self.assertIn("trailer/trailer-compliance", fig["ids"])
        self.assertEqual(fig["maxdepth"], 3)
        # Same concept id in both slices.
        metas = [c for c in fig["customdata"] if "trailer-compliance" in str(c)]
        self.assertGreaterEqual(len(metas), 2)
        # Plotly sunburst with branchvalues=total stays blank if a
        # parent value is not the sum of its children.
        from collections import defaultdict

        kids: dict[str, list[int]] = defaultdict(list)
        for i, parent in enumerate(fig["parents"]):
            if parent:
                kids[parent].append(i)
        for pid, cidx in kids.items():
            pi = fig["ids"].index(pid)
            self.assertEqual(
                fig["values"][pi],
                sum(fig["values"][j] for j in cidx),
                f"parent {pid} value != sum(children)",
            )


if __name__ == "__main__":
    unittest.main()
