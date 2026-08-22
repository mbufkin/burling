"""Supervisor combine after a letter is home. No model."""

from __future__ import annotations

import unittest

from burling.maintain_plan import (
    apply_merges,
    coerce_merges,
    maintain_after_place,
    parent_is_maintainable,
)
from burling.walk_plan import WalkState


def _state(*homes: tuple[str, list[str]]) -> WalkState:
    state = WalkState()
    for rel, home in homes:
        state.homes[rel] = list(home)
        state.records[rel] = {
            "rel_path": rel,
            "main": home[0] if home else "",
            "sub": home[1] if len(home) > 1 else "",
            "detail": home[2] if len(home) > 2 else "",
            "status": "done",
        }
    return state


class CoerceMergesTests(unittest.TestCase):
    def test_one_id_group_is_dropped(self) -> None:
        # A one-child group is an invent in disguise.
        groups = coerce_merges(
            {"groups": [{"merge": ["windows"], "into": "operating-systems"}]},
            ["windows", "macos", "printers"],
        )
        self.assertEqual(groups, [])

    def test_merging_everyone_is_a_rename_and_dies(self) -> None:
        groups = coerce_merges(
            {
                "groups": [
                    {"merge": ["windows", "macos", "printers"], "into": "computing"}
                ]
            },
            ["windows", "macos", "printers"],
        )
        self.assertEqual(groups, [])

    def test_two_siblings_with_a_leftover_are_kept(self) -> None:
        groups = coerce_merges(
            {
                "reasoning": "windows and macos are both operating systems.",
                "groups": [{"merge": ["windows", "macos"], "into": "operating-systems"}],
            },
            ["windows", "macos", "printers"],
        )
        self.assertEqual(len(groups), 1)
        merge, into = groups[0]
        self.assertEqual(set(merge), {"windows", "macos"})
        self.assertEqual(into, "operating-systems")


class MaintainableTests(unittest.TestCase):
    def test_root_and_thin_piles_are_not_maintainable(self) -> None:
        state = _state(
            ("a.txt", ["technology", "windows"]),
            ("b.txt", ["technology", "macos"]),
        )
        self.assertFalse(parent_is_maintainable(state, [], fat_min=2))
        self.assertTrue(parent_is_maintainable(state, ["technology"], fat_min=2))
        self.assertFalse(parent_is_maintainable(state, ["technology"], fat_min=8))

    def test_unmapped_prefix_is_never_maintainable(self) -> None:
        state = _state(("x.txt", ["unmapped"]))
        self.assertFalse(parent_is_maintainable(state, ["unmapped"], fat_min=1))


class MaintainAfterPlaceTests(unittest.TestCase):
    def test_rehomes_through_walk_state_and_stamps_why(self) -> None:
        # Filing already placed the letters. Maintain looks at sibling
        # names only — no document text in this window.
        state = _state(
            ("w.txt", ["technology", "windows"]),
            ("m.txt", ["technology", "macos"]),
            ("p.txt", ["technology", "printers"]),
        )

        def choose_combine(**_kw: object) -> dict:
            return {
                "reasoning": "windows and macos are both operating systems.",
                "groups": [{"merge": ["windows", "macos"], "into": "operating-systems"}],
            }

        moved = maintain_after_place(
            state,
            ["technology", "linux"],
            choose_combine=choose_combine,
            fat_min=2,
        )
        self.assertGreaterEqual(moved, 2)
        self.assertEqual(
            state.homes["w.txt"], ["technology", "operating-systems", "windows"]
        )
        self.assertEqual(
            state.homes["m.txt"], ["technology", "operating-systems", "macos"]
        )
        self.assertEqual(state.homes["p.txt"], ["technology", "printers"])
        note = state.combines[-1]
        self.assertEqual(note["into"], "operating-systems")
        self.assertEqual(set(note["from"]), {"windows", "macos"})
        self.assertIn("operating systems", note["reasoning"])

    def test_apply_merges_is_the_same_rehome(self) -> None:
        state = _state(
            ("w.txt", ["technology", "windows"]),
            ("m.txt", ["technology", "macos"]),
            ("p.txt", ["technology", "printers"]),
        )
        n = apply_merges(
            state,
            ["technology"],
            [(("windows", "macos"), "operating-systems")],
            reasoning="same kind of thing.",
        )
        self.assertEqual(n, 2)
        self.assertEqual(state.combines[-1]["reasoning"], "same kind of thing.")


if __name__ == "__main__":
    unittest.main()
