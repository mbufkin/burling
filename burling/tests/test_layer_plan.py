"""Layered file plan: 3-layer tags, roll-up, max-3 browse tree. No model."""

from __future__ import annotations

import unittest

from burling.file_plan import UNMAPPED_ID
from burling.layer_plan import (
    FAT_MIN,
    apply_rollup,
    build_regions,
    coerce_main,
    collapse_home,
    folder_segments,
    kebab,
    node_id,
    normalize_layers,
    prefix_counts,
    rollup_user_prompt,
)


class NormalizeLayersTests(unittest.TestCase):
    def test_kebab_and_drop_banned_main(self) -> None:
        # Channel/year cannot be a browse head — Navy files year inside the RN.
        out = normalize_layers(
            {"main": "Usenet 1993", "sub": "hockey", "detail": "playoffs", "summary": "x"}
        )
        self.assertEqual(out["main"], "")
        self.assertEqual(out["sub"], "")
        self.assertEqual(out["detail"], "")

    def test_keeps_workplace_path_and_dedupes(self) -> None:
        out = normalize_layers(
            {
                "main": "Technology",
                "sub": "technology",
                "detail": "Git",
                "summary": "Repo",
                "reasoning": "1. systems. 2. source control. 3. git.",
            }
        )
        self.assertEqual(out["main"], "technology")
        self.assertEqual(out["sub"], "git")
        self.assertEqual(out["detail"], "")
        self.assertIn("systems", out["reasoning"])

    def test_hardware_aliases_to_facilities(self) -> None:
        # Physical gear is a facilities sub, never a competing main.
        self.assertEqual(coerce_main("hardware"), "facilities")
        self.assertEqual(normalize_layers({"main": "Hardware", "sub": "printers"})["main"], "facilities")

    def test_nonwork_aliases_to_personal(self) -> None:
        # Employee-exit: isolate so a human can delete it.
        self.assertEqual(coerce_main("sports"), "personal")
        self.assertEqual(coerce_main("faith"), "personal")
        self.assertEqual(normalize_layers({"main": "personal", "sub": "photos"})["main"], "personal")

    def test_unknown_main_does_not_invent_a_series(self) -> None:
        self.assertEqual(coerce_main("cryptography"), "")
        self.assertEqual(normalize_layers({"main": "cryptography", "sub": "ripem"})["main"], "")


class FolderSegmentTests(unittest.TestCase):
    def test_rollup_parent_caps_detail_as_facet(self) -> None:
        # Housekeeping / Cleaning / Kitchen is 3 folders; grease-trap is layer 4.
        folders, facet = folder_segments(
            "cleaning",
            "kitchen",
            "grease-trap",
            {"cleaning": "housekeeping"},
        )
        self.assertEqual(folders, ["housekeeping", "cleaning", "kitchen"])
        self.assertEqual(facet, "grease-trap")

    def test_no_parent_allows_three_tagged_folders(self) -> None:
        folders, facet = folder_segments("sports", "hockey", "playoffs", {})
        self.assertEqual(folders, ["sports", "hockey", "playoffs"])
        self.assertIsNone(facet)

    def test_empty_main_is_unmapped(self) -> None:
        folders, facet = folder_segments("", "hockey", "", {})
        self.assertEqual(folders, [UNMAPPED_ID])
        self.assertIsNone(facet)


class CollapseTests(unittest.TestCase):
    def test_mixed_fat_parent_keeps_children(self) -> None:
        # Sports has hockey and baseball, both ≥ 8 → Sports/Hockey is a folder.
        hockey = ["sports", "hockey"]
        baseball = ["sports", "baseball"]
        paths = [hockey] * 10 + [baseball] * 10
        counts = prefix_counts(paths)
        self.assertEqual(collapse_home(hockey, counts), ["sports", "hockey"])

    def test_fat_unmixed_child_still_opens(self) -> None:
        # All sports are hockey, and hockey is fat → Sports/Hockey.
        # Mixed is the roll-up gate, not this cut.
        paths = [["sports", "hockey"]] * 12
        counts = prefix_counts(paths)
        self.assertEqual(collapse_home(["sports", "hockey"], counts), ["sports", "hockey"])

    def test_thin_child_sits_on_parent(self) -> None:
        hockey = ["sports", "hockey"]
        bowling = ["sports", "bowling"]
        paths = [hockey] * 12 + [bowling] * 2
        counts = prefix_counts(paths)
        self.assertEqual(collapse_home(bowling, counts, fat_min=FAT_MIN), ["sports"])
        self.assertEqual(collapse_home(hockey, counts, fat_min=FAT_MIN), ["sports", "hockey"])

    def test_thin_root_still_exists(self) -> None:
        # Three medicine files still get a Medicine drawer, not Unmapped.
        paths = [["medicine"]] * 3 + [["sports", "hockey"]] * 10 + [["sports", "baseball"]] * 10
        counts = prefix_counts(paths)
        self.assertEqual(collapse_home(["medicine"], counts), ["medicine"])


class RollupTests(unittest.TestCase):
    def test_merges_sibling_mains(self) -> None:
        mapping = apply_rollup(
            ["cleaning", "cooking", "hockey"],
            {
                "parents": [
                    {
                        "id": "housekeeping",
                        "label": "Housekeeping",
                        "children": ["cleaning", "cooking"],
                    }
                ]
            },
        )
        self.assertEqual(mapping["cleaning"], "housekeeping")
        self.assertEqual(mapping["cooking"], "housekeeping")
        self.assertEqual(mapping["hockey"], "hockey")

    def test_rejects_vague_and_banned_parents(self) -> None:
        mapping = apply_rollup(
            ["hockey", "baseball"],
            {
                "parents": [
                    {"id": "discussion", "children": ["hockey", "baseball"]},
                    {"id": "usenet-1993", "children": ["hockey", "baseball"]},
                ]
            },
        )
        self.assertEqual(mapping["hockey"], "hockey")
        self.assertEqual(mapping["baseball"], "baseball")

    def test_rejects_single_child_parent(self) -> None:
        mapping = apply_rollup(
            ["hockey", "crypto"],
            {"parents": [{"id": "sports", "children": ["hockey"]}]},
        )
        self.assertEqual(mapping["hockey"], "hockey")

    def test_prompt_lists_mains_not_subs(self) -> None:
        # Best practice: the question is "group these mains." Hockey is a
        # sub here; putting it in the prompt taught the 30B to roll it up.
        records = [
            {"main": "sports", "sub": "hockey"},
            {"main": "sports", "sub": "baseball"},
            {"main": "medicine", "sub": "oncology"},
            {"main": "faith", "sub": "christianity"},
        ]
        mains, user = rollup_user_prompt(records)
        self.assertEqual(set(mains), {"sports", "medicine", "faith"})
        self.assertIn("MAINS (count):", user)
        self.assertIn("- sports: 2", user)
        self.assertNotIn("hockey", user)
        self.assertNotIn("baseball", user)
        self.assertNotIn("oncology", user)
        self.assertNotIn("christianity", user)


class BuildRegionsTests(unittest.TestCase):
    def test_one_home_and_rollup_tree(self) -> None:
        records = []
        for i in range(10):
            records.append(
                {"rel_path": f"c{i}.txt", "main": "cleaning", "sub": "kitchen", "detail": "sink"}
            )
        for i in range(10):
            records.append(
                {"rel_path": f"k{i}.txt", "main": "cooking", "sub": "recipes", "detail": ""}
            )
        parent_of = {"cleaning": "housekeeping", "cooking": "housekeeping"}
        payload = build_regions(records, parent_of)
        self.assertEqual(payload["meta"]["homes_mean"], 1.0)
        self.assertEqual(payload["meta"]["unmapped"], 0)
        ids = {n["id"] for n in payload["regions"]}
        self.assertIn("housekeeping", ids)
        # Depth 3: housekeeping / cleaning / kitchen. detail=sink is facet.
        kitchen = None
        for n in payload["regions"]:
            if n["id"] == "housekeeping":
                for c in n["children"]:
                    if c["id"] == "housekeeping--cleaning":
                        kitchen = c["children"]
        self.assertTrue(kitchen)
        self.assertEqual(kitchen[0]["id"], "housekeeping--cleaning--kitchen")
        row = next(a for a in payload["assignments"] if a["rel_path"] == "c0.txt")
        self.assertEqual(row["region_ids"], ["housekeeping--cleaning--kitchen"])
        self.assertEqual(row["facet"], "sink")
        self.assertEqual(len(row["region_ids"]), 1)

    def test_node_ids_do_not_collide(self) -> None:
        self.assertEqual(node_id(["housekeeping", "cleaning"]), "housekeeping--cleaning")
        self.assertEqual(kebab("PC Hardware"), "pc-hardware")


if __name__ == "__main__":
    unittest.main()
