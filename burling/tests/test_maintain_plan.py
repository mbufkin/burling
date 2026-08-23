"""Folder-maintenance pass: combine is a supervisor step, not filing.

Seams (public interface only):
- coerce_merges — model proposes groups; code keeps or drops them
- folders_needing_maintain — only fat + mixed parents get a call
- apply_merges — accepted groups rehome through WalkState
- walk_one — a combine verb while holding one letter does not move siblings
"""

from __future__ import annotations

import unittest

from burling.layer_plan import FAT_MIN
from burling.walk_plan import WalkState, walk_one


class CoerceMergesTests(unittest.TestCase):
    def test_keeps_two_existing_siblings(self) -> None:
        from burling.maintain_plan import coerce_merges

        kept = coerce_merges(
            {
                "merges": [
                    {
                        "merge": ["windows", "macos"],
                        "into": "operating-systems",
                    }
                ]
            },
            ["windows", "macos", "printers"],
        )
        self.assertEqual(len(kept), 1)
        self.assertEqual(set(kept[0].merge), {"windows", "macos"})
        self.assertEqual(kept[0].into, "operating-systems")

    def test_drops_a_one_child_merge(self) -> None:
        from burling.maintain_plan import coerce_merges

        kept = coerce_merges(
            {"merges": [{"merge": ["windows"], "into": "operating-systems"}]},
            ["windows", "macos"],
        )
        self.assertEqual(kept, [])

    def test_drops_merge_of_every_sibling(self) -> None:
        # Dumping the whole folder into one leftover is a rename, not a combine.
        from burling.maintain_plan import coerce_merges

        kept = coerce_merges(
            {
                "merges": [
                    {
                        "merge": ["windows", "macos", "printers"],
                        "into": "stuff",
                    }
                ]
            },
            ["windows", "macos", "printers"],
        )
        self.assertEqual(kept, [])

    def test_empty_merges_is_correct(self) -> None:
        from burling.maintain_plan import coerce_merges

        self.assertEqual(coerce_merges({"merges": []}, ["hockey", "invoices"]), [])


class FatMixedGateTests(unittest.TestCase):
    def test_skips_thin_or_unmixed_parents(self) -> None:
        from burling.maintain_plan import folders_needing_maintain

        state = WalkState()
        # 7 files, two children — thin, skip.
        for i in range(4):
            state.homes[f"h{i}.txt"] = ["personal", "hockey"]
        for i in range(3):
            state.homes[f"b{i}.txt"] = ["personal", "baseball"]
        # Fat but one child — unmixed, skip.
        for i in range(FAT_MIN):
            state.homes[f"inv{i}.txt"] = ["finance", "invoices"]
        self.assertEqual(folders_needing_maintain(state), [])

    def test_lists_a_fat_mixed_parent(self) -> None:
        from burling.maintain_plan import folders_needing_maintain

        state = WalkState()
        for i in range(5):
            state.homes[f"h{i}.txt"] = ["personal", "hockey"]
        for i in range(5):
            state.homes[f"b{i}.txt"] = ["personal", "baseball"]
        found = folders_needing_maintain(state)
        self.assertEqual(found, [["personal"]])


class ApplyMergesTests(unittest.TestCase):
    def test_rehomes_accepted_siblings(self) -> None:
        from burling.maintain_plan import Merge, apply_merges

        state = WalkState()
        state.homes = {
            "w.txt": ["technology", "windows"],
            "m.txt": ["technology", "macos"],
            "n.txt": ["technology", "networks"],
        }
        moved = apply_merges(
            state,
            ["technology"],
            [Merge(merge=("windows", "macos"), into="operating-systems")],
        )
        self.assertEqual(moved, 2)
        self.assertEqual(state.homes["w.txt"], ["technology", "operating-systems", "windows"])
        self.assertEqual(state.homes["m.txt"], ["technology", "operating-systems", "macos"])
        self.assertEqual(state.homes["n.txt"], ["technology", "networks"])
        self.assertEqual(len(state.combines), 1)


class FilingDoesNotCombineTests(unittest.TestCase):
    def test_combine_in_child_json_does_not_move_siblings(self) -> None:
        # Combine is a later supervisor pass. Holding one letter must not
        # rewrite the tree the clerk already walked.
        state = WalkState()
        state.homes = {
            "w.txt": ["technology", "windows"],
            "m.txt": ["technology", "macos"],
        }
        state.records = {
            "w.txt": {"rel_path": "w.txt", "status": "done", "main": "technology", "sub": "windows"},
            "m.txt": {"rel_path": "m.txt", "status": "done", "main": "technology", "sub": "macos"},
        }

        def main(**_kw: object) -> dict:
            return {"main": "technology", "summary": "linux notes"}

        def child(**_kw: object) -> dict:
            return {
                "action": "combine",
                "merge": ["windows", "macos"],
                "into": "operating-systems",
                "name": "operating-systems",
            }

        home = walk_one(
            state,
            rel_path="l.txt",
            text="Installing Debian on the lab tower.",
            choose_main=main,
            choose_child=child,
        )
        self.assertEqual(home, ["technology", "operating-systems"])
        self.assertEqual(state.homes["w.txt"], ["technology", "windows"])
        self.assertEqual(state.homes["m.txt"], ["technology", "macos"])
        self.assertEqual(state.combines, [])


if __name__ == "__main__":
    unittest.main()
