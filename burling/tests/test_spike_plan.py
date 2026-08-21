"""Staged spike helpers. No model."""

from __future__ import annotations

import unittest

from burling.ollama_client import assert_cloud_allowed
from burling.spike_plan import (
    ALL_STAGES,
    apply_field_map,
    child_user_prompt,
    coerce_open_id,
    existing_children,
)


class CoerceOpenIdTests(unittest.TestCase):
    def test_news_mains_are_not_forced_onto_workplace_series(self) -> None:
        # 20news hockey must stay hockey — coerce_main would have blanked it.
        self.assertEqual(coerce_open_id("Hockey"), "hockey")
        self.assertEqual(coerce_open_id("space-flight"), "space-flight")

    def test_year_and_usenet_are_still_banned(self) -> None:
        self.assertEqual(coerce_open_id("1993"), "")
        self.assertEqual(coerce_open_id("usenet-1993"), "")


class ChildPromptTests(unittest.TestCase):
    def test_existing_drawers_are_listed_for_reuse(self) -> None:
        recs = [
            {"rel_path": "a.txt", "main": "hockey", "sub": "playoffs"},
            {"rel_path": "b.txt", "main": "hockey", "sub": "playoffs"},
            {"rel_path": "c.txt", "main": "space", "sub": "shuttle"},
        ]
        kids = existing_children(recs, main="hockey")
        self.assertEqual(kids, [("playoffs", 2)])
        prompt = child_user_prompt(
            parent="hockey",
            rel_path="d.txt",
            text="Leafs win in overtime.",
            existing=kids,
        )
        self.assertIn("- playoffs: 2", prompt)
        self.assertNotIn("shuttle", prompt)
        self.assertIn("Leafs", prompt)

    def test_apply_map_only_touches_that_cabinet(self) -> None:
        recs = [
            {"rel_path": "a.txt", "main": "hockey", "sub": "playoff"},
            {"rel_path": "b.txt", "main": "hockey", "sub": "playoffs"},
            {"rel_path": "c.txt", "main": "space", "sub": "playoffs"},
        ]
        n = apply_field_map(
            recs,
            "sub",
            {"playoff": "playoffs", "playoffs": "playoffs"},
            main="hockey",
        )
        self.assertEqual(n, 1)
        self.assertEqual(recs[0]["sub"], "playoffs")
        self.assertEqual(recs[2]["sub"], "playoffs")


class CloudGuardTests(unittest.TestCase):
    def test_nim_proxy_requires_public_corpus(self) -> None:
        cfg = {
            "ollama": {"url": "http://127.0.0.1:8787", "model": "nvidia/x"},
            "policy": {},
            "paths": {"intake_dir": "/home/lenovo/gold-20news/inbox"},
        }
        with self.assertRaises(RuntimeError) as ctx:
            assert_cloud_allowed(cfg)
        self.assertIn("public_corpus", str(ctx.exception))

    def test_cte_intake_is_refused_even_with_the_flag(self) -> None:
        cfg = {
            "ollama": {"url": "http://127.0.0.1:8787", "model": "nvidia/x"},
            "policy": {"public_corpus": True},
            "paths": {"intake_dir": "/home/lenovo/cte-manager-intake"},
        }
        with self.assertRaises(RuntimeError) as ctx:
            assert_cloud_allowed(cfg)
        self.assertIn("cte-manager", str(ctx.exception).lower())

    def test_20news_plus_flag_is_allowed(self) -> None:
        cfg = {
            "ollama": {"url": "http://127.0.0.1:8787", "model": "nvidia/x"},
            "policy": {"public_corpus": True},
            "paths": {"intake_dir": "/home/lenovo/gold-20news/inbox"},
        }
        assert_cloud_allowed(cfg)

    def test_local_llama_does_not_need_the_flag(self) -> None:
        cfg = {
            "ollama": {"url": "http://127.0.0.1:8080", "model": "local.gguf"},
            "policy": {},
            "paths": {"intake_dir": "/home/lenovo/cte-manager-intake"},
        }
        assert_cloud_allowed(cfg)

    def test_stage_order_is_the_agreed_pipeline(self) -> None:
        self.assertEqual(
            ALL_STAGES,
            (
                "main",
                "combine-mains",
                "sub",
                "combine-subs",
                "detail",
                "combine-details",
            ),
        )


if __name__ == "__main__":
    unittest.main()
