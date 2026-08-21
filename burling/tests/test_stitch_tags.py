"""Unit tests for Pass B region assignment (no model)."""

from __future__ import annotations

import unittest

from collections import Counter

from burling.stitch_tags import (
    STITCH_MAX_TAGS,
    STITCH_SYSTEM,
    STITCH_SYSTEM_COMPACT,
    _cluster_prompt,
    _flatten_tag_map,
    _inventory_prompt,
    _region_index,
    assign_docs,
    place_leftover_tags,
    stitch_to_placements,
)
from burling.tag_concepts import (
    Cluster,
    Concept,
    cluster_concepts,
    content_tokens,
    expand_aliases,
    kebab_pref,
    normalize_concepts,
)


class StitchAssignTests(unittest.TestCase):
    def test_doc_multi_homes_via_tags(self) -> None:
        regions = [
            {
                "id": "mobile-lab",
                "label": "Mobile Lab",
                "tags": ["mobile-lab"],
                "children": [
                    {
                        "id": "trailer-compliance",
                        "label": "Trailer compliance",
                        "tags": ["trailer-acknowledgment"],
                        "children": [],
                    }
                ],
            },
            {
                "id": "purchasing",
                "label": "Purchasing",
                "tags": ["purchasing-quote"],
                "children": [],
            },
        ]
        tag_map = _flatten_tag_map(regions, {})
        idx = _region_index(regions)
        records = [
            {
                "doc_id": "1",
                "rel_path": "Trailer Acknowledgment_.docx",
                "tags": ["mobile-lab", "trailer-acknowledgment", "mystery"],
                "summary": "x",
            }
        ]
        assigned = assign_docs(records, tag_map, idx)[0]
        self.assertIn("mobile-lab", assigned["region_ids"])
        self.assertIn("trailer-compliance", assigned["region_ids"])
        self.assertEqual(assigned["unmatched_tags"], ["mystery"])
        self.assertEqual(assigned["top_level_regions"], ["mobile-lab"])

    def test_inventory_prompt_caps_long_tail(self) -> None:
        # 3515 unique tags is what broke Nemotron JSON; the prompt must stay small.
        counts = Counter({f"tag-{i}": (5 if i < 10 else 1) for i in range(400)})
        records = [{"rel_path": "a.pdf", "tags": ["tag-0"]}]
        prompt = _inventory_prompt(counts, records)
        listed = prompt.count("\n- tag-")
        self.assertLessEqual(listed, STITCH_MAX_TAGS + 1)  # +1 sample-doc line
        self.assertIn("omitted", prompt)

    def test_leftover_tags_inherit_related_region(self) -> None:
        # Model listed one representative; harness maps the sibling singleton.
        regions = [
            {
                "id": "curriculum",
                "label": "Curriculum",
                "tags": ["curriculum-admin"],
                "children": [],
            }
        ]
        tag_map = _flatten_tag_map(regions, {})
        counts = Counter({"curriculum-admin": 10, "curriculum_administration": 1})
        placed = place_leftover_tags(counts, tag_map, regions)
        self.assertEqual(placed, 1)
        self.assertEqual(tag_map["curriculum_administration"], "curriculum")

    def test_unrelated_leftover_goes_to_needs_review(self) -> None:
        regions = [
            {"id": "purchasing", "label": "Purchasing", "tags": ["purchasing-quote"], "children": []}
        ]
        tag_map = _flatten_tag_map(regions, {})
        counts = Counter({"purchasing-quote": 5, "mystery-xyz": 1})
        place_leftover_tags(counts, tag_map, regions)
        self.assertEqual(tag_map["mystery-xyz"], "needs-review")
        self.assertTrue(any(n.get("id") == "needs-review" for n in regions))


class NormalizeClusterTests(unittest.TestCase):
    def test_kebab_merges_underscore_and_hyphen(self) -> None:
        self.assertEqual(kebab_pref("curriculum_admin"), "curriculum-admin")
        self.assertEqual(kebab_pref("curriculum-admin"), "curriculum-admin")

    def test_token_set_merges_word_order_and_admin_stem(self) -> None:
        # ISO equivalence: same concept, different surface form.
        self.assertEqual(
            content_tokens("cte-middle-school"),
            content_tokens("middle_school_cte"),
        )
        self.assertEqual(
            content_tokens("curriculum-admin"),
            content_tokens("curriculum-administration"),
        )

    def test_normalize_collapses_curriculum_spellings(self) -> None:
        counts = Counter(
            {
                "curriculum_admin": 88,
                "curriculum-admin": 45,
                "curriculum-administration": 13,
                "purchasing-quote": 19,
            }
        )
        docs = {
            "curriculum_admin": ["a", "b", "c"],
            "curriculum-admin": ["c", "d"],
            "curriculum-administration": ["e"],
            "purchasing-quote": ["q"],
        }
        concepts = normalize_concepts(counts, docs)
        preferred = {c.preferred: c for c in concepts}
        self.assertIn("curriculum-admin", preferred)
        self.assertEqual(
            set(preferred["curriculum-admin"].aliases),
            {"curriculum_admin", "curriculum-admin", "curriculum-administration"},
        )
        self.assertEqual(len(concepts), 2)

    def test_cluster_joins_coherent_cooccurring_concepts(self) -> None:
        # Same docs + shared token "pathful" → one cluster.
        a = Concept("pathful", ["pathful"], 4, frozenset("wxyz"))
        b = Concept("pathful-integration", ["pathful-integration"], 3, frozenset("wxy"))
        clusters = cluster_concepts([a, b], min_jaccard=0.25, min_shared=2)
        self.assertEqual(len(clusters), 1)
        self.assertEqual(clusters[0].label, "pathful")
        self.assertEqual({m.preferred for m in clusters[0].members}, {"pathful", "pathful-integration"})

    def test_cluster_does_not_merge_unrelated_cooccurrence(self) -> None:
        # These co-occur (same memos) but share no content token — RT, not the same concept.
        a = Concept("curriculum-admin", ["curriculum_admin"], 5, frozenset("abcde"))
        b = Concept("work-email", ["work_email_or_memo"], 4, frozenset("abcd"))
        clusters = cluster_concepts([a, b], min_jaccard=0.25, min_shared=2)
        self.assertEqual(len(clusters), 2)

    def test_expand_aliases_maps_every_spelling(self) -> None:
        cluster = Cluster(
            label="curriculum-admin",
            members=[],
            count=3,
            aliases=["curriculum_admin", "curriculum-admin", "curriculum-administration"],
        )
        tag_map = {"curriculum-admin": "curriculum"}
        added = expand_aliases(tag_map, [cluster])
        self.assertEqual(added, 2)
        self.assertEqual(tag_map["curriculum_admin"], "curriculum")
        self.assertEqual(tag_map["curriculum-administration"], "curriculum")

    def test_cluster_prompt_lists_labels_not_raw_inventory(self) -> None:
        clusters = [
            Cluster(
                label="curriculum-admin",
                members=[],
                count=10,
                aliases=["curriculum_admin", "curriculum-admin"],
            ),
            Cluster(label="rare-singleton", members=[], count=1, aliases=["rare-singleton"]),
        ]
        prompt = _cluster_prompt(clusters, [{"rel_path": "a.pdf", "tags": ["curriculum_admin"]}])
        self.assertIn("curriculum-admin: 10", prompt)
        self.assertNotIn("rare-singleton", prompt)
        self.assertIn("concept clusters", prompt)

    def test_stitch_to_placements_uses_child_as_function(self) -> None:
        # Sunburst Program = top-level; Function = child. No invented facets.
        regions = [
            {
                "id": "curriculum-and-instruction",
                "label": "Curriculum",
                "tags": ["curriculum-admin"],
                "children": [
                    {
                        "id": "curriculum-alignment",
                        "label": "Alignment",
                        "tags": ["curriculum-alignment"],
                        "children": [],
                    }
                ],
            }
        ]
        idx = _region_index(regions)
        assignments = [
            {
                "doc_id": "1",
                "rel_path": "pacing.pdf",
                "region_ids": ["curriculum-alignment"],
                "top_level_regions": ["curriculum-and-instruction"],
                "matched_tags": ["curriculum-alignment"],
                "summary": "pacing guide",
            },
            {
                "doc_id": "2",
                "rel_path": "untagged.pdf",
                "region_ids": [],
                "top_level_regions": [],
                "matched_tags": [],
                "summary": "",
            },
        ]
        placed = stitch_to_placements(assignments, idx)
        self.assertEqual(placed[0]["program"], ["curriculum-and-instruction"])
        self.assertEqual(placed[0]["function"], ["curriculum-alignment"])
        self.assertEqual(placed[0]["audience"], ["unmapped"])
        self.assertFalse(placed[0]["needs_review"])
        self.assertEqual(placed[1]["program"], ["unmapped"])
        self.assertTrue(placed[1]["needs_review"])

    def test_stitch_prompt_lets_tree_emerge(self) -> None:
        # "handoff map for a successor" forced a transition story on every tree.
        lowered = STITCH_SYSTEM.lower()
        self.assertNotIn("for a successor", lowered)
        self.assertNotIn("handoff map", lowered)
        self.assertIn("topic → subtopic →", lowered)
        compact = STITCH_SYSTEM_COMPACT.lower()
        self.assertNotIn("for a successor", compact)
        self.assertIn("tag frequency", compact)


if __name__ == "__main__":
    unittest.main()
