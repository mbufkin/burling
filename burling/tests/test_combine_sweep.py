"""Combine sweep: post-walk cleanup decoupled from the FAT_MIN filing gate."""
from __future__ import annotations

import unittest

from burling.maintain_plan import sweep_combines
from burling.walk_plan import ChildChoice, WalkState


def _place(state: WalkState, rel: str, main: str, sub: str) -> None:
    state.place(rel, main=main, sub=ChildChoice("invent", sub),
                detail=ChildChoice("empty", ""))


class SweepTests(unittest.TestCase):
    def test_thin_parents_get_a_cleanup_window(self) -> None:
        state = WalkState()
        _place(state, "a", "technology", "network")
        _place(state, "b", "technology", "api-gateway")
        _place(state, "c", "technology", "retros")
        _place(state, "d", "training", "plans")
        # FAT_MIN=8 would never open a window for this 3-file parent.

        def fake_combine(*, prefix, siblings):
            if prefix == ["technology"]:
                return {"groups": [{"merge": ["network", "api-gateway"],
                                     "into": "infrastructure"}],
                        "reasoning": "same domain"}
            return {"groups": []}  # decline

        moved = sweep_combines(state, fake_combine)
        self.assertEqual(moved, 2)
        self.assertEqual(state.homes["a"], ["technology", "infrastructure", "network"])
        self.assertEqual(state.homes["b"], ["technology", "infrastructure", "api-gateway"])
        # Leftover child stays put.
        self.assertEqual(state.homes["c"], ["technology", "retros"])

    def test_single_child_parent_is_skipped(self) -> None:
        state = WalkState()
        _place(state, "a", "legal", "nda")
        _place(state, "b", "legal", "nda")

        calls = []

        def fake_combine(*, prefix, siblings):
            calls.append(prefix)
            return {"groups": []}

        sweep_combines(state, fake_combine)
        self.assertEqual(calls, [])  # nothing to combine into

    def test_unmapped_never_swept(self) -> None:
        from burling.file_plan import UNMAPPED_ID

        state = WalkState()
        state.homes["j1"] = [UNMAPPED_ID]
        state.homes["j2"] = [UNMAPPED_ID]
        calls = []
        sweep_combines(state, lambda **kw: calls.append(kw) or {"groups": []})
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
