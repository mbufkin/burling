#!/usr/bin/env python3
"""Deterministic synthetic corpus generator (docs/test-corpus.md).

Writes the fixture layers the test suite runs against. Seeded, offline,
no real identifiers: 555-01xx phones, example.com addresses, SSNs in
ranges SSA never issued (000/900) or the CONTRIBUTING-blessed document
example 123-45-6789. Run once; commit the output.

    python tools/make_corpus.py            # writes every implemented layer
    python tools/make_corpus.py --layer pii-matrix

Layers:
  pii-matrix   Layer 1 of docs/test-corpus.md — one positive and one
               negative per priors.py detection class, plus filename-hint
               and clean controls. Plain text, KB-scale.
"""

from __future__ import annotations

import argparse
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
FIXTURES = PROJECT / "burling" / "tests" / "fixtures"

# ---------------------------------------------------------------------------
# Layer 1: PII / severity matrix. Each file isolates exactly one behavior in
# burling/priors.py. Expectations are mirrored in test_pii_matrix.py — keep
# the two in sync when editing content here.
# ---------------------------------------------------------------------------

PII_MATRIX: dict[str, str] = {
    # HIGH severity: formatted SSN (CONTRIBUTING.md-blessed example).
    "pii-ssn-formatted.txt": (
        "New hire onboarding checklist for Alex Rivera.\n"
        "SSN: 123-45-6789\n"
        "Badge photo attached to the personnel file.\n"
    ),
    # HIGH: bare 9-digit block INSIDE the SSN keyword window.
    "pii-ssn-keyword-blob.txt": (
        "HR note: the applicant's social security number is 447038211\n"
        "per the signed verification form.\n"
    ),
    # Negative control: same 9 digits, no keyword anywhere near it.
    "pii-neg-order-number.txt": (
        "Facilities log: order number 447038211 shipped Tuesday.\n"
        "Pallet went to the loading dock without incident.\n"
    ),
    # HIGH: Luhn-valid card (industry-standard test PAN).
    "pii-cc-luhn-valid.txt": (
        "Procurement memo. Corporate card on file:\n"
        "4111 1111 1111 1111\n"
        "Expires next fiscal year; limit unchanged.\n"
    ),
    # Negative control: same shape, fails the Luhn checksum.
    "pii-cc-luhn-invalid.txt": (
        "Draft entry from the expense workshop demo:\n"
        "4111 1111 1111 1112\n"
        "Not a real card; typing practice only.\n"
    ),
    # MEDIUM: DOB requires its keyword prefix.
    "pii-dob-keyword.txt": (
        "Benefits enrollment worksheet.\n"
        "Date of birth: 04/12/1988\n"
        "Plan tier unchanged from last year.\n"
    ),
    # Negative control: identical date, no keyword prefix.
    "pii-neg-bare-date.txt": (
        "Calendar note: the audit kickoff moved to 04/12/1988.\n"
        "Room booked; dial-in unchanged.\n"
    ),
    # MEDIUM: three phone formats the regex must all catch.
    "pii-phone-formats.txt": (
        "Emergency contact card for the front office.\n"
        "Primary: (214) 555-0142\n"
        "Mobile: +1 214-555-0142\n"
        "Fax line: 2145550142\n"
    ),
    # MEDIUM: street-suffix address match.
    "pii-address-street.txt": (
        "Delivery instructions left by the previous coordinator:\n"
        "Ring the bell at 3505 Mockingbird Lane.\n"
    ),
    # MEDIUM: PO box plus state+ZIP both land in the address bucket.
    "pii-address-po-box.txt": (
        "Mail routing card.\n"
        "P.O. Box 1234, Dallas, TX 75201\n"
    ),
    # MEDIUM: email with a plus tag survives the regex.
    "pii-email-plus.txt": (
        "Newsletter signup used alex+signup@example.com\n"
        "Unsubscribe handled at the list level.\n"
    ),
    # MEDIUM: sensitive keywords only — no identifier shapes at all.
    "pii-keywords-confidential.txt": (
        "Sticky note found in the top drawer:\n"
        "api key rotated quarterly; password hint is the usual one.\n"
        "Treat this page as confidential.\n"
    ),
    # Filename-hint path: body is clean, the NAME carries tax_financial.
    "hint-filename-w2.txt": (
        "Scanned cover sheet. The interesting numbers live in the\n"
        "attached payroll packet, not on this page.\n"
    ),
    # Global negative control: nothing fires, file still queues cleanly.
    "pii-neg-clean-meeting.md": (
        "# Curriculum planning\n\n"
        "- Draft the fall schedule\n"
        "- Confirm the guest speaker\n"
        "- Book room 204\n"
    ),
}

LAYERS = {
    "pii-matrix": (PII_MATRIX, FIXTURES / "pii-matrix"),
}


def write_layer(files: dict[str, str], out: Path) -> int:
    out.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (out / name).write_text(content, encoding="utf-8")
    return len(files)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--layer", choices=sorted(LAYERS), help="write one layer only")
    args = parser.parse_args()

    wanted = [args.layer] if args.layer else sorted(LAYERS)
    for layer in wanted:
        files, out = LAYERS[layer]
        n = write_layer(files, out)
        print(f"{layer}: wrote {n} file(s) → {out.relative_to(PROJECT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
