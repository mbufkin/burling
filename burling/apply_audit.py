"""Apply L2 audit flags to an existing stitch tree.

Best practice (docs/ralp-loop.md, Cormack & Grossman CAL):
  Audit is not the product. The next step is to *move* files and
  revise mixed groups, then audit a fresh pass. Confirms stay put.
  cannot-tell stays put. better_home must already exist on the tree.
"""

from __future__ import annotations

from burling.audit import NEEDS_REVIEW_ID, UNASSIGNED_ID, load_state
from burling.stitch_tags import _region_index

APPLYABLE = frozenset(
    {"wrong-parent", "missing-parent", "leftover-should-place"}
)


def apply_audit_to_payload(payload: dict, state: dict) -> dict:
    """Return {payload, applied, skipped} after mutating assignment copies."""
    regions = list(payload.get("regions") or [])
    idx = _region_index(regions)
    assignments = [dict(a) for a in (payload.get("assignments") or [])]
    by_path = {str(a.get("rel_path") or ""): a for a in assignments}

    applied: list[dict] = []
    skipped: list[dict] = []

    for chunk_id, rec in (state.get("chunks") or {}).items():
        if rec.get("status") != "done":
            continue
        for item in rec.get("files") or []:
            if not isinstance(item, dict):
                continue
            path = str(item.get("rel_path") or "")
            verdict = str(item.get("verdict") or "")
            home = str(item.get("better_home") or "").strip()
            row = {
                "rel_path": path,
                "verdict": verdict,
                "better_home": home,
                "chunk_id": chunk_id,
                "reason": item.get("reason") or "",
            }
            if verdict not in APPLYABLE:
                continue
            target = by_path.get(path)
            if not target:
                row["skip"] = "unknown-path"
                skipped.append(row)
                continue
            if not home or home not in idx or home == UNASSIGNED_ID:
                row["skip"] = "invalid-home"
                skipped.append(row)
                continue

            current = [str(r) for r in (target.get("region_ids") or []) if r]
            if verdict == "wrong-parent":
                # Replace the audited home; keep a second real parent if present.
                rest = [
                    r
                    for r in current
                    if r not in {home, NEEDS_REVIEW_ID, UNASSIGNED_ID}
                ]
                target["region_ids"] = [home] + rest
            elif verdict == "missing-parent":
                if home in current:
                    row["skip"] = "already-has-home"
                    skipped.append(row)
                    continue
                target["region_ids"] = current + [home]
            else:  # leftover-should-place
                target["region_ids"] = [home]
            applied.append(row)

    out = dict(payload)
    out["assignments"] = assignments
    return {"payload": out, "applied": applied, "skipped": skipped}


def flag_rate(state: dict) -> float:
    """Share of completed file verdicts that are not confirm."""
    done = 0
    flags = 0
    for rec in (state.get("chunks") or {}).values():
        if rec.get("status") != "done":
            continue
        for item in rec.get("files") or []:
            done += 1
            if item.get("verdict") and item.get("verdict") != "confirm":
                flags += 1
    if not done:
        return 0.0
    return flags / done


def should_stop_ralp(
    *,
    applied_n: int,
    rate: float,
    round_i: int,
    max_rounds: int,
    stop_flag_rate: float = 0.15,
    prev_rate: float | None = None,
) -> str | None:
    """CAL-style stop: watch the yield curve, then cap.

    Best practice (Cormack & Grossman): do not keep applying if the
    next audit is *worse*. Rising flag rate means the last edits
    mixed the tree. Stop before another apply. A low rate or a
    zero-apply round is a real stop; hitting max-rounds is a cap,
    not success.
    """
    if prev_rate is not None and rate > prev_rate + 1e-9:
        return "flags-rose"
    if round_i >= max_rounds:
        return "max-rounds"
    if applied_n == 0:
        return "no-applies"
    if rate < stop_flag_rate:
        return "flag-rate"
    return None


def load_apply_state(cfg: dict) -> dict:
    return load_state(cfg)
