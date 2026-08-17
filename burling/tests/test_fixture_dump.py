"""The shipped tiny-dump fixture must stay runnable without a GPU or a real dump."""

from __future__ import annotations

import unittest
from pathlib import Path

from burling.paths import EXAMPLE_CONFIG_PATH, load_config
from burling.priors import scan_filename, scan_text
from burling.queue import build_queue

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "tiny-dump"


class FixtureDumpTests(unittest.TestCase):
    def test_example_config_loads_without_config_yaml(self) -> None:
        self.assertTrue(EXAMPLE_CONFIG_PATH.is_file())
        cfg = load_config(EXAMPLE_CONFIG_PATH)
        self.assertTrue(cfg["policy"]["local_only"])
        self.assertTrue(cfg["policy"]["never_delete"])
        self.assertNotEqual((cfg.get("rclone") or {}).get("remote"), "disd:")
        # Fallback path (no config.yaml in a clean clone) must also work.
        loaded = load_config()
        self.assertEqual(loaded["ollama"]["url"], "http://127.0.0.1:11434")

    def test_tiny_dump_has_three_reviewable_files(self) -> None:
        names = sorted(p.name for p in FIXTURE.iterdir() if p.suffix in {".md", ".txt"} and p.name != "README.md")
        self.assertEqual(names, ["2023-W2-notes.txt", "meeting-notes.md", "staff-contact-sheet.md"])

        tax = (FIXTURE / "2023-W2-notes.txt").read_text(encoding="utf-8")
        self.assertIn("ssn", scan_text(tax))
        self.assertIn("tax_financial", scan_filename("2023-W2-notes.txt"))

        notes = (FIXTURE / "meeting-notes.md").read_text(encoding="utf-8")
        self.assertFalse(scan_text(notes))

        contacts = (FIXTURE / "staff-contact-sheet.md").read_text(encoding="utf-8")
        self.assertIn("email", scan_text(contacts))

    def test_priors_only_queue_on_fixture(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            cfg = load_config()
            cfg["paths"]["intake_dir"] = str(FIXTURE)
            cfg["paths"]["output_dir"] = str(Path(tmp) / "output")
            queue = build_queue(cfg, intake=FIXTURE)
            self.assertEqual(queue["total"], 3)
