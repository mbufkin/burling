"""Pass C — placement audit after stitch. Group-at-a-time, not random.

Best practice (docs/audit-pass.md):

  L1  Deterministic graph checks. No model.
  L2  Nemotron verifies *existing* homes, one browse group at a time.
  L3  Human reads the flag queue (AUDIT.md), not 670 confirms.

Work order is the tree: parent topic, then its children, then leftovers.
Files inside a group are sorted by path. A file with two homes is audited
once, in its deepest real region, with ``also under`` listed.

If a group is too fat for one prompt, we split it into documented chunks
and keep going. We do not dump the whole corpus into one chat — that is
what broke the 3515-tag stitch.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from burling.io_util import atomic_write, atomic_write_json, load_json
from burling.isolate import OPERATOR_STOP
from burling.ollama_client import chat
from burling.paths import output_dir
from burling.progress import Progress
from burling.stitch_tags import _region_index, _walk_regions
from burling.trace import utc_now

# One model call holds this many files. Larger than this, JSON and
# attention both degrade — we chunk and write it down so we can fix.
AUDIT_GROUP_MAX = 12
# A child with this many files is a fat branch (TaxoGen / TnT recurse).
FAT_BRANCH_DOCS = 40
# Singleton folder: one file, wasted ring (NN/g).
SINGULARITY_DOCS = 1
UNASSIGNED_ID = "__unassigned__"
NEEDS_REVIEW_ID = "needs-review"

VERDICTS = (
    "confirm",
    "wrong-parent",
    "missing-parent",
    "leftover-should-place",
    "cannot-tell",
)

AUDIT_SYSTEM = """You are auditing an existing browse tree for an arbitrary document dump.
You receive ONE group (a topic or subtopic) and the files already placed there.
Check whether those files belong in this group. Do not rebuild the taxonomy.
Do not assume this is a job handover or successor packet.
Do not invent programs that are not in the file list.

Output ONLY a single JSON object:
{
  "group_notes": "2-4 sentences: is this group coherent? too mixed? too fat?",
  "files": [
    {
      "rel_path": "exact path from the list",
      "verdict": "confirm | wrong-parent | missing-parent | leftover-should-place | cannot-tell",
      "better_home": "region-id if wrong-parent or leftover-should-place, else empty",
      "reason": "one sentence, no personal names"
    }
  ]
}

Verdicts:
- confirm: this group is a correct home (other homes may still be valid).
- wrong-parent: the listed home is a mismatch; suggest better_home from the tree list.
- missing-parent: keep this home AND add better_home (polyhierarchy).
- leftover-should-place: this leftover/unassigned file has a real home.
- cannot-tell: not enough text or the file is unreadable.

Rules:
- Every listed file must appear exactly once in files[].
- better_home must be a region-id from the TREE LIST, or empty.
- Do not quote emails, phones, SSNs, or street addresses.
"""


def load_regions(cfg: dict, path: Path | None = None) -> dict:
    p = path or (output_dir(cfg) / "regions.json")
    if not p.is_file():
        raise RuntimeError(
            f"No stitch output at {p}. Run: python -m burling.run --stitch"
        )
    return json.loads(p.read_text(encoding="utf-8"))


def _sort_nodes(nodes: list[dict]) -> list[dict]:
    """Stable, readable order. Needs-review always last in its sibling set."""

    def key(n: dict) -> tuple:
        rid = str(n.get("id") or "")
        label = str(n.get("label") or rid).casefold()
        return (1 if rid == NEEDS_REVIEW_ID else 0, label, rid)

    return sorted(
        (n for n in nodes if isinstance(n, dict) and n.get("id")),
        key=key,
    )


def ordered_region_ids(regions: list[dict]) -> list[str]:
    """Depth-first: clean a parent, then each child. Not random."""
    out: list[str] = []

    def walk(nodes: list[dict]) -> None:
        for node in _sort_nodes(nodes or []):
            rid = str(node["id"])
            out.append(rid)
            walk(node.get("children") or [])

    walk(regions)
    return out


def region_depth(rid: str, region_idx: dict[str, dict]) -> int:
    depth = 0
    cur = rid
    seen: set[str] = set()
    while region_idx.get(cur, {}).get("parent_id") and cur not in seen:
        seen.add(cur)
        cur = str(region_idx[cur]["parent_id"])
        depth += 1
    return depth


def primary_region(assignment: dict, region_idx: dict[str, dict]) -> str:
    """Audit a multi-home file once: deepest real region, then leftover bins.

    Best practice: Trailer Compliance (child) is a tighter check than
    dumping the same file into every parent. ``also under`` still goes
    in the prompt so a missing second parent can be flagged.
    """
    rids = [str(r) for r in (assignment.get("region_ids") or []) if r]
    known = [r for r in rids if r in region_idx]
    real = [r for r in known if r != NEEDS_REVIEW_ID]
    if real:
        real.sort(key=lambda r: (-region_depth(r, region_idx), r))
        return real[0]
    if NEEDS_REVIEW_ID in known or NEEDS_REVIEW_ID in rids:
        return NEEDS_REVIEW_ID
    return UNASSIGNED_ID


def chunk_files(files: list[dict], *, max_n: int = AUDIT_GROUP_MAX) -> list[list[dict]]:
    """Split a fat group into even batches. Last chunk may be smaller.

    We do not raise max_n silently. The plan file records the split so
    a later Method C recurse can replace chunking with a real child.
    """
    if max_n < 1:
        raise ValueError("max_n must be >= 1")
    if not files:
        return [[]]
    if len(files) <= max_n:
        return [files]
    return [files[i : i + max_n] for i in range(0, len(files), max_n)]


def plan_groups(
    payload: dict,
    *,
    max_n: int = AUDIT_GROUP_MAX,
) -> list[dict]:
    """Build the ordered audit plan: one dict per model chunk."""
    regions = list(payload.get("regions") or [])
    assignments = list(payload.get("assignments") or [])
    region_idx = _region_index(regions)
    region_idx.setdefault(
        UNASSIGNED_ID,
        {
            "id": UNASSIGNED_ID,
            "label": "Unassigned",
            "description": "Files with no stitch region.",
            "parent_id": None,
            "tags": [],
        },
    )

    by_primary: dict[str, list[dict]] = defaultdict(list)
    for a in assignments:
        by_primary[primary_region(a, region_idx)].append(a)
    for rid in by_primary:
        by_primary[rid].sort(key=lambda a: a.get("rel_path") or "")

    order = [rid for rid in ordered_region_ids(regions) if rid in by_primary]
    if UNASSIGNED_ID in by_primary and UNASSIGNED_ID not in order:
        order.append(UNASSIGNED_ID)

    tree_ids = [rid for rid in region_idx if rid != UNASSIGNED_ID]
    chunks: list[dict] = []
    for rid in order:
        files = by_primary[rid]
        parts = chunk_files(files, max_n=max_n)
        info = region_idx.get(rid) or {"id": rid, "label": rid, "parent_id": None}
        parent_id = info.get("parent_id")
        parent_label = (
            (region_idx.get(parent_id) or {}).get("label") if parent_id else None
        )
        fat = len(files) > max_n
        for i, part in enumerate(parts):
            chunks.append(
                {
                    "chunk_id": f"{rid}#{i:02d}",
                    "region_id": rid,
                    "label": info.get("label") or rid,
                    "parent_id": parent_id,
                    "parent_label": parent_label,
                    "description": info.get("description") or "",
                    "chunk_index": i,
                    "chunk_count": len(parts),
                    "chunked": fat,
                    "group_file_count": len(files),
                    "files": part,
                    "tree_ids": tree_ids,
                }
            )
    return chunks


def graph_findings(payload: dict, *, fat_at: int = FAT_BRANCH_DOCS) -> list[dict]:
    """L1: structure only. No model, no re-tag."""
    regions = list(payload.get("regions") or [])
    assignments = list(payload.get("assignments") or [])
    region_idx = _region_index(regions)
    by_region: dict[str, list[str]] = defaultdict(list)
    unassigned = 0
    for a in assignments:
        rel = a.get("rel_path") or a.get("doc_id") or ""
        rids = [r for r in (a.get("region_ids") or []) if r in region_idx]
        if not rids:
            unassigned += 1
            continue
        for rid in rids:
            by_region[rid].append(rel)

    findings: list[dict] = []
    if unassigned:
        findings.append(
            {
                "kind": "unassigned",
                "region_id": UNASSIGNED_ID,
                "detail": f"{unassigned} files have no region_ids",
                "docs": unassigned,
            }
        )

    for parent_id, node in _walk_regions(regions):
        rid = str(node["id"])
        n = len(by_region.get(rid) or [])
        if n == 0:
            findings.append(
                {
                    "kind": "empty-node",
                    "region_id": rid,
                    "detail": f"{node.get('label') or rid} has no assigned files",
                    "docs": 0,
                }
            )
        elif parent_id and n <= SINGULARITY_DOCS:
            findings.append(
                {
                    "kind": "singularity",
                    "region_id": rid,
                    "detail": f"{node.get('label') or rid} is a one-file child (NN/g singularity)",
                    "docs": n,
                }
            )
        elif n >= fat_at:
            findings.append(
                {
                    "kind": "fat-branch",
                    "region_id": rid,
                    "detail": (
                        f"{node.get('label') or rid} has {n} files "
                        f"(≥{fat_at}). Audit will chunk; consider a granular split."
                    ),
                    "docs": n,
                }
            )
        if parent_id and parent_id in by_region:
            child_set = set(by_region.get(rid) or [])
            parent_set = set(by_region[parent_id])
            # ISO BT/NT: narrower scope ⊆ broader. File membership is a proxy.
            extra = child_set - parent_set
            if extra and len(extra) > n * 0.25:
                findings.append(
                    {
                        "kind": "scope-drift",
                        "region_id": rid,
                        "detail": (
                            f"{len(extra)} child files are not also on parent "
                            f"{parent_id} (scope-inclusion proxy)"
                        ),
                        "docs": len(extra),
                    }
                )
    findings.sort(key=lambda f: (f["kind"], f["region_id"]))
    return findings


def _also_under(assignment: dict, primary: str) -> list[str]:
    others = [
        str(r)
        for r in (assignment.get("region_ids") or [])
        if r and r != primary
    ]
    return others[:8]


def _file_line(assignment: dict, primary: str) -> str:
    tags = ", ".join((assignment.get("matched_tags") or [])[:10])
    also = _also_under(assignment, primary)
    also_s = f"  also under: {', '.join(also)}" if also else ""
    summary = str(assignment.get("summary") or "")[:280]
    return (
        f"- PATH: {assignment.get('rel_path')}\n"
        f"  tags: {tags or '(none)'}{also_s}\n"
        f"  summary: {summary}"
    )


def _chunk_prompt(chunk: dict) -> str:
    tree = ", ".join(chunk.get("tree_ids") or [])
    parent = chunk.get("parent_label") or "(top-level topic)"
    files = chunk.get("files") or []
    lines = [
        f"GROUP: {chunk['label']}  (id={chunk['region_id']})",
        f"PARENT: {parent}",
        f"DESCRIPTION: {chunk.get('description') or ''}",
        f"GROUP SIZE: {chunk['group_file_count']} files. "
        f"CHUNK {chunk['chunk_index'] + 1} of {chunk['chunk_count']} "
        f"({len(files)} files in this call).",
    ]
    if chunk.get("chunked"):
        lines.append(
            "This group was too large for one prompt. You are continuing the "
            "SAME group. Do not invent a new topic. Judge only the files below."
        )
    lines.extend(
        [
            "",
            f"TREE LIST (valid better_home values): {tree}",
            "",
            "FILES:",
        ]
    )
    for a in files:
        lines.append(_file_line(a, chunk["region_id"]))
    return "\n".join(lines)


def _empty_verdict(rel_path: str, reason: str) -> dict:
    return {
        "rel_path": rel_path,
        "verdict": "cannot-tell",
        "better_home": "",
        "reason": reason,
    }


def normalize_chunk_result(raw: dict, chunk: dict) -> dict:
    """Keep only listed files; fill gaps so a short model reply cannot drop a path."""
    wanted = [a.get("rel_path") for a in (chunk.get("files") or [])]
    by_path = {p: None for p in wanted}
    for item in raw.get("files") or []:
        if not isinstance(item, dict):
            continue
        rel = item.get("rel_path")
        if rel not in by_path:
            continue
        verdict = str(item.get("verdict") or "cannot-tell").strip()
        if verdict not in VERDICTS:
            verdict = "cannot-tell"
        by_path[rel] = {
            "rel_path": rel,
            "verdict": verdict,
            "better_home": str(item.get("better_home") or "").strip(),
            "reason": str(item.get("reason") or "").strip()[:400],
        }
    files = [
        by_path[p] or _empty_verdict(p, "Model omitted this file.")
        for p in wanted
    ]
    return {
        "group_notes": str(raw.get("group_notes") or "").strip()[:800],
        "files": files,
    }


def state_path(cfg: dict) -> Path:
    return output_dir(cfg) / "audit-state.json"


def load_state(cfg: dict) -> dict:
    data = load_json(state_path(cfg), {"chunks": {}, "started_at": None})
    data.setdefault("chunks", {})
    return data


def _audit_cfg(cfg: dict) -> dict:
    """Give L2 room: long timeout, enough tokens for 12 file verdicts."""
    stitch_cfg = dict(cfg)
    ollama = dict(cfg.get("ollama") or {})
    ollama["timeout_seconds"] = max(int(ollama.get("timeout_seconds") or 300), 600)
    ollama["max_tokens"] = max(int(ollama.get("max_tokens") or 2048), 4096)
    stitch_cfg["ollama"] = ollama
    return stitch_cfg


def audit_chunk(cfg: dict, chunk: dict) -> dict:
    raw = chat(
        _audit_cfg(cfg),
        [
            {"role": "system", "content": AUDIT_SYSTEM},
            {"role": "user", "content": _chunk_prompt(chunk)},
        ],
        step=f"audit:{chunk['chunk_id']}",
    )
    if not isinstance(raw, dict):
        raise RuntimeError("audit model did not return a JSON object")
    return normalize_chunk_result(raw, chunk)


def _plan_md(chunks: list[dict], findings: list[dict]) -> str:
    lines = [
        "# Audit plan (group-at-a-time)",
        "",
        "Work order is the browse tree: parent, then children, then unassigned.",
        f"Fat groups (>{AUDIT_GROUP_MAX} files) are split into chunks. "
        "That split is a **workaround** — a later granular node is the real fix.",
        "",
        f"**Chunks:** {len(chunks)}",
        f"**L1 findings:** {len(findings)}",
        "",
        "## L1 graph",
        "",
    ]
    if not findings:
        lines.append("No structural flags.")
        lines.append("")
    for f in findings:
        lines.append(f"- `{f['kind']}` `{f['region_id']}` — {f['detail']}")
    lines.extend(["", "## Work order", "", "| # | Group | Files | Chunks | Why split |", "|---|---|---|---|---|"])
    seen: set[str] = set()
    n = 0
    for c in chunks:
        rid = c["region_id"]
        if rid in seen:
            continue
        seen.add(rid)
        n += 1
        why = (
            f">{AUDIT_GROUP_MAX} files; split so the model can finish JSON"
            if c["chunked"]
            else "fits in one call"
        )
        lines.append(
            f"| {n} | {c['label']} (`{rid}`) | {c['group_file_count']} | "
            f"{c['chunk_count']} | {why} |"
        )
    lines.append("")
    return "\n".join(lines)


def _audit_md(chunks: list[dict], state: dict, findings: list[dict]) -> str:
    done = state.get("chunks") or {}
    flags: list[str] = []
    confirms = 0
    skipped = 0
    failed = 0
    for c in chunks:
        rec = done.get(c["chunk_id"]) or {}
        status = rec.get("status")
        if status == "skipped":
            skipped += 1
            continue
        if status == "failed":
            failed += 1
            flags.append(
                f"- **chunk failed** `{c['chunk_id']}` {c['label']} — "
                f"{rec.get('error') or 'see log'}"
            )
            continue
        if status != "done":
            continue
        for item in rec.get("files") or []:
            v = item.get("verdict")
            if v == "confirm":
                confirms += 1
                continue
            home = item.get("better_home") or ""
            extra = f" → `{home}`" if home else ""
            flags.append(
                f"- **{v}** `{item.get('rel_path')}` in {c['label']}{extra} — "
                f"{item.get('reason') or ''}"
            )

    lines = [
        "# Placement audit",
        "",
        "L2 checked existing stitch homes, one group at a time. "
        "Confirms stay put. Flags below are the L3 queue.",
        "",
        f"**Confirms:** {confirms}",
        f"**Flags:** {len(flags)}",
        f"**Failed chunks:** {failed}",
        f"**Not yet run:** {skipped}",
        f"**L1 findings:** {len(findings)}",
        "",
        "## Flags (fix these)",
        "",
    ]
    if not flags:
        lines.append("No placement flags in completed chunks.")
    else:
        lines.extend(flags)
    lines.extend(["", "## Group notes", ""])
    for c in chunks:
        rec = done.get(c["chunk_id"]) or {}
        notes = rec.get("group_notes")
        if notes:
            part = (
                f" (chunk {c['chunk_index'] + 1}/{c['chunk_count']})"
                if c["chunked"]
                else ""
            )
            lines.append(f"### {c['label']}{part}")
            lines.append("")
            lines.append(notes)
            lines.append("")
    return "\n".join(lines)


def write_audit_artifacts(
    cfg: dict, chunks: list[dict], state: dict, findings: list[dict]
) -> None:
    out = output_dir(cfg)
    out.mkdir(parents=True, exist_ok=True)
    atomic_write(out / "AUDIT-PLAN.md", _plan_md(chunks, findings))
    graph_only = _plan_md(chunks, findings)
    cut = graph_only.find("## Work order")
    atomic_write(out / "AUDIT-GRAPH.md", graph_only[:cut] if cut >= 0 else graph_only)
    atomic_write(out / "AUDIT.md", _audit_md(chunks, state, findings))
    atomic_write_json(
        out / "audit.json",
        {
            "meta": {
                "built_at": utc_now(),
                "group_max": AUDIT_GROUP_MAX,
                "chunks": len(chunks),
                "findings": len(findings),
            },
            "findings": findings,
            "chunks": [
                {
                    "chunk_id": c["chunk_id"],
                    "region_id": c["region_id"],
                    "label": c["label"],
                    "chunked": c["chunked"],
                    "group_file_count": c["group_file_count"],
                    "chunk_index": c["chunk_index"],
                    "chunk_count": c["chunk_count"],
                    "paths": [a.get("rel_path") for a in c["files"]],
                    "result": (state.get("chunks") or {}).get(c["chunk_id"]),
                }
                for c in chunks
            ],
        },
    )


def run_audit(
    cfg: dict,
    *,
    force: bool = False,
    limit: int | None = None,
    max_n: int = AUDIT_GROUP_MAX,
) -> dict:
    """L1 then L2. Resume skips chunks with status=done unless force."""
    payload = load_regions(cfg)
    findings = graph_findings(payload)
    chunks = plan_groups(payload, max_n=max_n)
    state = load_state(cfg)
    state.setdefault("started_at", utc_now())
    if force:
        state["chunks"] = {}

    todo = []
    for c in chunks:
        rec = (state.get("chunks") or {}).get(c["chunk_id"]) or {}
        if rec.get("status") == "done":
            continue
        todo.append(c)
    if limit is not None:
        todo = todo[:limit]

    progress = Progress(cfg, "audit", len(todo))
    done_n = 0
    for i, chunk in enumerate(todo, start=1):
        label = f"{chunk['label']} {chunk['chunk_index'] + 1}/{chunk['chunk_count']}"
        try:
            progress.tick(i, label)
            result = audit_chunk(cfg, chunk)
            state["chunks"][chunk["chunk_id"]] = {
                "status": "done",
                "at": utc_now(),
                "group_notes": result.get("group_notes") or "",
                "files": result.get("files") or [],
            }
            done_n += 1
        except OPERATOR_STOP:
            raise
        except Exception as exc:
            # GOLDEN RULE: one fat/broken chunk must not kill the rest.
            print(f"  audit chunk failed {chunk['chunk_id']}: {exc}", flush=True)
            state["chunks"][chunk["chunk_id"]] = {
                "status": "failed",
                "at": utc_now(),
                "error": str(exc)[:500],
                "files": [
                    _empty_verdict(a.get("rel_path"), f"Chunk failed: {exc}")
                    for a in chunk["files"]
                ],
            }
        atomic_write_json(state_path(cfg), state)
        write_audit_artifacts(cfg, chunks, state, findings)

    progress.finish(done_n)
    write_audit_artifacts(cfg, chunks, state, findings)
    out = output_dir(cfg)
    print(
        f"audit: {done_n} chunks this run, {len(chunks)} planned, "
        f"{len(findings)} L1 flags → {out / 'AUDIT.md'}"
    )
    return {"chunks_run": done_n, "chunks_planned": len(chunks), "findings": len(findings)}
