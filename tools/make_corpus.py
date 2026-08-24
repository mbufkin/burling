#!/usr/bin/env python3
"""Deterministic synthetic corpus generator (docs/test-corpus.md).

Writes the fixture layers the test suite runs against. Seeded, offline,
no real identifiers: 555-01xx phones, example.com addresses, SSNs in
ranges SSA never issued (000/900) or the CONTRIBUTING-blessed document
example 123-45-6789. Run once; commit the output.

    python tools/make_corpus.py            # writes every implemented layer
    python tools/make_corpus.py --layer pii-matrix

Layers:
  pii-matrix           Layer 1 of docs/test-corpus.md — one positive and one
                       negative per priors.py detection class, plus filename-hint
                       and clean controls. Plain text, KB-scale.
  format-gauntlet      Layer 2 — every offline ingest path extract.py claims:
                       all text extensions, html stripping, rtf/docx/pptx/xlsx,
                       a hand-assembled text-layer PDF, a benign zip with junk
                       entries, unreadable dummies, and filename quirks.
  format-gauntlet-ocr  Layer 2 continuation — image-only scan PDF + PNG in
                       their own folder so offline CI can skip OCR cleanly.
"""

from __future__ import annotations

import argparse
import io
import zipfile
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

# ---------------------------------------------------------------------------
# Layer 2: format gauntlet. Every ingest bucket extract.py documents, plus
# the quirks. Expectations mirrored in test_format_gauntlet.py.
# ---------------------------------------------------------------------------

MARKER = "FORMAT GAUNTLET MARKER alpha bravo charlie"
TEXT_EXTS = ("txt", "text", "md", "markdown", "csv", "log", "rst", "json", "xml", "yml", "yaml")


def _marker(note: str) -> str:
    return f"{MARKER} via {note}.\n"


def _minimal_pdf(lines: list[str]) -> bytes:
    """Hand-assembled one-page PDF with a real Helvetica text layer."""
    escaped = [l.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") for l in lines]
    content = "\n".join(
        f"BT /F1 14 Tf 72 {720 - i * 22} Td ({line}) Tj ET" for i, line in enumerate(escaped)
    ).encode("latin-1")
    objects = [
        b"<</Type/Catalog/Pages 2 0 R>>",
        b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R"
        b"/Resources<</Font<</F1 5 0 R>>>>>>",
        b"<</Length " + str(len(content)).encode() + b">>stream\n" + content + b"\nendstream",
        b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>",
    ]
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for num, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{num} 0 obj".encode() + body + b"endobj\n"
    xref_at = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (
        f"trailer<</Size {len(objects) + 1}/Root 1 0 R>>\nstartxref\n{xref_at}\n%%EOF\n".encode()
    )
    return bytes(out)


def _office_zip(members: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, xml in members.items():
            zi = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            zi.external_attr = 0o644 << 16
            zf.writestr(zi, xml)
    return buf.getvalue()


def _build_format_gauntlet(out: Path) -> None:
    text_exts_dir = out / "text-exts"
    text_exts_dir.mkdir(parents=True, exist_ok=True)
    for ext in TEXT_EXTS:
        (text_exts_dir / f"sample.{ext}").write_text(_marker(f"the .{ext} reader"), encoding="utf-8")

    (out / "page.html").write_text(
        "<!doctype html><html><head><title>Dashboard</title>"
        "<style>.noise{color:red}</style>"
        "<script>var leak = 'SCRIPT_NOISE_MUST_NOT_SURVIVE';</script></head>"
        "<body><nav>Home About Contact</nav>"
        f"<main><p>{MARKER} in the body copy.</p></main></body></html>",
        encoding="utf-8",
    )

    (out / "doc.min.rtf").write_text(
        "{\\rtf1\\ansi FORMAT GAUNTLET MARKER alpha bravo charlie in rich text.\\par}",
        encoding="utf-8",
    )
    w_ns = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    (out / "doc.min.docx").write_bytes(
        _office_zip(
            {
                "[Content_Types].xml": "<?xml version='1.0'?><Types/>",
                "word/document.xml": (
                    f"<?xml version='1.0'?><w:document {w_ns}><w:body>"
                    f"<w:p><w:r><w:t>{MARKER} in word body.</w:t></w:r></w:p>"
                    "</w:body></w:document>"
                ),
            }
        )
    )
    (out / "doc.min.pptx").write_bytes(
        _office_zip(
            {
                "ppt/slides/slide1.xml": (
                    "<?xml version='1.0'?><slides xmlns:a='http://schemas.openxmlformats.org/drawingml/2006/main'>"
                    f"<body><a:p><a:r><a:t>{MARKER} on slide one.</a:t></a:r></a:p></body></slides>"
                ),
            }
        )
    )
    (out / "doc.min.xlsx").write_bytes(
        _office_zip(
            {
                "xl/sharedStrings.xml": (
                    "<?xml version='1.0'?><sst>"
                    f"<si><t>{MARKER} in shared strings.</t></si></sst>"
                ),
            }
        )
    )

    (out / "text-layer.pdf").write_bytes(
        _minimal_pdf([MARKER, "Second line for the pypdf reader."])
    )

    with zipfile.ZipFile(out / "benign.zip", "w") as zf:
        def add(name: str, data: bytes) -> None:
            zi = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            zi.external_attr = 0o644 << 16
            zf.writestr(zi, data)

        add("benign/a/b/one.txt", MARKER.encode())
        add("benign/two.txt", b"second queued member\n")
        add("benign/.DS_Store", b"")              # finder junk: never written
        add("__MACOSX/benign_two.txt", b"junk")   # resource fork: never written

    unreadable = out / "unreadable"
    unreadable.mkdir(exist_ok=True)
    for name, magic in (
        ("dummy.gif", b"GIF89a\x01"),
        ("dummy.mp3", b"ID3\x03\x00"),
        ("dummy.exe", b"MZ\x90\x00"),
    ):
        (unreadable / name).write_bytes(magic + b"\x00" * 4)

    quirk = out / "quirk"
    (quirk / "deep" / "a" / "b" / "c" / "d" / "e" / "f").mkdir(parents=True, exist_ok=True)
    (quirk / "deep" / "a" / "b" / "c" / "d" / "e" / "f" / "leaf.txt").write_text(
        _marker("six-deep nesting"), encoding="utf-8"
    )
    (quirk / "caf\u00e9-menu-\u00e9clair.txt").write_text(
        _marker("unicode filenames"), encoding="utf-8"
    )
    (quirk / "report. pdf").write_bytes(b"%PDF-not-really\x00garbage")

    site = out / "site"
    (site / "dashboard_files").mkdir(parents=True, exist_ok=True)
    (site / "dashboard.html").write_text(_marker("saved web page"), encoding="utf-8")
    (site / "dashboard_files" / "style.css").write_text(".x{color:red}", encoding="utf-8")
    (site / "dashboard_files" / "app.js").write_text("console.log(1);", encoding="utf-8")


def _build_format_gauntlet_ocr(out: Path) -> bool:
    """Image-only scan PDF + its source PNG. Needs pymupdf to render."""
    try:
        import pymupdf
    except ImportError:
        print("format-gauntlet-ocr: pymupdf unavailable, scan fixtures skipped")
        return False
    out.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    page.insert_textbox(
        pymupdf.Rect(72, 72, 540, 500),
        "FORMAT GAUNTLET\nSCAN ONLY PAGE\nNO TEXT LAYER HERE",
        fontname="helv",
        fontsize=30,
    )
    png = out / "scan-page.png"
    page.get_pixmap(dpi=150).save(str(png))
    doc.close()
    sdoc = pymupdf.open()
    spage = sdoc.new_page(width=612, height=792)
    spage.insert_image(spage.rect, filename=str(png))
    sdoc.save(str(out / "scanned-no-text-layer.pdf"))
    sdoc.close()
    return True


# ---------------------------------------------------------------------------
# Layer 3: organize drama. ~68 docs across all 13 approved mains with a
# scripted story: near-duplicate pairs for combine, one mixed drawer, one
# high-severity unplaceable (andon tripwire), low-severity junk that must
# still bin, personal/life files, and no-substance empties. labels.json is
# the ground truth scored by burling/score_placements.py.
# ---------------------------------------------------------------------------

# (rel_path, main, sub, body). Bodies are deliberately plain — the drama is
# in the filing decisions, not the prose.
DRAMA: list[tuple[str, str, str, str]] = [
    ("personnel/policies/offer-letter-jane-okafor.txt", "personnel", "policies",
     "Dear Jane Okafor, we are pleased to offer you the quality analyst position "
     "at a starting salary of seventy-two thousand dollars per year."),
    ("personnel/policies/travel-expense-policy.txt", "personnel", "policies",
     "Employees must submit travel receipts within thirty days. Per diem rates "
     "apply for overnight trips and require manager pre-approval."),
    ("personnel/cases/performance-review-q2-marcus.txt", "personnel", "cases",
     "Q2 review for Marcus: exceeded goals on the migration project; coaching "
     "area is delegating code review follow-ups."),
    ("personnel/cases/harassment-complaint-intake.txt", "personnel", "cases",
     "Intake summary for a workplace conduct complaint. Routed to HR business "
     "partner; investigation window opens within five business days."),
    ("personnel/records/benefits-enrollment-form.txt", "personnel", "benefits",
     "Benefits enrollment: medical plan B, dental family tier, forty-one percent "
     "of the premium is employee paid."),

    ("operations/schedules/production-schedule-march.txt", "operations", "schedules",
     "March production schedule: line one runs weekday dayshift, line two adds "
     "a weekend shift starting the second week."),
    ("operations/incidents/db-outage-postmortem.txt", "operations", "incidents",
     "Postmortem for the March database outage: root cause was a connection-pool "
     "exhaustion after the nightly vacuum job overran."),
    ("operations/incidents/conveyor-jam-report.txt", "operations", "incidents",
     "Conveyor belt jam at station four cleared in eleven minutes; sensor bracket "
     "loosened and re-torqued."),
    ("operations/planning/capacity-plan-h2.txt", "operations", "planning",
     "Second-half capacity plan assumes twelve percent order growth and one "
     "additional packaging cell coming online in October."),
    ("operations/logs/shift-handoff-week12.txt", "operations", "logs",
     "Week twelve handoff notes: punch list carried over two items; forklift "
     "three back in service after its service interval."),
    ("operations/logs/delivery-receiving-log.txt", "operations", "logs",
     "Receiving log for Thursday: three pallets of corrugate, one late freight "
     "arriving after the dock cut-off."),

    ("administration/policies/records-retention-policy.txt", "administration", "policies",
     "Records retention: invoices seven years, meeting minutes permanent, "
     "recruiting files two years from hire decision."),
    ("administration/policies/front-desk-rota.txt", "administration", "policies",
     "Front desk rotation covers reception from eight to five with lunch "
     "crossover at noon shared with the mail room."),
    ("administration/minutes/all-hands-minutes-january.txt", "administration", "minutes",
     "January all-hands minutes: revenue recap, two promotions announced, and "
     "the parking garage repair timeline moved up."),
    ("administration/minutes/supply-committee-minutes-february.txt", "administration", "minutes",
     "Supply committee minutes: approve standing order for toner and switch "
     "coffee vendor after the March tasting."),

    ("finance/budget/q3-budget-draft.txt", "finance", "budget",
     "Quarter three budget draft: travel flat, software renewals up six "
     "percent, contingency held at four percent of operating spend."),
    ("finance/budget/travel-budget-scenario.txt", "finance", "budget",
     "Travel budget scenario B caps conference attendance at two per team "
     "and moves regional visits to video-first."),
    ("finance/invoices/invoice-acme-0042.txt", "finance", "invoices",
     "Invoice ACME-0042 for consulting services rendered in April, net "
     "thirty days, purchase order referenced on line one."),
    ("finance/invoices/invoice-globex-0077.txt", "finance", "invoices",
     "Invoice GLOBEX-0077 covering managed services for May, payable net "
     "forty-five, remit to the lockbox address."),
    ("finance/payroll/payroll-calendar-2025.txt", "finance", "payroll",
     "Payroll calendar for 2025: twenty-six pay dates, biweekly Fridays, "
     "year-end adjustment run in mid-December."),
    ("finance/reimbursements/mileage-expense-claim.txt", "finance", "reimbursements",
     "Mileage claim for site visits: one hundred forty miles round trip at "
     "the standard rate, attached toll receipts."),
    ("finance/vendors/vendor-payment-list-2024.txt", "finance", "vendors",
     "Vendor payment list 2024: Acme Consulting, Globex Facilities, Initech "
     "Supplies, Umbrella Logistics with quarterly totals."),
    ("finance/vendors/vendor-payment-list-2025.txt", "finance", "vendors",
     "Vendor payment list 2025: Acme Consulting, Globex Facilities, Initech "
     "Supplies, Umbrella Logistics with quarterly totals."),

    ("legal/templates/nda-template.txt", "legal", "templates",
     "Mutual non-disclosure agreement template: definition of confidential "
     "information, three-year term, carve-outs for public knowledge."),
    ("legal/holds/litigation-hold-notice.txt", "legal", "holds",
     "Litigation hold: preserve all correspondence regarding the delivery "
     "dispute until counsel releases the hold in writing."),
    ("legal/trademarks/trademark-renewal-filing.txt", "legal", "trademarks",
     "Trademark renewal filing for the house mark, specimen attached, "
     "declaration of continued use due this quarter."),
    ("legal/leases/warehouse-lease-summary.txt", "legal", "leases",
     "Warehouse lease summary: five-year term, three percent annual "
     "escalator, tenant responsible for interior maintenance."),

    ("technology/design/api-gateway-design-notes.txt", "technology", "design",
     "API gateway design notes: rate limiting at the edge, request id "
     "propagation, and circuit breakers per upstream service."),
    ("technology/architecture/office-wifi-upgrade-plan.txt", "technology", "architecture",
     "Office wifi upgrade plan: access point survey, channel plan for dense "
     "areas, cutover scheduled for a Friday evening."),
    ("technology/runbooks/database-backup-runbook.txt", "technology", "runbooks",
     "Database backup runbook: nightly full at two, hourly incrementals, "
     "restore drill every quarter with timing captured."),
    ("technology/runbooks/laptop-imaging-guide.txt", "technology", "runbooks",
     "Laptop imaging guide: base image, security agent enrollment steps, "
     "and the local admin password escrow procedure."),
    ("technology/retros/sprint-42-retro.txt", "technology", "retros",
     "Sprint forty-two retro: liked the shorter release train, wondered about "
     "flaky end-to-end tests, action to add a smoke suite."),

    ("customers/acme/acme-kickoff-notes.txt", "customers", "acme",
     "Acme kickoff notes: success criteria agreed, weekly status call set "
     "for Tuesdays, escalation path through their program manager."),
    ("customers/acme/acme-qbr-deck-outline.txt", "customers", "acme",
     "Acme quarterly business review outline: adoption metrics, open tickets "
     "trend, and the roadmap ask for single sign-on."),
    ("customers/acme/acme-renewal-risk-call.txt", "customers", "acme",
     "Renewal risk call with Acme: pricing concerns raised, counterproposal "
     "to trade term length for a usage discount."),
    ("customers/globex/globex-support-history.txt", "customers", "globex",
     "Globex support history: fourteen tickets this quarter, mostly access "
     "provisioning, one sev-two resolved same day."),
    ("customers/surveys/customer-feedback-spring.txt", "customers", "surveys",
     "Spring customer feedback survey: response rate nine percent, top ask "
     "is bulk export, net promoter score steady."),

    ("facilities/logs/hvac-maintenance-log.txt", "facilities", "logs",
     "HVAC maintenance log: filters replaced on schedule, compressor two "
     "showing early wear, monitor monthly."),
    ("facilities/logs/key-card-audit-log.txt", "facilities", "logs",
     "Key card audit log: inventory reconciled, eleven cards retired for "
     "departed staff, two spares missing."),
    ("facilities/policies/parking-permit-policy.txt", "facilities", "policies",
     "Parking permit policy: two vehicles per employee, overflow lot opens "
     "in November once the garage repair finishes."),
    ("facilities/policies/loading-dock-hours.txt", "facilities", "policies",
     "Loading dock hours: deliveries accepted seven to three, appointments "
     "required for palletized freight."),

    ("security/incidents/badge-tailgate-incident.txt", "security", "incidents",
     "Badge tailgating incident at the east entrance: contractor followed "
     "through the man-trap, refresher briefing scheduled."),
    ("security/incidents/phishing-drill-results.txt", "security", "incidents",
     "Phishing drill results: click rate down to six percent, report button "
     "usage doubled since the last exercise."),
    ("security/policies/visitor-badge-policy.txt", "security", "policies",
     "Visitor badge policy: escorts required beyond the lobby, badges "
     "returned to the kiosk at departure."),
    ("security/tickets/firewall-change-ticket.txt", "security", "tickets",
     "Firewall change ticket: open port range for the new file transfer "
     "host, approved by network owner, revert plan attached."),

    ("communications/press/press-release-product-launch.txt", "communications", "press",
     "Press release draft for the product launch: embargo date, spokesperson "
     "quotes, and the analyst preview list."),
    ("communications/internal/newsletter-april-draft.txt", "communications", "internal",
     "April newsletter draft: volunteer day recap, new hires spotlight, and "
     "the cafeteria survey link."),
    ("communications/internal/all-hands-slides-outline.txt", "communications", "internal",
     "All-hands slides outline: quarter results, org updates, question "
     "queue moderated by the town hall team."),
    ("communications/crisis/crisis-comms-holding-statement.txt", "communications", "crisis",
     "Crisis communications holding statement template: acknowledge, commit "
     "to updates on a stated cadence, route press to the duty officer."),

    ("training/plans/newhire-training-plan.txt", "training", "plans",
     "New hire training plan: week one orientation, week two shadowing, "
     "thirty-day check-in with the hiring manager."),
    ("training/certifications/forklift-cert-records.txt", "training", "certifications",
     "Forklift certification records: renewal dates by operator, expired "
     "cards flagged for the safety coordinator."),
    ("training/compliance/compliance-training-deadlines.txt", "training", "compliance",
     "Compliance training deadlines: data handling module due end of month, "
     "harassment prevention every two years."),
    ("training/mentoring/mentor-program-guidelines.txt", "training", "mentoring",
     "Mentor program guidelines: pairings run two quarters, monthly one-on-"
     "ones, structured goal sheet at kickoff."),

    ("health/assessments/ergonomics-assessment-desk.txt", "health", "assessments",
     "Ergonomics assessment: monitor riser requested, chair lumbar support "
     "adjusted, follow-up in two weeks."),
    ("health/clinics/flu-shot-clinic-signup.txt", "health", "clinics",
     "Flu shot clinic signup: clinic runs in the multipurpose room, slots "
     "every ten minutes, insurance card needed."),
    ("health/inventory/first-aid-kit-inventory.txt", "health", "inventory",
     "First aid kit inventory: bandages restocked, eye wash expires next "
     "quarter, AED pads within date."),
    ("health/events/wellness-fair-flyer.txt", "health", "events",
     "Wellness fair flyer: vendor booths, biometric screening sign-ups, "
     "and a lunchtime walking club table."),

    ("personal/family/family-chili-recipe.txt", "personal", "family",
     "Family chili recipe: two cans of beans, chipotle in adobo, simmer "
     "low for an hour, cornbread on the side."),
    ("personal/family/soccer-car-pool-schedule.txt", "personal", "family",
     "Soccer car pool schedule: Saturdays at nine, my weeks are the odd "
     "ones, field three at the middle school."),
    ("personal/hobbies/guitar-lesson-notes.txt", "personal", "hobbies",
     "Guitar lesson notes: barre chord progressions, practice the circle "
     "of fifths exercise ten minutes daily."),
    ("personal/hobbies/delta-kite-build-plan.txt", "personal", "hobbies",
     "Delta kite build plan: ripstop nylon panels, carbon spar sizes, and "
     "the bridle adjustment notes from last flight."),

    # Mixed drawer: one head word (project-alpha), three different missions.
    # A naive head-word filer groups them; a good clerk splits them.
    ("mixed/project-alpha-budget.txt", "finance", "budget",
     "Project alpha budget: hardware capex split across two quarters, "
     "contingency released only by the steering group."),
    ("mixed/project-alpha-roster.txt", "personnel", "rosters",
     "Project alpha roster: staffing assignments, loan agreements for the "
     "two borrowed engineers, backfill requests pending."),
    ("mixed/project-alpha-press.txt", "communications", "press",
     "Project alpha press plan: announcement timing, media training for "
     "the product lead, embargo agreements to sign."),

    # Low-severity leftovers: must bin to unmapped normally.
    ("special/unsubscribe-confirmations.txt", "unmapped", "",
     "Please remove me from this list. Me too. Unsubscribe. Take me off "
     "this thread entirely."),
    ("special/me-too-thread.txt", "unmapped", "",
     "Me too. Same issue here. Any update? Closing this notification "
     "thread without further action."),

    # No-substance empty: extraction yields whitespace, never reaches a model.
    ("scratch/empty-scratch.txt", "unmapped", "", "   \n\n   \t\n"),
]

# The andon tripwire. High severity comes from the synthetic SSN in the body;
# unplaceable because there is no topical mission — it is raw export garbage.
# Until an operator assigns it a home, filing must halt, not bin.
ANDON_DOC = "special/legacy-export.txt"
ANDON_BODY = (
    "automated export job output\n"
    "row checksums follow; no subject matter\n"
    "f3a9c0e1b7d2465aa8c19d3e5f7011bb\n"
    "99112-3344-77 88231-0091-3 123-45-6789\n"
    "0000ff21 8c31aa07 d94b1200 e55f6682\n"
)


def _build_organize_drama(out: Path) -> None:
    import json as _json

    out.mkdir(parents=True, exist_ok=True)
    labels: dict[str, dict] = {}
    for rel, main, sub, body in DRAMA:
        path = out / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body + "\n", encoding="utf-8")
        labels[rel] = {"main": main, "sub": sub}

    path = out / ANDON_DOC
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(ANDON_BODY + "\n", encoding="utf-8")
    # Ground truth AFTER an operator assigns the kept file a home.
    labels[ANDON_DOC] = {
        "main": "security",
        "sub": "credentials",
        "note": "andon-kept until an operator assigns a home; see test_organize_drama",
    }

    (out / "labels.json").write_text(
        _json.dumps(labels, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_layer(files: dict[str, str], out: Path) -> int:
    out.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (out / name).write_text(content, encoding="utf-8")
    return len(files)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--layer",
        choices=["all", "pii-matrix", "format-gauntlet", "format-gauntlet-ocr", "organize-drama"],
        help="write one layer only (default: all)",
    )
    args = parser.parse_args()

    if args.layer in (None, "all", "pii-matrix"):
        n = write_layer(PII_MATRIX, FIXTURES / "pii-matrix")
        print(f"pii-matrix: wrote {n} file(s) → burling/tests/fixtures/pii-matrix")
    if args.layer in (None, "all", "format-gauntlet"):
        _build_format_gauntlet(FIXTURES / "format-gauntlet")
        print("format-gauntlet: wrote → burling/tests/fixtures/format-gauntlet")
    if args.layer in (None, "all", "format-gauntlet-ocr"):
        if _build_format_gauntlet_ocr(FIXTURES / "format-gauntlet-ocr"):
            print("format-gauntlet-ocr: wrote → burling/tests/fixtures/format-gauntlet-ocr")
    if args.layer in (None, "all", "organize-drama"):
        _build_organize_drama(FIXTURES / "organize-drama")
        print(f"organize-drama: wrote {len(DRAMA) + 1} docs + labels.json → burling/tests/fixtures/organize-drama")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
