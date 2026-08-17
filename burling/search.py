"""Keyword search over the local handover dump — no model, no cloud.

Use this when the question is retrieval, not delete/keep. Example:

    python -m burling.search --intake burling/corpus --preset summer-pd-travel

Best practice:
1. Score the filename first. Travel forms are usually named after the traveler.
2. Then extract text and search it, so a generic ``Hotel receipt.pdf`` still hits.
3. Require more than one signal (travel AND PD/conference) so a tax return that
   mentions ``summer`` does not rank.
4. Redact SSN / card numbers in snippets. The report is still a work product;
   it should not become a second copy of identity documents.
5. Encrypted PDFs stay in the result list from the filename. We do not skip them.
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
import warnings
from datetime import date
from pathlib import Path

from burling.extract import UNREADABLE_EXTENSIONS, extract_text, iter_source_files
from burling.io_util import atomic_write, atomic_write_json
from burling.paths import load_config, output_dir
from burling.priors import SSN_FORMATTED, looks_like_personal_tax, scan_filename

# --- query preset: who traveled for PD this summer --------------------------------

# Filename tokens that mean "this is a travel packet", not a curriculum PDF.
TRAVEL_NAME = re.compile(
    r"\b(travel|traveler|hotel|itinerary|mileage|milage|airfare|lodging|"
    r"per.?diem|boarding.?pass)\b",
    re.I,
)
# Conference / PD events that show up in this CTE dump.
PD_EVENT_NAME = re.compile(
    r"\b(pd|professional.?development|conference|acte|naf.?next|tiva|thoa|"
    r"atat|certiport|ed.?rising|workshop|training|vision.?20)\b",
    re.I,
)
SUMMER_NAME = re.compile(
    r"\b(summer|june|july|august|2025|2026)\b",
    re.I,
)
# Local in-district PD (rooms + schedule) is not the same as travel.
LOCAL_PD_NAME = re.compile(r"\b(summer.?pd|pd.?summer)\b", re.I)

# Text must hit at least one travel term and one PD/event term to count as
# "traveled for professional development" when the filename is generic.
TRAVEL_TEXT = re.compile(
    r"\b(travel(?:er|ing)?|hotel|lodging|airfare|mileage|per.?diem|"
    r"itinerary|preferred departure|arta travel|conference/event)\b",
    re.I,
)
PD_TEXT = re.compile(
    r"\b(professional development|\bpd\b|conference|workshop|acte|"
    r"naf next|tiva|thoa|summer pd|cte summer)\b",
    re.I,
)
YEAR_RX = re.compile(r"\b(2025|2026)\b")
MONTH_RX = re.compile(
    r"\b(may|june|july|august|jun|jul|aug)\b|\b(0?[5-8])[/-](0?[1-9]|[12]\d|3[01])[/-](2025|2026)\b",
    re.I,
)

# Words that look like names in a filename but are the form, the district, or the event.
FILENAME_NOISE = {
    "dallas", "isd", "dallasisdtravel", "travel", "form", "forms", "signed",
    "grant", "docs", "conference", "hotel", "naf", "next", "acte", "best",
    "practices", "practice", "revised", "secured", "google", "maps", "mileage",
    "milage", "from", "texas", "omni", "corpus", "christi", "itinerary",
    "badge", "meals", "meeting", "receipt", "recipe", "summer", "schedule",
    "feedback", "perkins", "tiva", "thoa", "atat", "certified", "educator",
    "preauthorization", "agenda", "parking", "receipts", "bank", "statement",
    "vision", "and", "the", "for", "to", "of", "pdf", "docx", "key",
}

# Labelled fields on Dallas ISD / grant travel forms.
LABELLED_NAME = re.compile(
    r"(?i)(?:traveler(?:'s)?\s*name|employee\s*name|guest\s*name|"
    r"participant(?:'s)?\s*name|name of (?:the )?(?:traveler|employee|guest))"
    r"[:\s]+([A-Z][A-Za-z.'\-]+(?:\s+[A-Z][A-Za-z.'\-]+){0,3})"
)

# ``A Goodson Travel``, ``L. Sanchez-Munoz Travel``, ``R. Coleman NAF``
LEADING_PERSON = re.compile(
    r"^([A-Z](?:\.[A-Z])?\.?\s+[A-Z][A-Za-z.'\-]+(?:\s+[A-Z][A-Za-z.'\-]+)?)"
    r"(?:\s*[-_]\s*|\s+)(?:travel|naf|hotel|conference|thoa|tiva|atat)",
    re.I,
)
# ``C.Seay- 2025 Certified Educator Conference`` (no space after the initial)
GLUED_INITIAL = re.compile(r"^([A-Z]\.[A-Z][A-Za-z.'\-]+)\s*[-–]")
# ``BAUTISTA_TIVA GRANT TRAVEL``, ``Jeremy Spence_NAF Next``
UNDERSCORE_PERSON = re.compile(
    r"^([A-Za-z][A-Za-z.'\-]+(?:\s+[A-Za-z][A-Za-z.'\-]+)?)_([A-Za-z][A-Za-z.'\-]+)"
)
# ``DallasISDTravel - ACTE Best Practices - JS``
TRAILING_INITIALS = re.compile(r"[-–]\s*([A-Z]{1,3})\s*$")
# ``Badge-Demars``, ``statement-Palmer``
HYPHEN_SURNAME = re.compile(
    r"(?:badge|statement|itinerary|form)[- _]([A-Z][A-Za-z.'\-]+)",
    re.I,
)
# ``Becerra Milage``, ``Jones-Gunter THOA Travel``
SURNAME_THEN_TRAVEL = re.compile(
    r"^([A-Z][A-Za-z.'\-]+(?:-[A-Z][A-Za-z.'\-]+)?)\s+"
    r"(?:milage|mileage|thoa|tiva|travel)",
    re.I,
)
# Gaylord / hotel folio: ``SPENCE/J`` sitting on the NAME line
FOLIO_LAST_INITIAL = re.compile(r"\b([A-Z]{3,})/([A-Z])\b(?=.{0,40}NAME)", re.S)
# ``Spence-Uber-NAF Conference``
SURNAME_UBER = re.compile(r"^([A-Z][A-Za-z.'\-]+)-Uber\b", re.I)

SKIP_NAME_RX = re.compile(
    r"\b(w-?2|w-?4|1099|1040|tax.?return|turbotax|immunization|mortgage)\b",
    re.I,
)
MAX_EXTRACT_BYTES = 8_000_000
SNIPPET_RADIUS = 90


def normalize_text(text: str) -> str:
    """Collapse ``S U M M E R`` style PDF titles so keyword search can match."""
    collapsed = re.sub(r"(?<=\b[A-Za-z]) (?=[A-Za-z]\b)", "", text)
    return collapsed


def redact_snippet(text: str) -> str:
    """Strip identity numbers from a short quote. Names stay — that is the question."""
    text = SSN_FORMATTED.sub(lambda m: f"***-**-{m.group(3)}", text)
    text = re.sub(r"\b\d{3}-\d{2}-\d{4}\b", "***-**-****", text)
    text = re.sub(
        r"\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b",
        lambda m: m.group(0)[0] + "***@" + m.group(0).split("@", 1)[1],
        text,
        flags=re.I,
    )
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _bare_stem(filename: str) -> str:
    """Strip stacked ``.pdf (SECURED).pdf`` suffixes these Drive copies use."""
    name = Path(filename).name
    name = re.sub(r"\s*\(SECURED\)", "", name, flags=re.I)
    name = re.sub(r"(\.pdf|\.docx|\.txt|\.md)+$", "", name, flags=re.I)
    name = re.sub(r"\s*\(\d+\)\s*$", "", name)
    return name.strip()


def names_from_filename(filename: str) -> list[str]:
    """Pull a likely traveler from how these packets were named.

    Best practice: filename is often more reliable than OCR on a signed scan.
    Keep the parser conservative — skip district/event words rather than inventing people.
    """
    original = _bare_stem(filename)
    # Underscores stay for LAST_EVENT packets; spaces help ``Jeremy Spence NAF``.
    spaced = original.replace("_", " ")
    found: list[str] = []

    m = LEADING_PERSON.search(spaced)
    if m:
        found.append(_clean_person(m.group(1)))

    m = GLUED_INITIAL.search(spaced)
    if m:
        found.append(_clean_person(m.group(1)))

    m = UNDERSCORE_PERSON.match(original)
    if m:
        left, right = m.group(1), m.group(2)
        if left.lower() not in FILENAME_NOISE and right.lower() in {
            "tiva", "thoa", "naf", "acte", "atat", "grant",
        }:
            found.append(_clean_person(left.title() if left.isupper() else left))
        elif (
            left.lower() not in FILENAME_NOISE
            and right.lower() not in FILENAME_NOISE
            and " " in left
        ):
            found.append(_clean_person(left))

    m = TRAILING_INITIALS.search(spaced)
    if m and "travel" in spaced.lower():
        found.append(m.group(1))

    m = HYPHEN_SURNAME.search(spaced)
    if m and m.group(1).lower() not in FILENAME_NOISE:
        found.append(_clean_person(m.group(1)))

    m = SURNAME_THEN_TRAVEL.search(spaced)
    if m and m.group(1).lower() not in FILENAME_NOISE:
        found.append(_clean_person(m.group(1)))

    m = SURNAME_UBER.search(spaced)
    if m:
        found.append(_clean_person(m.group(1)))

    return _uniq(found)


def names_from_text(text: str) -> list[str]:
    found = []
    for m in LABELLED_NAME.finditer(text):
        name = _clean_person(m.group(1))
        if name.lower() not in FILENAME_NOISE:
            found.append(name)
    for m in FOLIO_LAST_INITIAL.finditer(text):
        found.append(_clean_person(f"{m.group(1).title()}/{m.group(2)}"))
    return _uniq(found)


def _clean_person(name: str) -> str:
    name = re.sub(r"\s+", " ", name).strip(" -_,.")
    return name


def _uniq(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = item.lower()
        if not item or key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def years_in(text: str) -> list[str]:
    """Prefer four-digit years; also read hotel folio dates like 07/05/26."""
    years = list(YEAR_RX.findall(text))
    for m in re.finditer(r"\b0?[5-8]/\d{1,2}/(25|26)\b", text):
        years.append("20" + m.group(1))
    if re.search(r"naf next\s*26\b", text, re.I):
        years.append("2026")
    return _uniq(years)


def classify_hit(filename: str, text: str) -> str:
    """Bucket a file so the report separates travel from in-district PD."""
    name = filename.lower()
    # Campus summer-PD schedules are local. Conference/hotel packets are travel.
    if LOCAL_PD_NAME.search(name) and not TRAVEL_NAME.search(name):
        return "local_pd"
    travel = bool(TRAVEL_NAME.search(name) or TRAVEL_TEXT.search(text))
    conference = bool(
        re.search(r"\b(conference|naf.?next|acte|tiva|thoa|hotel|uber)\b", name, re.I)
    )
    pd = bool(PD_EVENT_NAME.search(name) or PD_TEXT.search(text) or LOCAL_PD_NAME.search(name))
    if (travel and pd) or conference:
        return "pd_travel"
    if travel:
        return "travel"
    if pd:
        return "pd_related"
    return "weak"


def score_file(filename: str, text: str) -> int:
    """Higher = more likely to answer 'who traveled for PD this summer'."""
    name = filename.lower()
    blob = f"{filename}\n{text}"
    score = 0
    if TRAVEL_NAME.search(name):
        score += 8
    if PD_EVENT_NAME.search(name):
        score += 4
    if SUMMER_NAME.search(name):
        score += 2
    if TRAVEL_TEXT.search(text):
        score += 5
    if PD_TEXT.search(text):
        score += 4
    if MONTH_RX.search(blob):
        score += 2
    if "2026" in blob:
        score += 3
    elif "2025" in blob:
        score += 1
    if names_from_filename(filename) or names_from_text(text):
        score += 4
    if SKIP_NAME_RX.search(name):
        score -= 20
    return score


def snippets(text: str, patterns: list[re.Pattern[str]], limit: int = 3) -> list[str]:
    hits: list[str] = []
    for rx in patterns:
        for m in rx.finditer(text):
            start = max(0, m.start() - SNIPPET_RADIUS)
            end = min(len(text), m.end() + SNIPPET_RADIUS)
            hits.append(redact_snippet(text[start:end]))
            if len(hits) >= limit:
                return hits
    return hits


def filename_is_candidate(name: str) -> bool:
    """Cheap cull. Do not open every curriculum PDF in a 1,000-file dump.

    Best practice for this question: if the name has no travel/PD/conference
    signal, the file is almost never a traveler packet. We still keep a
    filename-only row when the score is high enough without text.
    """
    return bool(
        TRAVEL_NAME.search(name)
        or PD_EVENT_NAME.search(name)
        or LOCAL_PD_NAME.search(name)
    )


def should_extract(path: Path) -> bool:
    """Skip binaries, tax packets, huge agendas, and off-topic files."""
    if path.suffix.lower() in UNREADABLE_EXTENSIONS:
        return False
    if path.suffix.lower() in {".key", ".numbers"}:
        return False
    tags = scan_filename(path.name)
    if looks_like_personal_tax(tags):
        return False
    if SKIP_NAME_RX.search(path.name):
        return False
    if not filename_is_candidate(path.name):
        return False
    if path.stat().st_size > MAX_EXTRACT_BYTES and not TRAVEL_NAME.search(path.name):
        return False
    return True


def search_tree(root: Path) -> list[dict]:
    """Walk ``root`` and return ranked hits. One file, one record."""
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    warnings.filterwarnings("ignore", message=".*FloatObject.*")
    rows: list[dict] = []
    files = iter_source_files(root)
    for i, path in enumerate(files, start=1):
        if i % 100 == 0:
            print(f"  scanned {i}/{len(files)} files...", flush=True)
        rel = path.relative_to(root).as_posix()
        # GOLDEN RULE: one file must not kill the run. Note it and continue.
        try:
            text = ""
            method = "filename-only"
            error = None
            if should_extract(path):
                try:
                    raw, method = extract_text(path)
                    text = normalize_text(raw)
                except Exception as exc:
                    error = str(exc)
                    method = "failed"
            score = score_file(path.name, text)
            kind = classify_hit(path.name, text)
            if score < 6 and kind == "weak":
                continue
            names = _uniq(names_from_filename(path.name) + names_from_text(text))
            rows.append(
                {
                    "rel_path": rel,
                    "filename": path.name,
                    "score": score,
                    "kind": kind,
                    "years": years_in(f"{path.name}\n{text}") or years_in(path.name),
                    "names": names,
                    "extraction_method": method,
                    "extraction_error": error,
                    "snippets": snippets(text, [TRAVEL_TEXT, PD_TEXT, MONTH_RX]),
                }
            )
        except Exception as exc:
            print(f"  NOTED [search] {rel}: {type(exc).__name__}: {exc}", flush=True)
    rows.sort(key=lambda r: (-r["score"], r["rel_path"].lower()))
    return rows


def people_index(rows: list[dict], this_year: str) -> dict[str, dict]:
    """Roll file hits up to people. That is the actual question."""
    people: dict[str, dict] = {}
    for row in rows:
        if row["kind"] not in {"pd_travel", "travel"}:
            continue
        if not row["names"]:
            continue
        for name in row["names"]:
            bucket = people.setdefault(
                name,
                {"name": name, "years": [], "files": [], "kinds": [], "this_summer": False},
            )
            bucket["files"].append(row["rel_path"])
            bucket["kinds"].append(row["kind"])
            for year in row["years"]:
                if year not in bucket["years"]:
                    bucket["years"].append(year)
            if this_year in row["years"] or (
                not row["years"] and this_year == "2026" and row["score"] >= 10
            ):
                bucket["this_summer"] = this_year in row["years"]
    return people


def render_report(root: Path, rows: list[dict], this_year: str) -> str:
    people = people_index(rows, this_year)
    this_summer = [p for p in people.values() if this_year in p["years"]]
    other = [p for p in people.values() if this_year not in p["years"]]
    local = [r for r in rows if r["kind"] == "local_pd"]
    encrypted = [r for r in rows if r.get("extraction_error")]

    lines = [
        "# Summer PD travel search",
        "",
        f"Question: who traveled for professional development this summer ({this_year})?",
        f"Corpus: `{root}`",
        f"Files scored: {len(rows)} (weak / tax / binary files were skipped)",
        "",
        "Method: Python filename + extracted-text search. No model. SSN/email redacted in snippets.",
        "Travel forms and hotel/conference packets count as travel. A campus summer-PD schedule does not.",
        "",
        f"## People with travel packets dated {this_year}",
        "",
    ]
    if this_summer:
        for person in sorted(this_summer, key=lambda p: p["name"].lower()):
            files = "; ".join(f"`{f}`" for f in person["files"][:8])
            lines.append(f"- **{person['name']}** — years {', '.join(person['years']) or 'unspecified'} — {files}")
    else:
        lines.append("_No traveler named in a 2026-dated travel packet yet. See filename-only / 2025 below._")

    lines += ["", "## People on travel packets (year missing or 2025)", ""]
    if other:
        for person in sorted(other, key=lambda p: p["name"].lower()):
            files = "; ".join(f"`{f}`" for f in person["files"][:8])
            years = ", ".join(person["years"]) or "year not in filename/text"
            lines.append(f"- **{person['name']}** — {years} — {files}")
    else:
        lines.append("_None._")

    lines += ["", "## Local summer PD (not travel)", ""]
    if local:
        for row in local[:20]:
            lines.append(f"- `{row['rel_path']}` (score {row['score']})")
    else:
        lines.append("_None._")

    lines += ["", "## Ranked evidence files", ""]
    for row in rows:
        if row["score"] < 8:
            continue
        names = ", ".join(row["names"]) or "—"
        years = ", ".join(row["years"]) or "—"
        err = f" — extract failed: {row['extraction_error']}" if row["extraction_error"] else ""
        lines.append(
            f"- **{row['kind']}** score {row['score']} | {names} | {years} | `{row['rel_path']}`{err}"
        )
        for snip in row["snippets"][:2]:
            lines.append(f"  - …{snip}…")

    if encrypted:
        lines += ["", "## Could not read (encrypted or binary) — filename still used", ""]
        for row in encrypted[:40]:
            lines.append(f"- `{row['rel_path']}` — {row['extraction_error']}")

    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Search local documents for who traveled for PD this summer."
    )
    parser.add_argument(
        "--intake",
        help="Folder to search. Default: burling/corpus if it exists, else burling/intake.",
    )
    parser.add_argument(
        "--preset",
        default="summer-pd-travel",
        choices=["summer-pd-travel"],
        help="Named query. Today this is the only preset; keep CLI stable for more later.",
    )
    parser.add_argument(
        "--year",
        default=None,
        help="Summer year to treat as 'this summer'. Default: current calendar year.",
    )
    parser.add_argument(
        "--config",
        help="Optional config.yaml override (only used for the output folder).",
    )
    args = parser.parse_args(argv)

    cfg = load_config(Path(args.config) if args.config else None)
    package = Path(__file__).resolve().parent
    default_corpus = package / "corpus"
    default_intake = package / "intake"
    if args.intake:
        root = Path(args.intake).resolve()
    elif default_corpus.is_dir() and any(default_corpus.iterdir()):
        root = default_corpus
    else:
        root = default_intake

    if not root.is_dir():
        print(f"search folder not found: {root}", file=sys.stderr)
        return 2

    this_year = args.year or str(date.today().year)
    print(f"Searching {root} for summer PD travel ({this_year})...")
    rows = search_tree(root)
    out = output_dir(cfg)
    report_path = out / "SUMMER-PD-TRAVEL.md"
    json_path = out / "SUMMER-PD-TRAVEL.json"
    payload = {
        "question": "who traveled for professional development this summer",
        "year": this_year,
        "intake": str(root),
        "preset": args.preset,
        "hits": rows,
        "people": list(people_index(rows, this_year).values()),
    }
    atomic_write(report_path, render_report(root, rows, this_year))
    atomic_write_json(json_path, payload)

    people = people_index(rows, this_year)
    summer = [p["name"] for p in people.values() if this_year in p["years"]]
    print(f"hits: {len(rows)}")
    print(f"named travelers with {this_year} on the packet: {', '.join(summer) or '(none yet)'}")
    print(f"report: {report_path}")
    print(f"json:   {json_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
