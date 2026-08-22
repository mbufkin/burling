"""Default --intake path is walk, not map.yml. No model."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from burling.paths import load_config
from burling.run import run_handover


class HandoverRunTests(unittest.TestCase):
    def test_default_run_calls_walk_not_map(self) -> None:
        called: list[str] = []

        def pass1(cfg: dict, limit=None) -> int:
            called.append("pass1")
            return 0

        def pass2(cfg: dict, limit=None) -> int:
            called.append("pass2")
            return 0

        def walk(cfg, **_kw) -> dict:
            called.append("walk")
            return {"documents": 0}

        def queue(cfg: dict) -> dict:
            called.append("queue")
            return {"total": 0, "intake": str(cfg["paths"]["intake_dir"])}

        with tempfile.TemporaryDirectory() as tmp:
            cfg = load_config()
            cfg["paths"]["intake_dir"] = str(Path(tmp) / "intake")
            cfg["paths"]["output_dir"] = str(Path(tmp) / "output")
            Path(cfg["paths"]["intake_dir"]).mkdir()
            Path(cfg["paths"]["output_dir"]).mkdir()
            rc = run_handover(
                cfg,
                run_pass1_fn=pass1,
                run_pass2_fn=pass2,
                run_walk_fn=walk,
                build_queue_fn=queue,
            )
            self.assertEqual(rc, 0)
            self.assertEqual(called, ["queue", "pass1", "pass2", "walk"])
            self.assertNotIn("map", called)

    def test_pass_two_only_does_not_walk(self) -> None:
        called: list[str] = []

        def pass2(cfg: dict, limit=None) -> int:
            called.append("pass2")
            return 0

        def walk(cfg, **_kw) -> dict:
            called.append("walk")
            return {}

        with tempfile.TemporaryDirectory() as tmp:
            cfg = load_config()
            cfg["paths"]["intake_dir"] = str(Path(tmp) / "intake")
            cfg["paths"]["output_dir"] = str(Path(tmp) / "output")
            Path(cfg["paths"]["output_dir"]).mkdir()
            rc = run_handover(
                cfg,
                only_pass="2",
                resume=True,
                run_pass2_fn=pass2,
                run_walk_fn=walk,
            )
            self.assertEqual(rc, 0)
            self.assertEqual(called, ["pass2"])


if __name__ == "__main__":
    unittest.main()
