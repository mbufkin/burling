"""Regression tests for taxonomy placement sanitization.

Nemotron (llama.cpp OpenAI API) often returns a single string per facet
instead of a one-element array. That must still place onto the map.
"""

from __future__ import annotations

import unittest

from burling.classify_map import _normalize, _sanitize_terms


ALLOWED = {
    "pathful-eif",
    "course-overview",
    "teachers",
    "word-procedure",
    "active-ops",
    "need-to-know-handoff",
    "unmapped",
}


class SanitizeTermsTests(unittest.TestCase):
    def test_string_facet_is_kept(self) -> None:
        # Live gb10 probe shape: "program": "pathful-eif" (not a list).
        self.assertEqual(
            _sanitize_terms("pathful-eif", ALLOWED),
            ["pathful-eif"],
        )

    def test_list_facet_unchanged(self) -> None:
        self.assertEqual(
            _sanitize_terms(["pathful-eif", "unmapped"], ALLOWED),
            ["pathful-eif", "unmapped"],
        )

    def test_unknown_term_becomes_unmapped(self) -> None:
        self.assertEqual(_sanitize_terms("made-up-label", ALLOWED), ["unmapped"])

    def test_nemotron_object_normalizes(self) -> None:
        # Exact shape from the one-doc gb10 probe that previously wiped to unmapped.
        raw = {
            "program": "pathful-eif",
            "function": "course-overview",
            "audience": "teachers",
            "record_type": "word-procedure",
            "lifecycle": ["active-ops"],
            "confidence": 0.95,
            "needs_review": False,
            "rationale": "Full-year course overview with Pathful integration.",
            "handoff_note": "Successor needs this for course setup.",
        }
        placed = _normalize(raw, {f: ALLOWED for f in (
            "program", "function", "audience", "record_type", "lifecycle"
        )})
        self.assertEqual(placed["program"], ["pathful-eif"])
        self.assertEqual(placed["function"], ["course-overview"])
        self.assertEqual(placed["audience"], ["teachers"])
        self.assertEqual(placed["record_type"], ["word-procedure"])
        self.assertEqual(placed["lifecycle"], ["active-ops"])
        self.assertFalse(placed["needs_review"])


if __name__ == "__main__":
    unittest.main()
