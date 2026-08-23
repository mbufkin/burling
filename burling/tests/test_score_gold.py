"""Gold L1 scorer — same numbers for every bake-off method. No model."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from burling.score_gold import format_table, score_regions


class ScoreGoldTests(unittest.TestCase):
    def test_hockey_primary_counts_as_recreation(self) -> None:
        # Names may differ from gold; the family still has to match.
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            regions = {
                "meta": {"method": "toy", "nodes": 1, "top_level": 1, "docs_mapped": 2},
                "regions": [
                    {
                        "id": "sports-hockey",
                        "label": "Hockey",
                        "children": [],
                    }
                ],
                "assignments": [
                    {"rel_path": "a.txt", "region_ids": ["sports-hockey"]},
                    {"rel_path": "b.txt", "region_ids": ["sports-hockey"]},
                ],
            }
            gold = {
                "a.txt": {"paths": ["recreation/sport-hockey"]},
                "b.txt": {"paths": ["science/space"]},
            }
            (root / "regions.json").write_text(json.dumps(regions), encoding="utf-8")
            (root / "gold.json").write_text(json.dumps(gold), encoding="utf-8")
            scored = score_regions(root / "regions.json", root / "gold.json")
            self.assertEqual(scored["primary_l1"], 1)
            self.assertEqual(scored["unmapped"], 0)
            # Two gold groups, each 100% together in their (different) piles.
            self.assertEqual(scored["mean_purity_pct"], 100.0)
            table = format_table([scored])
            self.assertIn("50.0%", table)
            self.assertIn("Purity", table)

    def test_split_topic_lowers_purity(self) -> None:
        # Three hockey files in Hockey, one stray in Crypto → 75% purity.
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            regions = {
                "meta": {"method": "toy", "nodes": 2, "top_level": 2, "docs_mapped": 4},
                "regions": [
                    {"id": "sports-hockey", "label": "Hockey", "children": []},
                    {"id": "crypto", "label": "Cryptography", "children": []},
                ],
                "assignments": [
                    {"rel_path": "a.txt", "region_ids": ["sports-hockey"]},
                    {"rel_path": "b.txt", "region_ids": ["sports-hockey"]},
                    {"rel_path": "c.txt", "region_ids": ["sports-hockey"]},
                    {"rel_path": "d.txt", "region_ids": ["crypto"]},
                ],
            }
            gold = {
                "a.txt": {"paths": ["recreation/hockey"]},
                "b.txt": {"paths": ["recreation/hockey"]},
                "c.txt": {"paths": ["recreation/hockey"]},
                "d.txt": {"paths": ["recreation/hockey"]},
            }
            (root / "regions.json").write_text(json.dumps(regions), encoding="utf-8")
            (root / "gold.json").write_text(json.dumps(gold), encoding="utf-8")
            scored = score_regions(root / "regions.json", root / "gold.json")
            self.assertEqual(scored["mean_purity_pct"], 75.0)
