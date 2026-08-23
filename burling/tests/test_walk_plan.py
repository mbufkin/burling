"""Tree-walk clerk: reuse / invent / combine + rehome. No model."""

from __future__ import annotations

import unittest

from burling.file_plan import UNMAPPED_ID
from burling.walk_plan import (
    ChildChoice,
    WalkState,
    build_walk_regions,
    coerce_child_choice,
    coerce_main_choice,
    walk_one,
)


class CoerceMainTests(unittest.TestCase):
    def test_empty_text_is_unmapped_with_reason(self) -> None:
        main, reason = coerce_main_choice({"main": "technology"}, text="")
        self.assertEqual(main, "")
        self.assertEqual(reason, "extract missing")

    def test_unsubscribe_may_be_unmapped(self) -> None:
        main, reason = coerce_main_choice(
            {"main": "unmapped", "reason": "unsubscribe request"},
            text="please unsubscribe me from this list",
        )
        self.assertEqual(main, "")
        self.assertIn("unsubscribe", reason)

    def test_unmapped_with_real_subject_is_invalid_not_a_series(self) -> None:
        # Model used the leftover bin as "doesn't fit." Code refuses both
        # a 14th series and a silent dump — the runner retries.
        main, reason = coerce_main_choice(
            {"main": "unmapped", "reason": "not sure"},
            text="Q3 invoice for Acme roof repair, PO 4412, amount $12,400 due net 30.",
        )
        self.assertEqual(main, "")
        self.assertEqual(reason, "")

    def test_hardware_aliases_to_facilities(self) -> None:
        main, _reason = coerce_main_choice(
            {"main": "hardware"},
            text="Replacement toner for the 4th floor printer.",
        )
        self.assertEqual(main, "facilities")

    def test_unknown_main_is_not_invented(self) -> None:
        main, reason = coerce_main_choice(
            {"main": "cryptography"},
            text="RIPEM on the Amiga, key exchange notes.",
        )
        self.assertEqual(main, "")
        self.assertEqual(reason, "")


class CoerceChildTests(unittest.TestCase):
    def test_first_child_invents(self) -> None:
        choice = coerce_child_choice({"action": "invent", "name": "Hockey"}, [], allow_empty=True)
        self.assertEqual(choice, ChildChoice("invent", "hockey", ()))

    def test_reuse_must_be_an_existing_sibling(self) -> None:
        choice = coerce_child_choice(
            {"action": "reuse", "name": "hockey"},
            ["hockey", "baseball"],
            allow_empty=True,
        )
        self.assertEqual(choice.action, "reuse")
        self.assertEqual(choice.name, "hockey")

    def test_named_existing_sibling_without_verb_is_reuse(self) -> None:
        # 30B often forgets "action" and just writes the id.
        choice = coerce_child_choice({"name": "hockey"}, ["hockey", "baseball"], allow_empty=True)
        self.assertEqual(choice.action, "reuse")

    def test_combine_requires_two_existing_siblings(self) -> None:
        ok = coerce_child_choice(
            {"action": "combine", "merge": ["windows", "macos"], "into": "operating-systems"},
            ["windows", "macos", "printers"],
            allow_empty=True,
        )
        self.assertEqual(ok.action, "combine")
        self.assertEqual(ok.name, "operating-systems")
        self.assertEqual(set(ok.merge), {"windows", "macos"})

        dropped = coerce_child_choice(
            {"action": "combine", "merge": ["windows"], "into": "operating-systems"},
            ["windows", "macos"],
            allow_empty=True,
        )
        self.assertEqual(dropped.action, "invent")
        self.assertEqual(dropped.name, "operating-systems")

    def test_banned_and_reserved_child_names_drop(self) -> None:
        # communications/unmapped was the workplace-run smell.
        self.assertEqual(
            coerce_child_choice({"action": "invent", "name": "unmapped"}, [], allow_empty=True).action,
            "empty",
        )
        self.assertEqual(
            coerce_child_choice({"action": "invent", "name": "technology"}, [], allow_empty=True).action,
            "empty",
        )
        self.assertEqual(
            coerce_child_choice({"action": "invent", "name": "usenet-1993"}, [], allow_empty=True).action,
            "empty",
        )
        self.assertEqual(
            coerce_child_choice({"action": "invent", "name": "misc"}, [], allow_empty=True).action,
            "empty",
        )


class RehomeTests(unittest.TestCase):
    def test_combine_moves_siblings_and_nests_old_name(self) -> None:
        # Navy closest-folder: windows + macos → operating-systems, files move.
        state = WalkState()
        state.homes = {
            "w1.txt": ["technology", "windows"],
            "w2.txt": ["technology", "windows", "printer-driver"],
            "m1.txt": ["technology", "macos"],
            "other.txt": ["technology", "networks"],
        }
        moved = state.rehome(["technology"], ["windows", "macos"], "operating-systems")
        self.assertEqual(moved, 3)
        self.assertEqual(state.homes["w1.txt"], ["technology", "operating-systems", "windows"])
        # Depth 3 cap: printer-driver becomes a facet, not a 4th folder.
        self.assertEqual(state.homes["w2.txt"], ["technology", "operating-systems", "windows"])
        self.assertEqual(state.facets["w2.txt"], "printer-driver")
        self.assertEqual(state.homes["m1.txt"], ["technology", "operating-systems", "macos"])
        self.assertEqual(state.homes["other.txt"], ["technology", "networks"])

    def test_combine_into_an_existing_sibling(self) -> None:
        state = WalkState()
        state.homes = {
            "w.txt": ["technology", "windows"],
            "m.txt": ["technology", "macos"],
        }
        state.rehome(["technology"], ["windows", "macos"], "windows")
        self.assertEqual(state.homes["w.txt"], ["technology", "windows"])
        self.assertEqual(state.homes["m.txt"], ["technology", "windows", "macos"])

    def test_detail_combine_flattens_to_into(self) -> None:
        state = WalkState()
        state.homes = {
            "g.txt": ["technology", "software", "git"],
            "h.txt": ["technology", "software", "mercurial"],
        }
        state.rehome(["technology", "software"], ["git", "mercurial"], "version-control")
        self.assertEqual(state.homes["g.txt"], ["technology", "software", "version-control"])
        self.assertEqual(state.facets["g.txt"], "git")


class WalkOneTests(unittest.TestCase):
    def test_first_file_invents_then_second_reuses(self) -> None:
        state = WalkState()

        def main(**_kw: object) -> dict:
            return {"main": "personal", "summary": "hockey scores"}

        def child(*, prefix: list[str], siblings: list, **_kw: object) -> dict:
            if prefix == ["personal"] and not siblings:
                return {"action": "invent", "name": "hockey"}
            if prefix == ["personal"]:
                return {"action": "reuse", "name": "hockey"}
            return {"action": "empty"}

        text = "Tonight's Leafs score and remaining schedule."
        self.assertEqual(
            walk_one(state, rel_path="a.txt", text=text, choose_main=main, choose_child=child),
            ["personal", "hockey"],
        )
        self.assertEqual(
            walk_one(state, rel_path="b.txt", text=text, choose_main=main, choose_child=child),
            ["personal", "hockey"],
        )
        self.assertEqual(state.children(["personal"]), [("hockey", 2)])

    def test_combine_verb_files_this_letter_without_moving_siblings(self) -> None:
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

        def child(*, prefix: list[str], siblings: list, **_kw: object) -> dict:
            names = {n for n, _c in siblings}
            if prefix == ["technology"] and names >= {"windows", "macos"}:
                return {
                    "action": "combine",
                    "merge": ["windows", "macos"],
                    "into": "operating-systems",
                    "name": "operating-systems",
                }
            if prefix == ["technology", "operating-systems"]:
                return {"action": "invent", "name": "linux"}
            return {"action": "empty"}

        home = walk_one(
            state,
            rel_path="l.txt",
            text="Installing Debian on the lab tower.",
            choose_main=main,
            choose_child=child,
        )
        self.assertEqual(home, ["technology", "operating-systems", "linux"])
        # Combine is a later supervisor pass. This letter lands in the
        # proposed folder; already-filed siblings stay where they are.
        self.assertEqual(state.homes["w.txt"], ["technology", "windows"])
        self.assertEqual(state.homes["m.txt"], ["technology", "macos"])
        payload = build_walk_regions(state)
        self.assertEqual(payload["meta"]["homes_mean"], 1.0)
        self.assertEqual(payload["meta"]["unmapped"], 0)
        self.assertEqual(payload["meta"]["combines"], 0)
        ids = {n["id"] for n in payload["regions"]}
        self.assertIn("technology", ids)
        self.assertNotIn(UNMAPPED_ID, {a["rel_path"] for a in payload["assignments"]})
        linux = next(a for a in payload["assignments"] if a["rel_path"] == "l.txt")
        self.assertEqual(linux["region_ids"], ["technology--operating-systems--linux"])
        self.assertEqual(len(linux["region_ids"]), 1)

    def test_empty_body_does_not_invent_a_folder(self) -> None:
        state = WalkState()

        def boom(**_kw: object) -> dict:
            raise AssertionError("chooser must not run on empty extract")

        home = walk_one(
            state, rel_path="x.txt", text="", choose_main=boom, choose_child=boom
        )
        self.assertEqual(home, [UNMAPPED_ID])
        self.assertEqual(state.records["x.txt"]["reason"], "extract missing")


if __name__ == "__main__":
    unittest.main()
