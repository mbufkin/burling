"""File-plan clerk: banned heads, closed enum, one home. No model."""

from __future__ import annotations

import unittest

from burling.file_plan import (
    UNMAPPED_ID,
    apply_clerk_homes,
    coerce_home,
    demote_banned_heads,
    fileable_homes,
    is_banned_head,
)
from burling.stitch_tags import STITCH_SYSTEM_CLERK


class BannedHeadTests(unittest.TestCase):
    def test_channel_and_year_are_banned(self) -> None:
        # Military: year is a cutoff inside the subject, not a root.
        self.assertTrue(is_banned_head("usenet-1993", "Usenet 1993"))
        self.assertTrue(is_banned_head("email-1990s", "Email 1990s"))
        self.assertTrue(is_banned_head("newsgroup-discussion", "Newsgroup Discussion"))
        self.assertTrue(is_banned_head("1993", "1993"))

    def test_topical_heads_are_kept(self) -> None:
        self.assertFalse(is_banned_head("sports-hockey", "Hockey"))
        self.assertFalse(is_banned_head("cryptography", "Cryptography"))
        self.assertFalse(is_banned_head("hardware", "PC Hardware"))

    def test_demote_promotes_topical_children(self) -> None:
        tree = [
            {
                "id": "usenet-1993",
                "label": "Usenet 1993",
                "children": [
                    {"id": "sports-hockey", "label": "Hockey", "children": []},
                    {"id": "email-archive", "label": "Email Archive", "children": []},
                ],
            },
            {"id": "cryptography", "label": "Cryptography", "children": []},
        ]
        kept = demote_banned_heads(tree)
        ids = [n["id"] for n in kept]
        self.assertEqual(ids, ["sports-hockey", "cryptography"])


class CoerceHomeTests(unittest.TestCase):
    def test_unknown_becomes_unmapped(self) -> None:
        allowed = {"sports-hockey", UNMAPPED_ID}
        self.assertEqual(coerce_home("sports-hockey", allowed), "sports-hockey")
        self.assertEqual(coerce_home("usenet-1993", allowed), UNMAPPED_ID)
        self.assertEqual(coerce_home("", allowed), UNMAPPED_ID)
        self.assertEqual(coerce_home(None, allowed), UNMAPPED_ID)

    def test_apply_clerk_forces_one_home(self) -> None:
        payload = {
            "regions": [
                {"id": "hockey", "label": "Hockey", "children": []},
                {"id": UNMAPPED_ID, "label": "Unmapped", "children": []},
            ],
            "assignments": [
                {
                    "rel_path": "a.txt",
                    "region_ids": ["hockey", "unmapped", "ghost"],
                    "top_level_regions": ["hockey", "unmapped"],
                }
            ],
        }
        apply_clerk_homes(payload, {"a.txt": "hockey"})
        row = payload["assignments"][0]
        self.assertEqual(row["region_ids"], ["hockey"])
        self.assertEqual(row["clerk_home"], "hockey")

    def test_fileable_homes_include_unmapped(self) -> None:
        homes = fileable_homes([{"id": "hockey", "label": "Hockey", "children": []}])
        ids = [h["id"] for h in homes]
        self.assertIn("hockey", ids)
        self.assertIn(UNMAPPED_ID, ids)


class ClerkPromptTests(unittest.TestCase):
    def test_clerk_stitch_bans_channel_heads(self) -> None:
        lowered = STITCH_SYSTEM_CLERK.lower()
        self.assertIn("file plan", lowered)
        self.assertIn("usenet", lowered)
        self.assertNotIn("for a successor", lowered)
        self.assertNotIn("handoff map", lowered)


if __name__ == "__main__":
    unittest.main()
