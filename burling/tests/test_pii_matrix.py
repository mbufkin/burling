"""PII matrix fixtures: every priors.py class fires exactly when it should.

The fixtures come from tools/make_corpus.py (docs/test-corpus.md, Layer 1).
Expectations here MUST stay in sync with the content there — the point is
that a corpus change that silently alters detection fails loudly here.

No model. No GPU. Runs entirely on regex + queue plumbing.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "pii-matrix"

# rel_path → (expected prior kinds, expected severity)
EXPECTATIONS: dict[str, tuple[set[str], str]] = {
    "pii-ssn-formatted.txt": ({"ssn"}, "high"),
    "pii-ssn-keyword-blob.txt": ({"ssn", "sensitive_keyword"}, "high"),
    "pii-neg-order-number.txt": (set(), "low"),
    "pii-cc-luhn-valid.txt": ({"credit_card"}, "high"),
    "pii-cc-luhn-invalid.txt": (set(), "low"),
    "pii-dob-keyword.txt": ({"dob", "sensitive_keyword"}, "medium"),
    "pii-neg-bare-date.txt": (set(), "low"),
    "pii-phone-formats.txt": ({"phone"}, "medium"),
    "pii-address-street.txt": ({"address"}, "medium"),
    "pii-address-po-box.txt": ({"address"}, "medium"),
    "pii-email-plus.txt": ({"email"}, "medium"),
    "pii-keywords-confidential.txt": ({"sensitive_keyword"}, "medium"),
    "hint-filename-w2.txt": (set(), "low"),  # hint lives in filename_tags
    "pii-neg-clean-meeting.md": (set(), "low"),
}

# Raw identifiers that must NEVER appear in persisted artifacts.
RAW_STRINGS = (
    "123-45-6789",
    "447038211",
    "4111 1111 1111 1111",
    "4111111111111111",
    "alex+signup@example.com",
    "(214) 555-0142",
    "+1 214-555-0142",
    "04/12/1988",
    "3505 Mockingbird Lane",
)


class PiiMatrixDetectionTests(unittest.TestCase):
    """Layer-1 unit contract: scan_text + severity per fixture."""

    def test_every_fixture_is_covered(self) -> None:
        on_disk = {p.name for p in FIXTURES.glob("*") if p.is_file()}
        self.assertEqual(on_disk, set(EXPECTATIONS), "corpus and expectations diverged")

    def test_detection_and_severity_per_file(self) -> None:
        from burling.priors import prior_severity, scan_filename, scan_text

        for name, (kinds, severity) in EXPECTATIONS.items():
            with self.subTest(fixture=name):
                text = (FIXTURES / name).read_text(encoding="utf-8")
                priors = scan_text(text)
                self.assertEqual(set(priors), kinds, f"priors mismatch for {name}")
                self.assertEqual(prior_severity(priors), severity, f"severity mismatch for {name}")

    def test_filename_hint_fires_on_name_alone(self) -> None:
        from burling.priors import scan_filename

        tags = scan_filename("hint-filename-w2.txt")
        self.assertIn("tax_financial", tags)


class PiiRedactionEndToEndTests(unittest.TestCase):
    """The privacy promise, run against real queue plumbing.

    build_queue must persist REDACTED samples only: no raw identifier may
    appear anywhere in the saved ledger/queue artifact.
    """

    def test_raw_identifiers_never_reach_disk(self) -> None:
        from burling.queue import build_queue

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = {
                "paths": {
                    "intake_dir": str(root / "intake"),
                    "output_dir": str(root / "output"),
                },
            }
            build_queue(cfg, intake=FIXTURES)

            # Strongest form: read the artifact back off disk.
            queue_files = list((root / "output").glob("*.json"))
            self.assertTrue(queue_files, "queue wrote no json artifact")
            blob = "\n".join(
                p.read_text(encoding="utf-8", errors="replace") for p in queue_files
            )
            for raw in RAW_STRINGS:
                with self.subTest(raw=raw):
                    self.assertNotIn(raw, blob)


if __name__ == "__main__":
    unittest.main()
