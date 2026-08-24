"""Topic-map chrome: district default vs public sample masthead."""

from __future__ import annotations

import unittest

from burling.map_html import SAMPLE_CHROME, build_topic_map_html


def _payload(**extra):
    data = {
        "placements": [
            {
                "rel_path": "finance/invoices/invoice-acme-0042.txt",
                "program": ["finance"],
                "function": ["invoices"],
                "audience": ["unmapped"],
                "record_type": ["unmapped"],
                "lifecycle": ["unmapped"],
                "confidence": 1.0,
                "needs_review": False,
                "handoff_note": "April consulting invoice.",
            }
        ]
    }
    data.update(extra)
    return data


class TopicMapChromeTests(unittest.TestCase):
    def test_default_chrome_keeps_district_masthead(self) -> None:
        html = build_topic_map_html(_payload())
        self.assertIn("Dallas ISD", html)
        self.assertIn("data-label", html)

    def test_sample_chrome_has_no_district_name(self) -> None:
        html = build_topic_map_html(_payload(chrome=SAMPLE_CHROME))
        self.assertIn("Burling", html)
        self.assertIn("Sample collection", html)
        self.assertNotIn("Dallas ISD", html)
        self.assertNotIn("Career &amp; Technical Education", html)
        # Walk maps only have a program ring — hide empty facet tabs.
        self.assertNotIn('data-facet="audience"', html)
        self.assertIn('data-facet="program"', html)


if __name__ == "__main__":
    unittest.main()
