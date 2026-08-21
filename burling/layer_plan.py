"""Layered file plan: 3-layer tags on the file, then one roll-up.

Folders are prefixes of those paths, not a stitch-invented tree. A stranger
walks at most three folders, and only that deep when the parent is fat and
mixed. The fourth layer stays a tag (``facet``). Spec:
``docs/file-plan-layers.md``.

Previous test (``--layers``). Everyday organize is ``--walk``.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from burling.extract import extract_record
from burling.file_plan import (
    UNMAPPED_ID,
    ensure_unmapped,
    is_banned_head,
)
from burling.isolate import OPERATOR_STOP, note_file_failure
from burling.io_util import atomic_write_json
from burling.ollama_client import chat
from burling.paths import intake_dir as config_intake, output_dir
from burling.progress import Progress, console_safe
from burling.trace import utc_now

# Same budget as the locked fresh-window spec.
LAYER_DOC_CAP = 80_000
FAT_MIN = 8
MAX_BROWSE_DEPTH = 3
# Open-discovery only. A closed workplace plan already has ≤13 roots — do not merge them.
MAX_ROOTS_BEFORE_ROLLUP = 16

# Parents that could hold anything. Navy would not mint a 14th series named Misc.
_VAGUE_PARENT = re.compile(
    r"^(discussion|misc|miscellaneous|other|general|files?|documents?|"
    r"topics?|items?|archive|stuff|content|records?)$",
    re.I,
)

# Workplace file plan (employee-exit). Navy analog: 13 prescribed series, then nest.
# personal is not a mission series — it is the delete bin after someone leaves.
WORKPLACE_MAINS: tuple[str, ...] = (
    "personnel",
    "operations",
    "administration",
    "finance",
    "legal",
    "technology",
    "customers",
    "facilities",
    "security",
    "communications",
    "training",
    "health",
    "personal",
)

# Closest approved series. Unknown mains do not become a 14th type.
MAIN_ALIASES: dict[str, str] = {
    "hr": "personnel",
    "people": "personnel",
    "ops": "operations",
    "admin": "administration",
    "money": "finance",
    "accounting": "finance",
    "compliance": "legal",
    "software": "technology",
    "computing": "technology",
    "it": "technology",
    "hardware": "facilities",
    "equipment": "facilities",
    "electronics": "facilities",
    "sales": "customers",
    "support": "customers",
    "medical": "health",
    "medicine": "health",
    "safety": "health",
    "sports": "personal",
    "recreation": "personal",
    "hobby": "personal",
    "religion": "personal",
    "faith": "personal",
    "family": "personal",
}

LAYER_SYSTEM = """You are a records clerk. One employee has left. You assign ONE
document to a 3-layer path on the workplace file plan. Only approved mains.

Output ONLY a valid JSON object. Use "reasoning" to think in three short steps
before you pick the layers.

{
  "reasoning": "1. The work function is X. 2. The category inside that is Y. 3. The specific thing is Z.",
  "main": "kebab-id",
  "sub": "kebab-id-or-empty",
  "detail": "kebab-id-or-empty",
  "summary": "One clear, descriptive sentence."
}

APPROVED MAINS (pick exactly one):
- personnel: employment of people (hiring, reviews, 1:1s, org)
- operations: doing the work (projects, deliverables, plans)
- administration: running the office (policies, process, governance)
- finance: money (invoices, expenses, budgets, purchasing)
- legal: obligations (contracts, compliance, IP, disputes)
- technology: systems and software (code, IT, tools, networks)
- customers: accounts (sales, support, proposals)
- facilities: physical place and gear (office, equipment, supplies)
- security: access and incidents
- communications: official comms as a function (press, government relations). Not "this is an email."
- training: instruction (onboarding, courses)
- health: workplace medical and safety
- personal: not work (family, hobbies, sports, religion, photos). Isolate so it can be deleted.
- unmapped: no substance (unsubscribe, test post, empty, "me too")

ONTOLOGY:
1. main is one approved id. Do not invent a 14th series.
2. sub is a category wholly inside that main (technology/software, facilities/electronics).
3. detail is the exact tool, project, person, or file. Empty if the text has no specific.
4. sub must sit inside main. detail must sit inside sub.

GUARDRAILS:
- Hardware, equipment, and physical electronics are facilities — never a main.
- Software, code, and digital protocols are technology.
- Year, email address, newsgroup, and filename are never a layer.
- If the text has a subject but it is not work, main is personal, not unmapped.
"""

ROLLUP_SYSTEM = """You are proposing parent folders over sibling mains.
Cleaning + cooking → housekeeping. Those two labels are mains, not folders
nested under them.

Output ONLY a JSON object:
{
  "parents": [
    {"id": "kebab-id", "label": "Human label", "children": ["main-id", "main-id"]}
  ]
}

Rules:
- Children must be copied exactly from the MAIN list in the user message.
- Do not add a narrower type (a sub) as a child. Subs already live under a main.
- Only group mains that a stranger would open as one drawer.
- A parent needs two or more children from that list.
- Leave a main off the list to keep it as its own root.
- Parent ids are subjects (housekeeping, computing). Not year, usenet, email, discussion, misc, files.
"""


def kebab(raw: object) -> str:
    """Stable folder id. Empty string means 'this layer is unused'."""
    text = str(raw or "").strip().lower().replace("_", "-")
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text[:48]


def human_label(slug: str) -> str:
    """Best practice: show the stranger a title, not a kebab id."""
    if not slug or slug == UNMAPPED_ID:
        return "Unmapped"
    return slug.replace("-", " ").title()


def node_id(segments: list[str]) -> str:
    """Path-unique id so two Kitchens under different parents do not collide."""
    parts = [kebab(s) for s in segments if kebab(s)]
    return "--".join(parts) if parts else UNMAPPED_ID


def coerce_main(raw: object) -> str:
    """Only approved workplace series. Unknown → unmapped, not a 14th type.

    Best practice: the model proposes; code is the records office. Aliases
    are closest-SSIC (hardware → facilities). personal stays personal so
    a human can delete it after an employee leaves.
    """
    main = kebab(raw)
    if not main or main == UNMAPPED_ID or is_banned_head(main, main):
        return ""
    if main in WORKPLACE_MAINS:
        return main
    mapped = MAIN_ALIASES.get(main)
    if mapped in WORKPLACE_MAINS:
        return mapped
    return ""


def normalize_layers(obj: dict) -> dict:
    """Coerce a model blob onto the workplace file plan."""
    main = coerce_main(obj.get("main"))
    sub = kebab(obj.get("sub"))
    detail = kebab(obj.get("detail"))
    if not main:
        main, sub, detail = "", "", ""
    if sub and is_banned_head(sub, sub):
        sub, detail = "", ""
    if detail and is_banned_head(detail, detail):
        detail = ""
    # Consecutive duplicates are one layer (technology/technology/git → technology/git).
    layers: list[str] = []
    for part in (main, sub, detail):
        if part and (not layers or part != layers[-1]):
            layers.append(part)
    main = layers[0] if layers else ""
    sub = layers[1] if len(layers) > 1 else ""
    detail = layers[2] if len(layers) > 2 else ""
    summary = str(obj.get("summary") or "").strip()[:500]
    reasoning = str(obj.get("reasoning") or "").strip()[:500]
    return {
        "main": main,
        "sub": sub,
        "detail": detail,
        "summary": summary,
        "reasoning": reasoning,
        "status": "done",
        "at": utc_now(),
    }


def folder_segments(
    main: str,
    sub: str,
    detail: str,
    parent_of: dict[str, str],
) -> tuple[list[str], str | None]:
    """Prefix the roll-up parent, cap at three folders, leftover is facet.

    Housekeeping (parent) / Cleaning (main) / Kitchen (sub) is the browse
    path. Detail becomes the fourth layer and must not be a folder.
    """
    main = kebab(main)
    if not main:
        return [UNMAPPED_ID], None
    parent = kebab(parent_of.get(main) or "")
    layers: list[str] = []
    if parent and parent != main and not is_banned_head(parent, parent):
        layers.append(parent)
    for part in (main, kebab(sub), kebab(detail)):
        if part and (not layers or part != layers[-1]):
            layers.append(part)
    folders = layers[:MAX_BROWSE_DEPTH]
    facet = layers[MAX_BROWSE_DEPTH] if len(layers) > MAX_BROWSE_DEPTH else None
    return folders, facet


def prefix_counts(paths: list[list[str]]) -> dict[tuple[str, ...], int]:
    """How many files sit at or under each prefix."""
    counts: dict[tuple[str, ...], int] = defaultdict(int)
    for segs in paths:
        for i in range(1, len(segs) + 1):
            counts[tuple(segs[:i])] += 1
    return counts


def collapse_home(
    segments: list[str],
    counts: dict[tuple[str, ...], int],
    *,
    fat_min: int = FAT_MIN,
) -> list[str]:
    """Open a tagged child folder only when it holds enough files.

    Roots always exist (a 3-file Medicine pile still needs a drawer).
    Mixed is the roll-up gate (two+ mains to invent a parent), not this
    cut. Navy subdivides inside the RN when there is enough paper — here
    that is ``fat_min`` (~8). Thin leftovers sit on the parent.
    """
    if not segments or segments[0] == UNMAPPED_ID:
        return [UNMAPPED_ID]
    kept: list[str] = [segments[0]]
    for seg in segments[1:]:
        child = tuple(kept + [seg])
        if len(child) > MAX_BROWSE_DEPTH:
            break
        if counts.get(child, 0) >= fat_min:
            kept.append(seg)
        else:
            break
    return kept


def apply_rollup(
    mains: list[str],
    raw: object,
) -> dict[str, str]:
    """Map each main → parent id (or itself). Invalid groups are ignored.

    Best practice: the model proposes; code is the records office. A vague
    or banned parent does not land in the file plan.
    """
    allowed = {kebab(m) for m in mains if kebab(m)}
    mapping = {m: m for m in allowed}
    if not isinstance(raw, dict):
        return mapping
    parents = raw.get("parents")
    if not isinstance(parents, list):
        return mapping
    used: set[str] = set()
    for group in parents:
        if not isinstance(group, dict):
            continue
        pid = kebab(group.get("id") or group.get("label"))
        kids = [kebab(c) for c in (group.get("children") or []) if kebab(c) in allowed]
        kids = [k for k in kids if k not in used and k != pid]
        if len(kids) < 2 or not pid:
            continue
        if is_banned_head(pid, str(group.get("label") or pid)):
            continue
        if _VAGUE_PARENT.match(pid):
            continue
        for kid in kids:
            mapping[kid] = pid
            used.add(kid)
    return mapping


def build_regions(
    records: list[dict],
    parent_of: dict[str, str],
    *,
    fat_min: int = FAT_MIN,
) -> dict:
    """Python tree from tagged paths. One home per file."""
    staged: list[dict] = []
    raw_paths: list[list[str]] = []
    for rec in records:
        segs, facet = folder_segments(
            rec.get("main") or "",
            rec.get("sub") or "",
            rec.get("detail") or "",
            parent_of,
        )
        raw_paths.append(segs)
        staged.append(
            {
                "rel_path": rec.get("rel_path") or "",
                "segments": segs,
                "facet": facet,
                "summary": rec.get("summary") or "",
                "main": rec.get("main") or "",
                "sub": rec.get("sub") or "",
                "detail": rec.get("detail") or "",
            }
        )
    counts = prefix_counts(raw_paths)
    homes: list[list[str]] = [collapse_home(s["segments"], counts, fat_min=fat_min) for s in staged]

    # Build a trie of surviving homes.
    trie: dict = {}
    for home in homes:
        node = trie
        for seg in home:
            node = node.setdefault(seg, {})

    def to_regions(node: dict, prefix: list[str]) -> list[dict]:
        out: list[dict] = []
        for seg in sorted(node):
            path = prefix + [seg]
            kids = to_regions(node[seg], path)
            out.append(
                {
                    "id": node_id(path),
                    "label": human_label(seg),
                    "description": f"A file belongs here if its subject is {human_label(seg).lower()}.",
                    "tags": [seg],
                    "children": kids,
                }
            )
        return out

    regions = [n for n in to_regions(trie, []) if n["id"] != UNMAPPED_ID]
    ensure_unmapped(regions)

    assignments = []
    for row, home in zip(staged, homes):
        hid = node_id(home)
        top = node_id(home[:1]) if home else UNMAPPED_ID
        assignments.append(
            {
                "rel_path": row["rel_path"],
                "region_ids": [hid],
                "top_level_regions": [top],
                "summary": row["summary"],
                "facet": row["facet"],
                "layer_path": "/".join(x for x in (row["main"], row["sub"], row["detail"]) if x),
            }
        )

    n_homes = [len(a["region_ids"]) for a in assignments]
    unmapped = sum(1 for a in assignments if a["region_ids"] == [UNMAPPED_ID])
    return {
        "meta": {
            "method": "layered-file-plan",
            "documents": len(assignments),
            "top_level": len([r for r in regions if r.get("id") != UNMAPPED_ID]),
            "nodes": _count_nodes(regions),
            "docs_mapped": len(assignments) - unmapped,
            "unmapped": unmapped,
            "homes_mean": round(sum(n_homes) / len(n_homes), 2) if n_homes else 0,
            "fat_min": fat_min,
            "max_browse_depth": MAX_BROWSE_DEPTH,
            "built_at": utc_now(),
        },
        "regions": regions,
        "rollup": parent_of,
        "assignments": assignments,
    }


def _count_nodes(nodes: list) -> int:
    n = 0
    for node in nodes or []:
        if not isinstance(node, dict):
            continue
        n += 1
        n += _count_nodes(node.get("children") or [])
    return n


def _layer_tags_path(cfg: dict) -> Path:
    return output_dir(cfg) / "layer-tags.json"


def load_layer_tags(cfg: dict) -> dict[str, dict]:
    path = _layer_tags_path(cfg)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    out: dict[str, dict] = {}
    for rec in data.get("documents") or []:
        rel = str(rec.get("rel_path") or "")
        if rel:
            out[rel] = rec
    return out


def save_layer_tags(cfg: dict, by_path: dict[str, dict]) -> None:
    docs = [by_path[k] for k in sorted(by_path)]
    atomic_write_json(
        _layer_tags_path(cfg),
        {"count": len(docs), "documents": docs, "method": "layered-file-plan"},
    )


def _resolve_intake_file(intake: Path, rel_path: str) -> Path | None:
    rel = Path(rel_path)
    direct = intake / rel
    if direct.is_file():
        return direct
    by_name = intake / rel.name
    if by_name.is_file():
        return by_name
    return None


def tag_one_layers(cfg: dict, *, rel_path: str, text: str) -> dict:
    """One fresh-window 3-layer tag. Returns a normalized record."""
    user = f"FILE: {rel_path}\n\nDOCUMENT TEXT:\n{text}"
    raw = chat(
        cfg,
        [
            {"role": "system", "content": LAYER_SYSTEM},
            {"role": "user", "content": user},
        ],
        step=f"layers:{rel_path}",
    )
    if not isinstance(raw, dict):
        raw = {}
    rec = normalize_layers(raw)
    rec["rel_path"] = rel_path
    return rec


def _doc_text(cfg: dict, rel_path: str) -> str:
    """Extracted body, or a filename stub when the PDF is locked.

    Best practice: empty extract → no model call (unmapped). A passworded
    Drive copy still has a usable name — send that, clearly marked, so the
    clerk can pick finance/travel without inventing a body.
    """
    intake = config_intake(cfg)
    path = _resolve_intake_file(intake, rel_path)
    if path is None:
        return ""
    extracted = extract_record(path, path.parent)
    text = (extracted.get("text") or "").strip()
    if extracted.get("extraction_ok") and text:
        return text[:LAYER_DOC_CAP]
    err = str(extracted.get("extraction_error") or "")
    if "encrypted PDF" in err:
        return (
            f"EXTRACT FAILED ({err}). FILE NAME ONLY — do not invent body text:\n"
            f"{path.name}"
        )[:LAYER_DOC_CAP]
    return ""


def run_layer_tags(
    cfg: dict,
    records: list[dict],
    *,
    limit: int | None = None,
    force: bool = False,
) -> list[dict]:
    """Tag every listed file with a 3-layer path. Resume-safe."""
    by_path = {} if force else load_layer_tags(cfg)
    pending = [
        r
        for r in records
        if (r.get("rel_path") and (force or (r.get("rel_path") not in by_path) or by_path[r["rel_path"]].get("status") != "done"))
    ]
    if limit is not None:
        pending = pending[: max(0, limit)]
    print(
        f"LAYERS: {len(by_path)} already tagged, {len(pending)} to tag",
        flush=True,
    )
    progress = Progress(cfg, "layers", len(pending))
    try:
        for i, rec in enumerate(pending, start=1):
            rel = str(rec.get("rel_path") or "")
            progress.tick(i, rel)
            try:
                text = _doc_text(cfg, rel)
                if not text:
                    tagged = normalize_layers({"main": UNMAPPED_ID, "summary": "extract missing"})
                    tagged["rel_path"] = rel
                    tagged["status"] = "done"
                else:
                    if text.startswith("EXTRACT FAILED"):
                        print(console_safe(f"  layer {rel} (filename only, locked PDF)"), flush=True)
                    tagged = tag_one_layers(cfg, rel_path=rel, text=text)
                by_path[rel] = tagged
                print(
                    console_safe(
                        f"  layer {rel} → {tagged.get('main')}/{tagged.get('sub')}/{tagged.get('detail')}"
                    ),
                    flush=True,
                )
            except OPERATOR_STOP:
                raise
            except Exception as exc:
                note_file_failure(cfg, None, None, stage="layers", exc=exc, rel_path=rel)
                tagged = normalize_layers({"main": UNMAPPED_ID, "summary": f"{type(exc).__name__}: {exc}"})
                tagged["rel_path"] = rel
                by_path[rel] = tagged
            save_layer_tags(cfg, by_path)
    finally:
        progress.finish(len(pending))
        save_layer_tags(cfg, by_path)
    # Stable order matching the source file list.
    ordered = []
    seen: set[str] = set()
    for rec in records:
        rel = str(rec.get("rel_path") or "")
        if rel in by_path and rel not in seen:
            ordered.append(by_path[rel])
            seen.add(rel)
    return ordered


def _main_inventory(records: list[dict]) -> list[tuple[str, int]]:
    """Unique mains and counts. Subs stay off this list — they are not roll-up children."""
    counts: Counter[str] = Counter()
    for rec in records:
        main = kebab(rec.get("main"))
        if not main:
            continue
        counts[main] += 1
    return list(counts.most_common())


def rollup_user_prompt(records: list[dict]) -> tuple[list[str], str]:
    """Ask only about mains. Showing subs made the 30B group hockey as a main."""
    inventory = _main_inventory(records)
    mains = [m for m, _n in inventory]
    lines = [
        f"CORPUS: {len(records)} documents, {len(mains)} unique mains.",
        "Each line is one MAIN id. Group two or more of these ids under a new",
        "parent only when they are the same kind of thing.",
        "Copy child ids exactly from this list. Do not add any other id.",
        "",
        "MAINS (count):",
    ]
    for main, n in inventory:
        lines.append(f"- {main}: {n}")
    return mains, "\n".join(lines)


def run_rollup(cfg: dict, records: list[dict], *, resume: bool = False) -> dict[str, str]:
    """One call to combine sibling mains. Skipped when already few roots."""
    mains, user = rollup_user_prompt(records)
    identity = {m: m for m in mains}
    out = output_dir(cfg)
    rollup_path = out / "rollup.json"
    if resume and rollup_path.is_file():
        try:
            saved = json.loads(rollup_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            saved = {}
        mapping = saved.get("mapping")
        if isinstance(mapping, dict) and mapping:
            print(f"LAYERS: resume — keeping roll-up at {rollup_path}", flush=True)
            return {kebab(k): kebab(v) or kebab(k) for k, v in mapping.items()}
    approved = set(WORKPLACE_MAINS)
    if mains and all(m in approved for m in mains):
        print("LAYERS: all mains are on the workplace file plan — no roll-up", flush=True)
        atomic_write_json(
            out / "rollup.json",
            {"parents": [], "mapping": identity, "skipped": True, "reason": "closed-file-plan"},
        )
        return identity
    if len(mains) <= MAX_ROOTS_BEFORE_ROLLUP:
        print(
            f"LAYERS: {len(mains)} mains ≤ {MAX_ROOTS_BEFORE_ROLLUP} — no roll-up",
            flush=True,
        )
        atomic_write_json(out / "rollup.json", {"parents": [], "mapping": identity, "skipped": True})
        return identity

    raw = chat(
        cfg,
        [
            {"role": "system", "content": ROLLUP_SYSTEM},
            {"role": "user", "content": user},
        ],
        step="layers:rollup",
    )
    mapping = apply_rollup(mains, raw if isinstance(raw, dict) else {})
    roots = sorted({mapping[m] for m in mains})
    print(f"LAYERS: roll-up {len(mains)} mains → {len(roots)} roots", flush=True)
    atomic_write_json(
        out / "rollup.json",
        {"raw": raw if isinstance(raw, dict) else {}, "mapping": mapping, "skipped": False},
    )
    return mapping


def run_layer_plan(
    cfg: dict,
    *,
    resume: bool = False,
    limit: int | None = None,
    force: bool = False,
) -> dict:
    """Tag 3 layers → roll-up → Python tree. Writes a new output folder."""
    from burling.ralp import persist_payload
    from burling.stitch_tags import load_tag_records

    out = output_dir(cfg)
    out.mkdir(parents=True, exist_ok=True)
    tags_path = Path(cfg.get("paths", {}).get("tags_json") or (out / "tags.json"))
    source = load_tag_records(cfg, tags_path if tags_path.is_file() else None)
    if not source:
        raise RuntimeError(f"No document list at {tags_path} (need tags.json for the file list).")

    records = run_layer_tags(cfg, source, limit=limit, force=force)
    parent_of = run_rollup(cfg, records, resume=resume)
    payload = build_regions(records, parent_of)
    persist_payload(cfg, payload)
    # Mirror a slim tags.json so the HTML map can title files from summaries.
    atomic_write_json(
        out / "tags.json",
        {
            "count": len(records),
            "documents": [
                {
                    "rel_path": r.get("rel_path"),
                    "tags": [t for t in (r.get("main"), r.get("sub"), r.get("detail")) if t],
                    "summary": r.get("summary") or "",
                }
                for r in records
            ],
        },
    )
    meta = payload["meta"]
    print(
        f"LAYERS done: {meta['documents']} files, {meta['top_level']} roots, "
        f"{meta['nodes']} nodes, {meta['unmapped']} unmapped, "
        f"homes/file {meta['homes_mean']} → {out / 'regions.json'}",
        flush=True,
    )
    return meta
