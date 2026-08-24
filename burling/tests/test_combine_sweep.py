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


class DissolveTests(unittest.TestCase):
    def test_thin_drawer_dissolves_into_parent(self) -> None:
        state = WalkState()
        _place(state, "a", "legal", "nda")
        _place(state, "b", "legal", "trademarks")

        def fake_combine(*, prefix, siblings):
            return {"groups": [{"merge": ["nda"], "into": "legal"}],
                    "reasoning": "one-file drawer"}

        moved = sweep_combines(state, fake_combine)
        self.assertEqual(moved, 1)
        self.assertEqual(state.homes["a"], ["legal"])
        self.assertEqual(state.combines[0]["dissolve"], True)
        # Fat-enough drawer untouched.
        self.assertEqual(state.homes["b"], ["legal", "trademarks"])

    def test_fat_drawer_refuses_dissolve(self) -> None:
        from burling.walk_plan import DISSOLVE_MAX_FILES

        state = WalkState()
        for i in range(DISSOLVE_MAX_FILES + 1):
            _place(state, f"n{i}", "technology", "network")

        def fake_combine(*, prefix, siblings):
            return {"groups": [{"merge": ["network"], "into": "technology"}]}

        moved = sweep_combines(state, fake_combine)
        self.assertEqual(moved, 0)
        self.assertTrue(all(h[:2] == ["technology", "network"] for h in state.homes.values()))

    def test_dissolve_at_depth_two(self) -> None:
        state = WalkState()
        st = WalkState()
        st.place("a", main="finance", sub=ChildChoice("invent", "invoices"),
                 detail=ChildChoice("invent", "services"))
        st.place("b", main="finance", sub=ChildChoice("invent", "invoices"),
                 detail=ChildChoice("invent", "payments"))
        state.homes.update(st.homes)
        state.records.update(st.records)

        def fake_combine(*, prefix, siblings):
            if prefix == ["finance"]:
                return {"groups": []}
            if prefix == ["finance", "invoices"]:
                return {"groups": [{"merge": ["services"], "into": "invoices"}]}
            return {"groups": []}
            return {"groups": []}

        moved = sweep_combines(state, fake_combine)
        self.assertEqual(moved, 1)
        self.assertEqual(state.homes["a"], ["finance", "invoices"])
