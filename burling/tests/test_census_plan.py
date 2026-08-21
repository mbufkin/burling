"""Census organize: roster + groups + need_files. No model."""

from __future__ import annotations

import unittest

from burling.census_plan import (
    apply_groups,
    coerce_groups,
    coerce_need_files,
    counts_for,
    counts_under_root,
    mains_user_prompt,
    pick_dive_root,
    roster_lines,
    sources_of_root,
    subs_user_prompt,
)


def _rec(rel: str, main: str, sub: str = "", detail: str = "", summary: str = "") -> dict:
    return {
        "rel_path": rel,
        "main": main,
        "sub": sub,
        "detail": detail,
        "summary": summary,
        "status": "done",
    }


class RosterTests(unittest.TestCase):
    def test_roster_is_filename_plus_path_plus_summary(self) -> None:
        # Hashed inbox names are opaque; tags and the existing summary are the signal.
        lines = roster_lines(
            [_rec("aa.txt", "Faith", "Atheism", "college", "Ivy League atheism rates.")]
        )
        self.assertEqual(len(lines), 1)
        self.assertIn("aa.txt", lines[0])
        self.assertIn("faith/atheism/college", lines[0])
        self.assertIn("Ivy League", lines[0])

    def test_counts_skip_empty_and_can_filter_by_main(self) -> None:
        recs = [
            _rec("a.txt", "hardware", "printer"),
            _rec("b.txt", "hardware", "printer"),
            _rec("c.txt", "faith", "atheism"),
            _rec("d.txt", "hardware", ""),
        ]
        self.assertEqual(counts_for(recs, "main"), [("hardware", 3), ("faith", 1)])
        self.assertEqual(counts_for(recs, "sub", main="hardware"), [("printer", 2)])

    def test_mains_prompt_does_not_leak_subs_or_filenames(self) -> None:
        # Showing hockey on a main call is what made the 30B greedy.
        recs = [
            _rec("aa.txt", "hardware", "printer"),
            _rec("bb.txt", "faith", "atheism"),
            _rec("cc.txt", "sports", "hockey", "leafs", "Tonight's score."),
        ]
        prompt = mains_user_prompt(len(recs), counts_for(recs, "main"))
        self.assertIn("- hardware: 1", prompt)
        self.assertIn("- sports: 1", prompt)
        self.assertNotIn("hockey", prompt)
        self.assertNotIn("atheism", prompt)
        self.assertNotIn(".txt", prompt)
        self.assertNotIn("Tonight", prompt)


    def test_subs_prompt_states_the_bush_and_the_bans(self) -> None:
        prompt = subs_user_prompt(
            "computing",
            173,
            [("automotive", 14), ("macintosh", 3), ("mac", 4)],
        )
        self.assertIn("173 files, 3 unique subs", prompt)
        self.assertIn("cannot walk 3 drawers", prompt)
        self.assertIn("spelling variants", prompt)
        self.assertIn("Do not dump the leftover into computing or misc", prompt)
        self.assertNotIn("aa.txt", prompt)


class MappedRootTests(unittest.TestCase):
    def test_subs_under_science_are_the_union(self) -> None:
        # astronomy/stars and spaceflight/shuttle share a parent after the fold.
        recs = [
            _rec("a.txt", "astronomy", "stars"),
            _rec("b.txt", "astronomy", "stars"),
            _rec("c.txt", "spaceflight", "shuttle"),
            _rec("d.txt", "faith", "atheism"),
        ]
        mapping = apply_groups(
            ["astronomy", "spaceflight", "faith"],
            [(("astronomy", "spaceflight"), "science")],
        )
        self.assertEqual(mapping["astronomy"], "science")
        self.assertEqual(
            counts_under_root(recs, mapping, "science"),
            [("stars", 2), ("shuttle", 1)],
        )
        self.assertEqual(sources_of_root(mapping, "science"), ["astronomy", "spaceflight"])
        self.assertEqual(pick_dive_root(mapping, recs), "science")

    def test_small_merge_beats_fat_bush_when_source_count_ties(self) -> None:
        # hardware+computers is huge; astronomy+spaceflight is the question.
        recs = [
            *[_rec(f"h{i}.txt", "hardware", "printer") for i in range(8)],
            _rec("a.txt", "astronomy", "stars"),
            _rec("s.txt", "spaceflight", "shuttle"),
        ]
        mapping = apply_groups(
            ["hardware", "computers", "astronomy", "spaceflight"],
            [
                (("hardware", "computers"), "hardware"),
                (("astronomy", "spaceflight"), "science"),
            ],
        )
        self.assertEqual(pick_dive_root(mapping, recs), "science")

    def test_named_dive_overrides(self) -> None:
        recs = [_rec("a.txt", "hardware", "printer"), _rec("b.txt", "faith", "atheism")]
        mapping = {"hardware": "hardware", "faith": "faith"}
        self.assertEqual(pick_dive_root(mapping, recs, named="faith"), "faith")

    def test_named_dive_follows_the_fold(self) -> None:
        recs = [_rec("a.txt", "hardware", "printer")]
        mapping = {"hardware": "tech", "computers": "tech"}
        self.assertEqual(pick_dive_root(mapping, recs, named="hardware"), "tech")


class CoerceGroupsTests(unittest.TestCase):
    def test_keeps_two_existing_mains(self) -> None:
        groups = coerce_groups(
            {
                "groups": [
                    {"merge": ["astronomy", "spaceflight", "space"], "into": "space-science"}
                ]
            },
            ["astronomy", "spaceflight", "space", "faith"],
            leave_one=False,
        )
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0][1], "space-science")
        self.assertEqual(set(groups[0][0]), {"astronomy", "spaceflight", "space"})

    def test_drops_vague_into_and_unknown_children(self) -> None:
        groups = coerce_groups(
            {"groups": [{"merge": ["astronomy", "not-a-main"], "into": "misc"}]},
            ["astronomy", "faith"],
            leave_one=False,
        )
        self.assertEqual(groups, [])

    def test_leave_one_rejects_merge_everyone(self) -> None:
        # Subs: merging the whole cabinet is a rename, not a combine.
        dropped = coerce_groups(
            {"groups": [{"merge": ["hockey", "baseball"], "into": "sports"}]},
            ["hockey", "baseball"],
            leave_one=True,
        )
        self.assertEqual(dropped, [])
        kept = coerce_groups(
            {"groups": [{"merge": ["hockey", "baseball"], "into": "ball-sports"}]},
            ["hockey", "baseball", "cycling"],
            leave_one=True,
        )
        self.assertEqual(len(kept), 1)


class NeedFilesTests(unittest.TestCase):
    def test_unknown_and_over_limit_are_dropped(self) -> None:
        known = [f"{i}.txt" for i in range(12)]
        got = coerce_need_files(
            {"need_files": ["1.txt", "missing.txt", "2.txt", "1.txt"] + [f"{i}.txt" for i in range(12)]},
            known,
            limit=3,
        )
        self.assertEqual(got, ["1.txt", "2.txt", "0.txt"])


class ApplyGroupsTests(unittest.TestCase):
    def test_unmentioned_ids_stay_themselves(self) -> None:
        mapping = apply_groups(
            ["faith", "astronomy", "space"],
            [(("astronomy", "space"), "space-science")],
        )
        self.assertEqual(mapping["faith"], "faith")
        self.assertEqual(mapping["astronomy"], "space-science")
        self.assertEqual(mapping["space"], "space-science")


if __name__ == "__main__":
    unittest.main()
