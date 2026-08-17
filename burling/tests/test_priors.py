"""Unit tests for regex priors. No model, no GPU."""

from __future__ import annotations

import unittest

from burling.ollama_client import assert_local_only
from burling.pass2 import _force_personal_tax
from burling.priors import luhn_ok, prior_severity, scan_filename, scan_text


class PriorScanTests(unittest.TestCase):
    def test_formatted_ssn_is_redacted(self) -> None:
        # 123-45-6789 is the SSA advertising / invalid example, not a real person.
        text = "Employee SSN: 123-45-6789 on the leftover tax packet."
        hits = scan_text(text)
        self.assertIn("ssn", hits)
        self.assertEqual(hits["ssn"]["count"], 1)
        self.assertEqual(hits["ssn"]["redacted_samples"], ["***-**-6789"])
        self.assertNotIn("123-45-6789", str(hits))

    def test_keyword_plus_nine_digits(self) -> None:
        text = "social security number 123456789 is listed below"
        hits = scan_text(text)
        self.assertIn("ssn", hits)
        self.assertTrue(hits["ssn"]["redacted_samples"][0].endswith("6789"))

    def test_luhn_test_visa(self) -> None:
        self.assertTrue(luhn_ok("4111111111111111"))
        self.assertFalse(luhn_ok("4111111111111112"))
        hits = scan_text("card 4111 1111 1111 1111")
        self.assertIn("credit_card", hits)
        self.assertTrue(hits["credit_card"]["redacted_samples"][0].endswith("1111"))

    def test_filename_hints(self) -> None:
        tags = scan_filename("personal/2023-W2-john.pdf")
        self.assertIn("tax_financial", tags)

    def test_severity(self) -> None:
        self.assertEqual(prior_severity({"ssn": {"count": 1}}), "high")
        self.assertEqual(prior_severity({"email": {"count": 1}}), "medium")
        self.assertEqual(prior_severity({}), "low")

    def test_fail_closed_overrides_model_keep(self) -> None:
        # Filename W-2 is personal leftover even if the model says keep.
        row = {"filename_tags": ["tax_financial"], "priors": {"ssn": {"count": 1}}}
        result = {"recommendation": "keep", "reasons": ["keep_work_curriculum"]}
        cfg = {"policy": {"fail_closed_on_personal_tax": True}}
        out = _force_personal_tax(row, result, cfg)
        self.assertEqual(out["recommendation"], "delete_candidate")
        self.assertIn("personal_tax", out["reasons"])
        self.assertTrue(out["fail_closed"])

    def test_refuses_cloud_model_url(self) -> None:
        with self.assertRaises(RuntimeError):
            assert_local_only("https://api.openai.com/v1/chat/completions")
        assert_local_only("http://127.0.0.1:11434/api/chat")


if __name__ == "__main__":
    unittest.main()
