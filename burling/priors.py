"""Deterministic PII priors (Loom Bet 2).

The model still reads the document. Regex does not replace that read — it is a
cross-check that cannot be talked out of an SSN. Hits are stored REDACTED so the
ledger itself is not a second copy of the sensitive file.

Best practice: fail closed on high-precision patterns (formatted SSN, Luhn-valid
card numbers). Use keyword context for noisier 9-digit blobs so zip codes and
order numbers do not flood the queue.
"""

from __future__ import annotations

import re
from pathlib import Path

# Formatted SSN / ITIN. Area 000/666/9xx and some SSA invalids still get flagged
# on purpose — a leftover personal file often has typos, and we would rather
# over-flag than miss.
SSN_FORMATTED = re.compile(r"\b(\d{3})[-\s](\d{2})[-\s](\d{4})\b")
SSN_KEYWORDS = re.compile(
    r"\b(ssn|ss#|social\s*security|itin|taxpayer\s*id|tin)\b",
    re.I,
)
NINE_DIGIT = re.compile(r"\b(\d{9})\b")

EMAIL = re.compile(r"\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b", re.I)
PHONE = re.compile(r"\b(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b")
DOB = re.compile(
    r"\b(?:dob|date of birth|born)\b[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
    re.I,
)
CC_CANDIDATE = re.compile(r"\b(?:\d[ -]*?){13,19}\b")

STREET = re.compile(
    r"\b\d{1,6}\s+[A-Za-z0-9][A-Za-z0-9.'\- ]{1,40}\s+"
    r"(?:St|Street|Ave|Avenue|Rd|Road|Ln|Lane|Blvd|Dr|Drive|Ct|Court|Way|Pkwy|Hwy|Highway)\.?\b",
    re.I,
)
STATE_ZIP = re.compile(r"\b[A-Z]{2}\s+\d{5}(?:-\d{4})?\b")
PO_BOX = re.compile(r"\bP\.?\s*O\.?\s*Box\s+\d+\b", re.I)

# Filename is evidence too. A W-2 named correctly should not wait on OCR.
FILENAME_HINTS = {
    "identity_document": re.compile(r"\b(ssn|social|passport|driver.?licen|dlscan|itin)\b", re.I),
    "tax_financial": re.compile(
        r"\b(w-?2|w-?4|1099|1040|tax|turbotax|bank.?stmt|routing|direct.?deposit|mortgage|deed)\b",
        re.I,
    ),
    "student_record": re.compile(r"\b(ferpa|transcript|iep|504|student.?id|gradebook|immunization)\b", re.I),
    "medical": re.compile(r"\b(hipaa|immunization|health.?record|rx|prescription|\btb\b)\b", re.I),
    "credentials_secrets": re.compile(r"\b(password|passwd|secret|api.?key|private.?key|\.pem|id_rsa)\b", re.I),
    "personal_correspondence": re.compile(r"\b(resume|cv_|personal|family|kids?|divorce|will)\b", re.I),
    "work_travel": re.compile(r"\b(travel|perkins.?travel|acte)\b", re.I),
}

SENSITIVE_KEYWORDS = re.compile(
    r"\b(social security|date of birth|driver'?s license|passport number|"
    r"routing number|account number|student id|medical record|"
    r"password|api key|private key|confidential)\b",
    re.I,
)


def luhn_ok(digits: str) -> bool:
    """Luhn checksum — the cheap way to tell a card number from a long ID."""
    if not digits.isdigit() or not (13 <= len(digits) <= 19):
        return False
    total = 0
    reverse = digits[::-1]
    for i, ch in enumerate(reverse):
        n = int(ch)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def _redact_ssn(a: str, b: str, c: str) -> str:
    return f"***-**-{c}"


def scan_text(text: str) -> dict:
    """Return counts + redacted samples. Never return the original identifier."""
    hits: dict[str, dict] = {}

    def add(kind: str, sample: str) -> None:
        bucket = hits.setdefault(kind, {"count": 0, "redacted_samples": []})
        bucket["count"] += 1
        if sample not in bucket["redacted_samples"] and len(bucket["redacted_samples"]) < 5:
            bucket["redacted_samples"].append(sample)

    for m in SSN_FORMATTED.finditer(text):
        add("ssn", _redact_ssn(*m.groups()))

    if SSN_KEYWORDS.search(text):
        for m in NINE_DIGIT.finditer(text):
            raw = m.group(1)
            # Skip obvious non-SSNs: years glued to zip-like values are still possible,
            # so we only keep 9-digit blobs that sit near an SSN keyword window.
            window = text[max(0, m.start() - 40) : m.end() + 40]
            if SSN_KEYWORDS.search(window):
                add("ssn", f"*****-{raw[-4:]}")

    for m in EMAIL.finditer(text):
        local, _, domain = m.group(0).partition("@")
        add("email", f"{local[:1]}***@{domain}")

    for m in PHONE.finditer(text):
        digits = re.sub(r"\D", "", m.group(0))
        add("phone", f"***-***-{digits[-4:]}")

    for m in DOB.finditer(text):
        add("dob", "**/**/****")

    for _ in STREET.finditer(text):
        add("address", "[street]")
    for _ in PO_BOX.finditer(text):
        add("address", "[po-box]")
    for _ in STATE_ZIP.finditer(text):
        add("address", "[st-zip]")

    for m in CC_CANDIDATE.finditer(text):
        digits = re.sub(r"\D", "", m.group(0))
        if luhn_ok(digits):
            add("credit_card", f"****-****-****-{digits[-4:]}")

    kw = SENSITIVE_KEYWORDS.findall(text)
    if kw:
        add("sensitive_keyword", ", ".join(sorted({k.lower() for k in kw})[:8]))

    return hits


def scan_filename(rel_path: str) -> list[str]:
    name = Path(rel_path).name
    tags = [tag for tag, rx in FILENAME_HINTS.items() if rx.search(name) or rx.search(rel_path)]
    return tags


def prior_severity(priors: dict) -> str:
    """high = identity/financial identifiers. medium = contact or address. low = none."""
    kinds = set(priors)
    if kinds & {"ssn", "credit_card"}:
        return "high"
    if kinds & {"dob", "email", "phone", "address", "sensitive_keyword"}:
        return "medium"
    return "low"


def has_pii(priors: dict) -> bool:
    """Any identifier-shaped hit. Builds the PII map; does not auto-delete."""
    return bool(set(priors) & {"ssn", "credit_card", "dob", "email", "phone", "address"})


def looks_like_personal_tax(filename_tags: list[str]) -> bool:
    """W-2 / TurboTax / mortgage in the path is personal paperwork, not CTE work."""
    return "tax_financial" in (filename_tags or [])
