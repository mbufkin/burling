"""RALP — Revise-Audit Loop for Placement.

docs/ralp-loop.md. The 30B organizes *groups* (name + decision rule +
split). Code clusters, applies moves, and stops when a fresh audit
applies nothing (CAL yield drop), not when the model repeats itself.

Works on any --intake folder. No district or handover vocabulary.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from burling.apply_audit import (
    apply_audit_to_payload,
    flag_rate,
    should_stop_ralp,
)
from burling.audit import NEEDS_REVIEW_ID, UNASSIGNED_ID, load_regions, load_state, run_audit
from burling.io_util import atomic_write, atomic_write_json
from burling.ollama_client import chat
from burling.paths import output_dir
from burling.stitch_tags import (
    _region_index,
    _regions_md,
    _simple_region_html,
    write_stitch_topic_map,
)
from burling.trace import utc_now

DEFAULT_MAX_ROUNDS = 3
DEFAULT_STOP_FLAG_RATE = 0.15
# One wrong-parent is enough. The old floor of 3 meant a 1–2 file
# group never earned a 30B revise, so apply ran naked and the tree got worse.
REVISE_WRONG_PARENT_MIN = 1

REVISE_SYSTEM = """You are revising ONE browse group in a document collection.
The audit said this group is mixed. Do real organizational work.
Do not invent a job handover, a district, or a successor story.
Do not emit keyword tags. Write a decision rule a stranger could apply.

Output ONLY a single JSON object:
{
  "action": "keep | rename | split | dissolve",
  "label": "Human label for this group (or empty if dissolve)",
  "description": "A file belongs here if … (2-4 sentences, testable)",
  "children": [
    {
      "id": "kebab-id",
      "label": "Human label",
      "description": "A file belongs here if …",
      "member_paths": ["exact rel_path from the list"]
    }
  ],
  "notes": "why this edit"
}

Rules:
- keep: the group is coherent; maybe tighten the description.
- rename: same members, clearer label + rule.
- split: two or more children when members are genuinely different topics.
  Every listed path must appear in exactly one child. Do not leave a
  catch-all child named Other / Misc / General.
- dissolve: this is not a real topic; leave children empty. The harness
  will park members on the parent or needs-review.
- Do not invent paths. Do not invent programs that are not in the file list.
"""


def persist_payload(cfg: dict, payload: dict) -> None:
    """Write regions + maps. No model call."""
    out = output_dir(cfg)
    out.mkdir(parents=True, exist_ok=True)
    atomic_write_json(out / "regions.json", payload)
    regions = list(payload.get("regions") or [])
    assignments = list(payload.get("assignments") or [])
    idx = _region_index(regions)
    meta = dict(payload.get("meta") or {})
    meta.setdefault("documents", len(assignments))
    meta.setdefault("top_level", len(regions))
    meta.setdefault("nodes", len(idx))
    meta.setdefault("docs_mapped", sum(1 for a in assignments if a.get("region_ids")))
    atomic_write(out / "REGIONS.md", _regions_md(regions, idx, assignments, meta))
    _simple_region_html(payload, out / "regions.html")
    write_stitch_topic_map(out, payload, idx)


def dissolve_singularities(payload: dict, *, min_docs: int = 2) -> list[str]:
    """Fold one-file (and empty) children into their parent. No model call.

    Best practice (NN/g singularity): a folder with one file is wasted
    structure. TaxoGen pushes general members back to the parent. Do
    that in code so the 30B revises *mixed* groups, not thin labels.
    Top-level topics stay even if they are small — they are the map.
    """
    notes: list[str] = []
    regions = payload.get("regions") or []

    def member_count(rid: str) -> int:
        return sum(
            1
            for a in payload.get("assignments") or []
            if rid in (a.get("region_ids") or [])
        )

    def dissolve_id(rid: str, dest: str) -> int:
        moved = 0
        for a in payload.get("assignments") or []:
            rids = [str(r) for r in (a.get("region_ids") or [])]
            if rid not in rids:
                continue
            nxt: list[str] = []
            for r in rids:
                keep = dest if r == rid else r
                if keep and keep not in nxt:
                    nxt.append(keep)
            a["region_ids"] = nxt
            moved += 1
        _remove_node(regions, rid)
        return moved

    def walk(nodes: list, parent_id: str | None) -> None:
        for node in list(nodes or []):
            if not isinstance(node, dict):
                continue
            walk(node.get("children") or [], str(node.get("id") or ""))
            if not parent_id:
                continue
            rid = str(node.get("id") or "")
            if not rid:
                continue
            n = member_count(rid)
            if n < min_docs:
                moved = dissolve_id(rid, parent_id)
                notes.append(f"{rid}: folded {moved} file(s) → {parent_id}")

    walk(regions, None)
    return notes


def _mixed_groups(state: dict, *, min_wrong: int = REVISE_WRONG_PARENT_MIN) -> list[str]:
    """Region ids with at least one wrong-parent — those get a 30B revise.

    Best practice: do not wait for a pile of three mistakes. On a small
    dump every group is 1–2 files; skipping revise leaves apply as a
    random walk. Leftover bins are not topics.
    """
    skip = {NEEDS_REVIEW_ID, "needs-review", UNASSIGNED_ID, "unassigned"}
    counts: dict[str, int] = defaultdict(int)
    for chunk_id, rec in (state.get("chunks") or {}).items():
        if rec.get("status") != "done":
            continue
        rid = str(chunk_id).split("#")[0]
        if rid in skip:
            continue
        for item in rec.get("files") or []:
            if item.get("verdict") == "wrong-parent":
                counts[rid] += 1
    return sorted(rid for rid, n in counts.items() if n >= min_wrong)


def _group_members(payload: dict, region_id: str) -> list[dict]:
    out = []
    for a in payload.get("assignments") or []:
        if region_id in (a.get("region_ids") or []):
            out.append(a)
    out.sort(key=lambda a: a.get("rel_path") or "")
    return out


def _find_node(nodes: list[dict], rid: str) -> dict | None:
    for node in nodes or []:
        if not isinstance(node, dict):
            continue
        if str(node.get("id")) == rid:
            return node
        hit = _find_node(node.get("children") or [], rid)
        if hit:
            return hit
    return None


def _parent_of_id(regions: list[dict], rid: str) -> dict | None:
    idx = _region_index(regions)
    pid = (idx.get(rid) or {}).get("parent_id")
    if not pid:
        return None
    return _find_node(regions, str(pid))


def revise_group(cfg: dict, payload: dict, region_id: str) -> dict:
    """Ask the 30B to keep / rename / split / dissolve one mixed group."""
    node = _find_node(payload.get("regions") or [], region_id)
    if not node:
        return {"action": "keep", "notes": "missing node"}
    members = _group_members(payload, region_id)
    if region_id in {NEEDS_REVIEW_ID, "needs-review"}:
        return {"action": "keep", "notes": "leftover bin is not a topic"}
    lines = [
        f"GROUP: {node.get('label')} (id={region_id})",
        f"CURRENT RULE: {node.get('description') or ''}",
        "",
        "MEMBERS:",
    ]
    for a in members[:40]:
        summary = str(a.get("summary") or "")[:240]
        lines.append(f"- {a.get('rel_path')}: {summary}")
    if len(members) > 40:
        lines.append(f"… {len(members) - 40} more not shown")
    raw = chat(
        cfg,
        [
            {"role": "system", "content": REVISE_SYSTEM},
            {"role": "user", "content": "\n".join(lines)},
        ],
        step=f"ralp-revise:{region_id}",
    )
    if not isinstance(raw, dict):
        return {"action": "keep", "notes": "revise did not return JSON"}
    action = str(raw.get("action") or "keep").strip()
    if action not in {"keep", "rename", "split", "dissolve"}:
        action = "keep"
    raw["action"] = action
    return raw


def _apply_revise(payload: dict, region_id: str, edit: dict) -> str:
    """Mutate the tree from a revise JSON. Returns a short log line."""
    regions = payload.get("regions") or []
    node = _find_node(regions, region_id)
    if not node:
        return f"{region_id}: missing"
    action = edit.get("action") or "keep"
    if action == "rename":
        if edit.get("label"):
            node["label"] = str(edit["label"])[:80]
        if edit.get("description"):
            node["description"] = str(edit["description"])[:500]
        return f"{region_id}: renamed → {node.get('label')}"
    if action == "keep":
        if edit.get("description"):
            node["description"] = str(edit["description"])[:500]
        return f"{region_id}: kept (rule updated)" if edit.get("description") else f"{region_id}: kept"
    if action == "dissolve":
        parent = _parent_of_id(regions, region_id)
        dest = str(parent["id"]) if parent else NEEDS_REVIEW_ID
        for a in payload.get("assignments") or []:
            rids = [str(r) for r in (a.get("region_ids") or [])]
            if region_id in rids:
                a["region_ids"] = [dest if r == region_id else r for r in rids]
        kids = node.get("children") or []
        # Drop this node from its sibling list.
        _remove_node(regions, region_id)
        return f"{region_id}: dissolved → {dest} (dropped {len(kids)} children)"
    if action == "split":
        children = []
        seen: set[str] = set()
        for child in edit.get("children") or []:
            if not isinstance(child, dict):
                continue
            cid = str(child.get("id") or "").strip()
            if not cid or cid in seen:
                continue
            seen.add(cid)
            paths = [str(p) for p in (child.get("member_paths") or []) if p]
            children.append(
                {
                    "id": cid,
                    "label": str(child.get("label") or cid)[:80],
                    "description": str(child.get("description") or "")[:500],
                    "tags": [],
                    "children": [],
                    "_paths": paths,
                }
            )
        if len(children) < 2:
            return f"{region_id}: split ignored (need ≥2 children)"
        by_path = {str(a.get("rel_path")): a for a in (payload.get("assignments") or [])}
        new_kids = []
        for ch in children:
            paths = ch.pop("_paths")
            new_kids.append(ch)
            for path in paths:
                a = by_path.get(path)
                if not a:
                    continue
                rids = [str(r) for r in (a.get("region_ids") or []) if r != region_id]
                a["region_ids"] = [ch["id"]] + [r for r in rids if r != ch["id"]]
        node["children"] = (node.get("children") or []) + new_kids
        if edit.get("description"):
            node["description"] = str(edit["description"])[:500]
        return f"{region_id}: split → {len(new_kids)} children"
    return f"{region_id}: {action}"


def _remove_node(nodes: list[dict], rid: str) -> bool:
    for i, node in enumerate(list(nodes or [])):
        if not isinstance(node, dict):
            continue
        if str(node.get("id")) == rid:
            nodes.pop(i)
            return True
        if _remove_node(node.get("children") or [], rid):
            return True
    return False


def write_ralp_log(cfg: dict, rounds: list[dict], stop: str) -> Path:
    out = output_dir(cfg)
    lines = [
        "# RALP log",
        "",
        "Organize → audit → apply → revise mixed groups → audit again.",
        "The 30B writes decision rules and splits. Code applies and stops.",
        "",
        f"**Stop:** `{stop}`",
        f"**Rounds:** {len(rounds)}",
        "",
        "| Round | Flags | Flag rate | Applied | Skipped | Revise |",
        "|---|---|---|---|---|---|",
    ]
    for r in rounds:
        lines.append(
            f"| {r['round']} | {r['flags']} | {r['flag_rate']:.0%} | "
            f"{r['applied']} | {r['skipped']} | {r.get('revise') or '—'} |"
        )
    lines.extend(["", "## Notes", ""])
    for r in rounds:
        for note in r.get("notes") or []:
            lines.append(f"- R{r['round']}: {note}")
    lines.append("")
    path = out / "RALP.md"
    atomic_write(path, "\n".join(lines))
    atomic_write_json(
        out / "ralp-state.json",
        {"stop": stop, "rounds": rounds, "updated_at": utc_now()},
    )
    return path


def run_ralp(
    cfg: dict,
    *,
    max_rounds: int = DEFAULT_MAX_ROUNDS,
    stop_flag_rate: float = DEFAULT_STOP_FLAG_RATE,
    tags_force: bool = False,
) -> dict:
    """Full loop on whatever is in cfg intake / output. Any dump."""
    from burling.queue import build_queue
    from burling.stitch_tags import run_stitch
    from burling.tag_rich import run_rich_tags

    out = output_dir(cfg)
    if not (out / "tags.json").is_file() or tags_force:
        print("RALP 0a: extract + rich tags (description pass)", flush=True)
        build_queue(cfg)
        run_rich_tags(cfg, force=tags_force)
    if not (out / "regions.json").is_file():
        print("RALP 0b: organize (cluster + name/rule)", flush=True)
        run_stitch(cfg)

    payload = load_regions(cfg)
    folded = dissolve_singularities(payload)
    if folded:
        print(f"RALP 0c: folded {len(folded)} thin children into parents", flush=True)
        persist_payload(cfg, payload)

    rounds: list[dict] = []
    stop = "max-rounds"
    prev_rate: float | None = None
    for i in range(1, max_rounds + 1):
        print(f"RALP {i}: audit", flush=True)
        # Fresh L2 each round so we are not scoring the same frozen state
        # (Cormack & Grossman: do not freeze at 'stabilization').
        run_audit(cfg, force=True)
        state = load_state(cfg)
        payload = load_regions(cfg)
        rate = flag_rate(state)
        flags = sum(
            1
            for rec in (state.get("chunks") or {}).values()
            if rec.get("status") == "done"
            for item in rec.get("files") or []
            if item.get("verdict") and item.get("verdict") != "confirm"
        )
        notes: list[str] = []
        # If this audit is worse than the last, do not apply it.
        if prev_rate is not None and rate > prev_rate + 1e-9:
            notes.append(
                f"skipped apply: flag rate rose {prev_rate:.0%} → {rate:.0%}"
            )
            rec = {
                "round": i,
                "flags": flags,
                "flag_rate": rate,
                "applied": 0,
                "skipped": 0,
                "revise": "",
                "notes": notes,
            }
            rounds.append(rec)
            stop = "flags-rose"
            print(
                f"RALP {i}: flags={flags} rate={rate:.0%} "
                f"applied=0 stop=flags-rose",
                flush=True,
            )
            break

        result = apply_audit_to_payload(payload, state)
        persist_payload(cfg, result["payload"])
        notes.extend(dissolve_singularities(result["payload"]))
        mixed = _mixed_groups(state)
        for rid in mixed:
            print(f"RALP {i}: revise mixed group {rid}", flush=True)
            edit = revise_group(cfg, result["payload"], rid)
            notes.append(_apply_revise(result["payload"], rid, edit))
        persist_payload(cfg, result["payload"])
        rec = {
            "round": i,
            "flags": flags,
            "flag_rate": rate,
            "applied": len(result["applied"]),
            "skipped": len(result["skipped"]),
            "revise": ", ".join(mixed) if mixed else "",
            "notes": notes,
        }
        rounds.append(rec)
        why = should_stop_ralp(
            applied_n=len(result["applied"]),
            rate=rate,
            round_i=i,
            max_rounds=max_rounds,
            stop_flag_rate=stop_flag_rate,
            prev_rate=None,
        )
        print(
            f"RALP {i}: flags={flags} rate={rate:.0%} "
            f"applied={rec['applied']} stop={why or 'continue'}",
            flush=True,
        )
        if why:
            stop = why
            break
        prev_rate = rate

    path = write_ralp_log(cfg, rounds, stop)
    print(f"RALP done ({stop}) → {path}", flush=True)
    return {"stop": stop, "rounds": rounds, "log": str(path)}
