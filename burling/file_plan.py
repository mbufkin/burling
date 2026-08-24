"""Constrained clerk: one stitch names the drawers, then one home per file.

The military file plan is a closed list. The 30B is good at "read this
memo, pick the closest numbered folder." It is bad at inventing a tree
in a loop. This module is that clerk SOP:

1. Stitch once with a ban on channel / year heads.
2. File each document into exactly one approved home, or ``unmapped``.

See docs/military-document-sorting.md. Everyday organize is ``--walk``,
not this path and not ``--ralp``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from burling.extract import extract_record
from burling.isolate import OPERATOR_STOP, note_file_failure
from burling.io_util import atomic_write_json
from burling.ollama_client import chat
from burling.paths import intake_dir as config_intake, output_dir
from burling.progress import Progress, console_safe
from burling.trace import utc_now

# Same budget as the locked fresh-window spec. Usenet posts are tiny;
# the cap is for the next dump, not this gold set.
CLERK_DOC_CAP = 80_000
UNMAPPED_ID = "unmapped"

# Channel / era tokens. A pile named by *how it arrived* or *when* is
# not a browse head — Navy files year as a cutoff inside the subject.
_CHANNEL_RE = re.compile(
    r"\b(usenet|e-?mail|newsgroup|nntp|internet[- ]culture)\b",
    re.I,
)
_YEAR_RE = re.compile(r"\b(19\d\d|20\d\d|1980s|1990s|2000s)\b")
_YEAR_ONLY = re.compile(r"^(19\d\d|20\d\d|1980s|1990s|2000s)$")

CLERK_SYSTEM = """You are a records clerk. The FILE PLAN is already approved.
Read ONE document. Assign it to the single closest home.

Output ONLY a JSON object:
{"home": "<id>", "reason": "one short sentence"}

Rules:
- home MUST be an id from the FILE PLAN, or "unmapped".
- Do not invent a folder. Do not pick two homes.
- Year, email, usenet, and filename are not subjects. File by what the
  document is about.
- If nothing in the plan fits, home is "unmapped". That is correct, not a failure.
"""


def is_banned_head(region_id: str, label: str = "") -> bool:
    """True when the folder is a channel or year, not a subject.

    Best practice: enforce this in code. The stitch prompt asks the same
    thing; Nemotron still emits ``usenet-1993`` unless we strip it.
    """
    blob = f"{region_id} {label}".replace("_", " ").replace("-", " ").strip()
    if _CHANNEL_RE.search(blob):
        return True
    tokens = [t for t in re.split(r"\s+", blob.lower()) if t]
    topical = [t for t in tokens if not _YEAR_ONLY.match(t)]
    return not topical


def demote_banned_heads(regions: list) -> list[dict]:
    """Promote topical children; drop channel/year roots.

    A banned parent with a Hockey child becomes a top-level Hockey.
    Banned leaves disappear — those files go through the clerk to
    ``unmapped`` or a real sibling.
    """
    kept: list[dict] = []
    for node in regions or []:
        if not isinstance(node, dict):
            continue
        kids = [c for c in (node.get("children") or []) if isinstance(c, dict)]
        rid = str(node.get("id") or "")
        label = str(node.get("label") or "")
        if is_banned_head(rid, label):
            kept.extend(demote_banned_heads(kids))
            continue
        nxt = dict(node)
        nxt["children"] = demote_banned_heads(kids)
        kept.append(nxt)
    return kept


def ensure_unmapped(regions: list[dict]) -> None:
    """Every file plan has an honest leftover bin. Do not invent a 14th type."""
    if any(str(n.get("id") or "") == UNMAPPED_ID for n in regions if isinstance(n, dict)):
        return
    regions.append(
        {
            "id": UNMAPPED_ID,
            "label": "Unmapped",
            "description": "No approved head fits. Human decides — not a new type.",
            "tags": [],
            "children": [],
        }
    )


def fileable_homes(regions: list) -> list[dict]:
    """Closed list the clerk may emit. Every node id + unmapped."""
    homes: list[dict] = []

    def walk(nodes: list, parent: str | None) -> None:
        for node in nodes or []:
            if not isinstance(node, dict):
                continue
            rid = str(node.get("id") or "").strip()
            if not rid:
                continue
            homes.append(
                {
                    "id": rid,
                    "label": str(node.get("label") or rid),
                    "description": str(node.get("description") or ""),
                    "parent_id": parent,
                }
            )
            walk(node.get("children") or [], rid)

    walk(regions, None)
    if not any(h["id"] == UNMAPPED_ID for h in homes):
        homes.append(
            {
                "id": UNMAPPED_ID,
                "label": "Unmapped",
                "description": "No approved head fits.",
                "parent_id": None,
            }
        )
    return homes


def coerce_home(raw: object, allowed: set[str]) -> str:
    """Accept only an approved id. Unknown / empty → unmapped.

    Best practice: never let a hallucinated folder land in regions.json.
    Retry happens at the call site; this function is the last gate.
    """
    if raw is None:
        return UNMAPPED_ID
    home = str(raw).strip().lower().replace(" ", "-")
    if home in allowed:
        return home
    # Model sometimes returns the human label. Match kebab of the label.
    return UNMAPPED_ID


def plan_block(homes: list[dict]) -> str:
    lines = ["FILE PLAN (pick exactly one id):"]
    for home in homes:
        parent = f" (under {home['parent_id']})" if home.get("parent_id") else ""
        desc = (home.get("description") or "").strip()
        extra = f" — {desc}" if desc else ""
        lines.append(f"- {home['id']}: {home['label']}{parent}{extra}")
    return "\n".join(lines)


def _state_path(cfg: dict) -> Path:
    return output_dir(cfg) / "clerk-state.json"


def load_clerk_state(cfg: dict) -> dict:
    path = _state_path(cfg)
    if not path.is_file():
        return {"homes": {}, "errors": {}, "updated_at": None}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"homes": {}, "errors": {}, "updated_at": None}
    data.setdefault("homes", {})
    data.setdefault("errors", {})
    return data


def save_clerk_state(cfg: dict, state: dict) -> None:
    state["updated_at"] = utc_now()
    atomic_write_json(_state_path(cfg), state)


def _resolve_intake_file(intake: Path, rel_path: str) -> Path | None:
    """Gold inbox is flat hashes; some records still carry a folder prefix."""
    rel = Path(rel_path)
    direct = intake / rel
    if direct.is_file():
        return direct
    by_name = intake / rel.name
    if by_name.is_file():
        return by_name
    return None


def clerk_text(cfg: dict, rel_path: str, record: dict) -> str:
    """Full extracted text when we can read the file; else the tag summary.

    The bet is extracted text. A missing inbox file must not kill the run —
    the summary is a weaker clerk, noted on the assignment.
    """
    intake = config_intake(cfg)
    path = _resolve_intake_file(intake, rel_path)
    if path is not None:
        # extract_record only needs a root for rel_path; we only want the text.
        extracted = extract_record(path, path.parent)
        text = (extracted.get("text") or "").strip()
        if extracted.get("extraction_ok") and text:
            return text[:CLERK_DOC_CAP]
    summary = str(record.get("summary") or "").strip()
    tags = ", ".join(str(t) for t in (record.get("tags") or [])[:20])
    return f"(extract missing — file from tags only)\nTAGS: {tags}\nSUMMARY: {summary}"


def file_one(cfg: dict, *, rel_path: str, text: str, homes: list[dict]) -> dict:
    """One fresh-window clerk call. Returns ``{home, reason}``."""
    allowed = {h["id"] for h in homes}
    user = (
        f"{plan_block(homes)}\n\n"
        f"FILE: {rel_path}\n\n"
        f"DOCUMENT TEXT:\n{text}"
    )
    raw = chat(
        cfg,
        [
            {"role": "system", "content": CLERK_SYSTEM},
            {"role": "user", "content": user},
        ],
        step=f"clerk:{rel_path}",
    )
    if not isinstance(raw, dict):
        raw = {}
    home = coerce_home(raw.get("home"), allowed)
    # Second chance: match the model's home against labels (Hockey → sports-hockey).
    if home == UNMAPPED_ID and raw.get("home"):
        wanted = str(raw.get("home")).strip().lower()
        for h in homes:
            if h["id"] == UNMAPPED_ID:
                continue
            if wanted in {h["id"], h["label"].lower(), h["label"].lower().replace(" ", "-")}:
                home = h["id"]
                break
    reason = str(raw.get("reason") or "").strip()
    return {"home": home, "reason": reason}


def apply_clerk_homes(payload: dict, homes_by_path: dict[str, str]) -> None:
    """Overwrite each assignment to a single primary home."""
    idx_ids = {h["id"] for h in fileable_homes(payload.get("regions") or [])}
    by_name: dict[str, dict] = {}
    for row in payload.get("assignments") or []:
        rel = str(row.get("rel_path") or "")
        by_name[rel] = row
        by_name[Path(rel).name] = row
    for rel, home in homes_by_path.items():
        row = by_name.get(rel) or by_name.get(Path(rel).name)
        if row is None:
            continue
        hid = home if home in idx_ids else UNMAPPED_ID
        row["region_ids"] = [hid]
        row["top_level_regions"] = [hid]
        row["clerk_home"] = hid


def run_clerk(cfg: dict, *, limit: int | None = None) -> dict:
    """File every tagged document into one approved home. Resume-safe."""
    from burling.ralp import persist_payload
    from burling.stitch_tags import load_tag_records

    out = output_dir(cfg)
    regions_path = out / "regions.json"
    if not regions_path.is_file():
        raise RuntimeError(f"No file plan at {regions_path}. Run stitch method=clerk first.")
    payload = json.loads(regions_path.read_text(encoding="utf-8"))
    ensure_unmapped(payload.setdefault("regions", []))
    homes = fileable_homes(payload["regions"])
    allowed = {h["id"] for h in homes}

    tags_path = Path(cfg.get("paths", {}).get("tags_json") or (out / "tags.json"))
    records = load_tag_records(cfg, tags_path if tags_path.is_file() else None)
    if not records:
        raise RuntimeError(f"No tags at {tags_path}")

    state = load_clerk_state(cfg)
    pending = [
        r
        for r in records
        if str(r.get("rel_path") or "") not in state["homes"]
        and Path(str(r.get("rel_path") or "")).name not in state["homes"]
    ]
    if limit is not None:
        pending = pending[: max(0, limit)]

    already = len(state["homes"])
    print(
        f"CLERK: {already} already filed, {len(pending)} to file, "
        f"{len(homes)} approved homes",
        flush=True,
    )
    progress = Progress(cfg, "clerk", len(pending))

    try:
        for i, rec in enumerate(pending, start=1):
            rel = str(rec.get("rel_path") or "")
            progress.tick(i, rel)
            try:
                text = clerk_text(cfg, rel, rec)
                result = file_one(cfg, rel_path=rel, text=text, homes=homes)
                home = result["home"] if result["home"] in allowed else UNMAPPED_ID
                state["homes"][rel] = home
                print(console_safe(f"  clerk {rel} → {home}"), flush=True)
            except OPERATOR_STOP:
                raise
            except Exception as exc:
                note_file_failure(
                    cfg, None, None, stage="clerk", exc=exc, rel_path=rel
                )
                state["homes"][rel] = UNMAPPED_ID
                state["errors"][rel] = f"{type(exc).__name__}: {exc}"
            save_clerk_state(cfg, state)
            # Persist often enough to survive a kill; HTML rewrite is the slow bit.
            if i % 10 == 0:
                apply_clerk_homes(payload, state["homes"])
                _stamp_meta(payload, homes, state)
                persist_payload(cfg, payload)
    finally:
        apply_clerk_homes(payload, state["homes"])
        _stamp_meta(payload, homes, state)
        persist_payload(cfg, payload)
        save_clerk_state(cfg, state)
        progress.finish(len(pending))

    filed = len(state["homes"])
    unmapped = sum(1 for h in state["homes"].values() if h == UNMAPPED_ID)
    print(f"CLERK done: {filed} files, {unmapped} unmapped → {out / 'regions.json'}", flush=True)
    return {
        "filed": filed,
        "unmapped": unmapped,
        "homes": len(homes),
        "errors": len(state["errors"]),
    }


def _stamp_meta(payload: dict, homes: list[dict], state: dict) -> None:
    meta = dict(payload.get("meta") or {})
    meta["method"] = "clerk-file-plan"
    meta["clerk_filed"] = len(state["homes"])
    meta["clerk_unmapped"] = sum(1 for h in state["homes"].values() if h == UNMAPPED_ID)
    meta["clerk_homes"] = len(homes)
    payload["meta"] = meta


def run_file_plan(
    cfg: dict,
    *,
    resume: bool = False,
    limit: int | None = None,
) -> dict:
    """Stitch a banned-head file plan (unless resume), then clerk every file."""
    from burling.stitch_tags import load_tag_records, stitch_from_records

    out = output_dir(cfg)
    out.mkdir(parents=True, exist_ok=True)
    tags_path = Path(cfg.get("paths", {}).get("tags_json") or (out / "tags.json"))
    dest_tags = out / "tags.json"
    # Copy cached tags into the clerk folder so the browse map can title files.
    if tags_path.is_file() and dest_tags.resolve() != tags_path.resolve():
        dest_tags.write_text(tags_path.read_text(encoding="utf-8"), encoding="utf-8")
    regions_path = out / "regions.json"
    have_plan = regions_path.is_file()
    if resume and have_plan:
        print(f"CLERK: resume — keeping file plan at {regions_path}", flush=True)
    else:
        records = load_tag_records(cfg, tags_path if tags_path.is_file() else None)
        if not records:
            raise RuntimeError(f"No Pass A tags at {tags_path}")
        print(f"CLERK: stitching file plan from {len(records)} tagged docs", flush=True)
        stitch_from_records(cfg, records, method="clerk")
    return run_clerk(cfg, limit=limit)


# Approved child drawers per workplace main (the series beneath each series).
# Mains are locked; children are menu-locked too when this map applies.
# An org overrides per installation via config `walk.children`.
WORKPLACE_CHILDREN: dict[str, tuple[str, ...]] = {
    "personnel": ("policies", "cases", "benefits", "rosters"),
    "operations": ("schedules", "incidents", "planning", "logs"),
    "administration": ("policies", "minutes"),
    "finance": ("budget", "invoices", "payroll", "reimbursements", "vendors"),
    "legal": ("templates", "holds", "trademarks", "leases"),
    "technology": ("design", "architecture", "runbooks", "retros"),
    # customers is deliberately absent: its drawers are account/matter
    # names, which no plan can pre-declare. Free invention applies there,
    # as it does for any main without an entry.
    "facilities": ("logs", "policies"),
    "security": ("incidents", "policies", "tickets", "credentials"),
    "communications": ("press", "internal", "crisis"),
    "training": ("plans", "certifications", "compliance", "mentoring"),
    "health": ("assessments", "clinics", "inventory", "events"),
    "personal": ("family", "hobbies"),
}


def _kebab(raw: object) -> str:
    text = str(raw or "").strip().lower().replace("_", "-")
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:48]


def approved_children(cfg: dict | None, main: str) -> set[str] | None:
    """Menu of legal child drawers for main, or None when free invention applies.

    Config `walk.children` (main -> list) overrides the built-in map;
    `walk.children: false` disables menus entirely.
    """
    if cfg is None:
        return set(WORKPLACE_CHILDREN.get(main, ())) or None
    override = (cfg.get("walk") or {}).get("children")
    if override is False:
        return None
    if isinstance(override, dict):
        raw = override.get(main)
        return {_kebab(x) for x in raw} if raw else None
    own = WORKPLACE_CHILDREN.get(main, ())
    return set(own) or None
