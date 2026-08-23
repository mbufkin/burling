"""Unit tests for Pass A rich-tag normalization."""

from __future__ import annotations

import unittest

from burling.tag_rich import SYSTEM, _should_tag, normalize_rich_tags


class NormalizeRichTagsTests(unittest.TestCase):
    def test_string_tags_coerced(self) -> None:
        # Nemotron often returns a single string instead of an array.
        raw = {
            "tags": (
                "mobile-lab, trailer-compliance, campus-acknowledgment, "
                "safety-protocol, scheduling, principal-signoff, "
                "career-exploration, 2026-2027"
            ),
            "entities": "Dallas ISD CTE Mobile Lab",
            "audiences": ["campus-admin"],
            "artifact_types": "checklist",
            "years": ["2026-2027"],
            "summary": "Campus acknowledgment form for Mobile Lab visits.",
            "confidence": 0.9,
        }
        out = normalize_rich_tags(raw)
        self.assertIn("mobile-lab", out["tags"])
        self.assertIn("trailer-compliance", out["tags"])
        self.assertGreaterEqual(len(out["tags"]), 3)
        self.assertFalse(out["needs_review"])

    def test_sparse_tags_need_review(self) -> None:
        out = normalize_rich_tags(
            {"tags": ["a", "b"], "summary": "too thin", "confidence": 0.9}
        )
        self.assertTrue(out["needs_review"])

    def test_prompt_does_not_force_handover_frame(self) -> None:
        # Forcing "successor / handover" made every summary a transition story.
        lowered = SYSTEM.lower()
        self.assertNotIn("for a successor", lowered)
        self.assertIn("do not assume", lowered)

    def test_should_tag_retries_skipped_extract(self) -> None:
        skipped = {"rich_tags": {"status": "skipped", "summary": "Extract failed"}}
        done = {"rich_tags": {"status": "done", "tags": ["a"]}}
        self.assertTrue(_should_tag(skipped, force=False))
        self.assertFalse(_should_tag(done, force=False))
        self.assertTrue(_should_tag(done, force=True))


if __name__ == "__main__":
    unittest.main()
