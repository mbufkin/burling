"""Unit tests for local-model JSON parsing. No GPU, no network."""

from __future__ import annotations

import unittest

from burling.ollama_client import parse_model_json


class ParseModelJsonTests(unittest.TestCase):
    def test_plain_object(self) -> None:
        # Happy path: a clean object is returned as-is.
        self.assertEqual(parse_model_json('{"regions": []}'), {"regions": []})

    def test_fenced_json(self) -> None:
        # Models often wrap the object in a markdown fence.
        text = "here you go\n```json\n{\"ok\": true}\n```\n"
        self.assertEqual(parse_model_json(text), {"ok": True})

    def test_trailing_comma_is_repaired(self) -> None:
        # This is the CTE stitch crash: Nemotron left a trailing comma
        # and the unguarded json.loads raised JSONDecodeError.
        raw = '{"regions": [{"id": "mobile-lab",}], "notes": "x",}'
        self.assertEqual(
            parse_model_json(raw, context="stitch:regions"),
            {"regions": [{"id": "mobile-lab"}], "notes": "x"},
        )

    def test_line_comment_is_stripped(self) -> None:
        raw = '{\n  "id": "purchasing", // quotes and POs\n  "tags": ["quote"]\n}'
        self.assertEqual(parse_model_json(raw), {"id": "purchasing", "tags": ["quote"]})

    def test_garbage_raises_value_error(self) -> None:
        # Best practice: callers catch ValueError, never a raw JSONDecodeError.
        with self.assertRaises(ValueError):
            parse_model_json("not json at all", context="stitch:regions")


if __name__ == "__main__":
    unittest.main()
