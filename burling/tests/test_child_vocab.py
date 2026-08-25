"""Child vocabulary: sub-drawers get the same menu+coercion lock mains have.

Mains hit ~96% accuracy because they are menu-locked; free-invented subs
scored ~15-27% because the model guesses house words it cannot know.
"""

from __future__ import annotations

import unittest

from burling.file_plan import WORKPLACE_CHILDREN, approved_children
from burling.walk_plan import ChildChoice, WalkState, _child_user, _coerce_with_menu


class ApprovedChildrenTests(unittest.TestCase):
    def test_builtin_menu_for_known_main(self) -> None:
        self.assertEqual(
            approved_children(None, "personnel"),
            {"policies", "cases", "benefits", "rosters"},
        )

    def test_unknown_main_means_free_invention(self) -> None:
        self.assertIsNone(approved_children(None, "customers"))

    def test_config_override(self) -> None:
        cfg = {"walk": {"children": {"legal": ["Contracts", "_disputes"]}}}
        self.assertEqual(approved_children(cfg, "legal"), {"contracts", "disputes"})

    def test_config_can_disable_menus(self) -> None:
        self.assertIsNone(approved_children({"walk": {"children": False}}, "legal"))


class MenuCoercionTests(unittest.TestCase):
    def test_off_menu_invent_falls_back_to_empty(self) -> None:
        choice = _coerce_with_menu(
            {"action": "invent", "name": "meetings"},
            [],
            {"minutes", "policies"},
        )
        self.assertEqual(choice.action, "empty")

    def test_on_menu_names_pass_through(self) -> None:
        choice = _coerce_with_menu(
            {"action": "invent", "name": "Minutes"},
            [],
            {"minutes", "policies"},
        )
        self.assertEqual((choice.action, choice.name), ("invent", "minutes"))

    def test_no_menu_keeps_free_invention(self) -> None:
        choice = _coerce_with_menu({"action": "invent", "name": "anything"}, [], None)
        self.assertEqual((choice.action, choice.name), ("invent", "anything"))


class PromptMenuTests(unittest.TestCase):
    def test_prompt_lists_approved_children(self) -> None:
        user = _child_user("a.txt", "body text here", ["personnel"], [],
                           approved={"policies", "cases"})
        self.assertIn("APPROVED CHILDREN for this folder", user)
        self.assertIn("- policies", user)
        # Document body must not leak into the logged context (split marker).
        self.assertIn("DOCUMENT TEXT:", user)


class WalkOneVocabTests(unittest.TestCase):
    def test_walk_one_enforces_the_menu(self) -> None:
        from burling.layer_plan import kebab

        state = WalkState()
        home = state.place  # noqa: F841  (readability)
        got = WalkState()
        result = _walk(got, choose_sub="rosters")
        self.assertEqual(result[:2], ["personnel", "rosters"])
        off = _walk(WalkState(), choose_sub="team-offsite")
        self.assertEqual(off, ["personnel"])

def _walk(state: WalkState, *, choose_sub: str):
    from burling.walk_plan import walk_one

    return walk_one(
        state,
        rel_path="x.txt",
        text="offer letter for a quality analyst position",
        choose_main=lambda **kw: {"main": "personnel"},
        choose_child=lambda **kw: {"name": choose_sub},
        cfg={},
    )


if __name__ == "__main__":
    unittest.main()
