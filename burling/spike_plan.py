"""Staged organize spike: main → combine → sub → detail → review.

This is the step sequence the 20news NVIDIA run is for. Tag **one layer**
across every file, then fold that layer from ids+counts. Do not pick
main/sub/detail in one window — that hid the bush until it was too late.

Workplace CTE dumps never use this module's NIM path.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from burling.census_plan import (
    MAIN_SYSTEM,
    SUB_SYSTEM,
    apply_groups,
    coerce_groups,
    counts_for,
    mains_user_prompt,
    subs_user_prompt,
)
from burling.file_plan import UNMAPPED_ID, is_banned_head
from burling.isolate import OPERATOR_STOP, note_file_failure
from burling.io_util import atomic_write_json
from burling.layer_plan import _doc_text, kebab
from burling.ollama_client import assert_cloud_allowed, chat
from burling.paths import output_dir
from burling.progress import Progress, console_safe
from burling.trace import utc_now

# Cheap enough for NIM. A 20news post is a few KB; 80k is a workplace PDF.
SPIKE_DOC_CAP = 8_000

ALL_STAGES = (
    "main",
    "combine-mains",
    "sub",
    "combine-subs",
    "detail",
    "combine-details",
)

MAIN_TAG_SYSTEM = """You are a records clerk filing Usenet / news articles.
Assign ONE browse MAIN. You are not picking a sub or a detail yet.

Output ONLY a valid JSON object:
{
  "reasoning": "The subject is X.",
  "main": "kebab-id",
  "summary": "One clear sentence."
}

Rules:
- main is a subject a stranger would open (hockey, space, cryptography, autos).
- Not a year, newsgroup name, email address, or filename.
- Not misc / other / general / discussion / unmapped unless the text has no subject.
- Prefer a short existing-kind name over a unique phrase.
"""

CHILD_TAG_SYSTEM = """You are filing ONE article inside a parent folder.
Look at the drawers that already exist in this cabinet. Prefer reuse.

Output ONLY a valid JSON object:
{
  "reasoning": "Existing drawers are A, B. This article belongs with X.",
  "name": "kebab-id-or-empty",
  "summary": "One clear sentence."
}

Rules:
- If an EXISTING name already fits, copy it character for character.
- Invent a new kebab id only when none of the existing names fit.
- Empty string means stay in the parent (no narrower drawer).
- Year, email, usenet, misc, other, and the parent name are not drawers.
"""


def coerce_open_id(raw: object) -> str:
    """Open discovery: kebab + ban channel/year. Not the 13 workplace series."""
    name = kebab(raw)
    if not name or name == UNMAPPED_ID or is_banned_head(name, name):
        return ""
    return name


def _state_path(cfg: dict) -> Path:
    return output_dir(cfg) / "spike-tags.json"


def load_spike_state(cfg: dict) -> dict[str, dict]:
    path = _state_path(cfg)
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    by_path: dict[str, dict] = {}
    for rec in data.get("documents") or []:
        if isinstance(rec, dict) and rec.get("rel_path"):
            by_path[str(rec["rel_path"])] = rec
    return by_path


def save_spike_state(cfg: dict, by_path: dict[str, dict]) -> None:
    docs = list(by_path.values())
    atomic_write_json(
        _state_path(cfg),
        {
            "count": len(docs),
            "documents": docs,
            "method": "spike-stages",
            "at": utc_now(),
        },
    )


def _blank_rec(rel: str) -> dict:
    return {
        "rel_path": rel,
        "main": "",
        "sub": "",
        "detail": "",
        "summary": "",
        "reasoning": "",
        "status": "pending",
        "at": utc_now(),
    }


def _records_list(by_path: dict[str, dict], source: list[dict]) -> list[dict]:
    ordered: list[dict] = []
    seen: set[str] = set()
    for rec in source:
        rel = str(rec.get("rel_path") or "")
        if rel and rel in by_path and rel not in seen:
            ordered.append(by_path[rel])
            seen.add(rel)
    return ordered


def existing_children(records: list[dict], *, main: str, sub: str | None = None) -> list[tuple[str, int]]:
    """Counts of the next layer inside one cabinet. Shown so the clerk reuses."""
    if sub is None:
        return counts_for(records, "sub", main=main)
    counts: dict[str, int] = defaultdict(int)
    for rec in records:
        if kebab(rec.get("main")) != main:
            continue
        if kebab(rec.get("sub")) != sub:
            continue
        name = kebab(rec.get("detail"))
        if name:
            counts[name] += 1
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))


def child_user_prompt(
    *,
    parent: str,
    rel_path: str,
    text: str,
    existing: list[tuple[str, int]],
) -> str:
    lines = [
        f"PARENT: {parent}",
        f"FILE: {rel_path}",
        "",
        "EXISTING DRAWERS IN THIS CABINET (id: files). Copy one if it fits:",
    ]
    if existing:
        for name, n in existing:
            lines.append(f"- {name}: {n}")
    else:
        lines.append("(none yet — invent if the article has a narrower subject)")
    lines += ["", "DOCUMENT TEXT:", text]
    return "\n".join(lines)


def details_user_prompt(main: str, sub: str, n_files: int, details: list[tuple[str, int]]) -> str:
    n = len(details)
    lines = [
        f"PARENT: {main}/{sub}. {n_files} files, {n} unique details.",
        "Fold same-kind ids (singular/plural, spelling). Leave unlike kinds apart.",
        "Do not dump leftovers into the parent or misc.",
        "",
        "DETAILS (id: files):",
    ]
    for name, n_files_id in details:
        lines.append(f"- {name}: {n_files_id}")
    return "\n".join(lines)


def apply_field_map(
    records: list[dict],
    field: str,
    mapping: dict[str, str],
    *,
    main: str | None = None,
    sub: str | None = None,
) -> int:
    """Rewrite one layer. Code is the records office; the model only proposed."""
    changed = 0
    for rec in records:
        if main is not None and kebab(rec.get("main")) != main:
            continue
        if sub is not None and kebab(rec.get("sub")) != sub:
            continue
        cur = kebab(rec.get(field))
        nxt = mapping.get(cur, cur)
        if nxt != cur:
            rec[field] = nxt
            rec["at"] = utc_now()
            changed += 1
    return changed


def _ask(cfg: dict, messages: list[dict], step: str) -> dict:
    raw = chat(cfg, messages, step=step)
    return raw if isinstance(raw, dict) else {}


def _tag_mains(
    cfg: dict,
    by_path: dict[str, dict],
    pending: list[str],
    *,
    force: bool,
) -> None:
    progress = Progress(cfg, "spike-main", len(pending))
    try:
        for i, rel in enumerate(pending, start=1):
            progress.tick(i, rel)
            rec = by_path.setdefault(rel, _blank_rec(rel))
            if rec.get("main") and rec.get("status") == "done" and not force:
                continue
            try:
                text = (_doc_text(cfg, rel) or "")[:SPIKE_DOC_CAP]
                if not text:
                    rec.update(
                        {
                            "main": "",
                            "summary": "extract missing",
                            "status": "done",
                            "at": utc_now(),
                        }
                    )
                else:
                    user = f"FILE: {rel}\n\nDOCUMENT TEXT:\n{text}"
                    raw = _ask(
                        cfg,
                        [
                            {"role": "system", "content": MAIN_TAG_SYSTEM},
                            {"role": "user", "content": user},
                        ],
                        step=f"spike-main:{rel}",
                    )
                    rec["main"] = coerce_open_id(raw.get("main"))
                    rec["summary"] = str(raw.get("summary") or "")[:500]
                    rec["reasoning"] = str(raw.get("reasoning") or "")[:500]
                    rec["status"] = "done"
                    rec["at"] = utc_now()
                print(
                    console_safe(f"  main {rel} → {rec.get('main') or UNMAPPED_ID}"),
                    flush=True,
                )
            except OPERATOR_STOP:
                raise
            except Exception as exc:
                note_file_failure(cfg, None, None, stage="spike-main", exc=exc, rel_path=rel)
                rec["main"] = ""
                rec["summary"] = f"{type(exc).__name__}: {exc}"
                rec["status"] = "done"
                rec["at"] = utc_now()
            save_spike_state(cfg, by_path)
    finally:
        progress.finish(len(pending))
        save_spike_state(cfg, by_path)


def _combine_mains(cfg: dict, records: list[dict]) -> None:
    mains = counts_for(records, "main")
    ids = [name for name, _n in mains]
    print(f"SPIKE combine-mains: {len(ids)} unique mains", flush=True)
    raw = _ask(
        cfg,
        [
            {"role": "system", "content": MAIN_SYSTEM},
            {"role": "user", "content": mains_user_prompt(len(records), mains)},
        ],
        step="spike-combine-mains",
    )
    groups = coerce_groups(raw, ids, leave_one=False)
    mapping = apply_groups(ids, groups)
    changed = apply_field_map(records, "main", mapping)
    print(f"  groups {len(groups)}, files remapped {changed}", flush=True)
    for merge, into in groups:
        print(console_safe(f"  merge {list(merge)} → {into}"), flush=True)


def _tag_children(
    cfg: dict,
    by_path: dict[str, dict],
    records: list[dict],
    *,
    field: str,
    force: bool,
) -> None:
    """Sub: one cabinet at a time. Detail: one drawer at a time."""
    if field == "sub":
        cabinets = [(kebab(r.get("main")), None) for r in records if kebab(r.get("main"))]
        keys = list(dict.fromkeys(cabinets))
    else:
        keys = list(
            dict.fromkeys(
                (kebab(r.get("main")), kebab(r.get("sub")))
                for r in records
                if kebab(r.get("main"))
            )
        )

    pending_rels: list[str] = []
    for main, sub in keys:
        for rec in records:
            if kebab(rec.get("main")) != main:
                continue
            if field == "detail" and kebab(rec.get("sub")) != (sub or ""):
                continue
            if rec.get(field) and rec.get("status") == "done" and not force:
                continue
            pending_rels.append(str(rec["rel_path"]))
    pending_rels = list(dict.fromkeys(pending_rels))
    stage = f"spike-{field}"
    progress = Progress(cfg, stage, len(pending_rels))
    done = 0
    try:
        for main, sub in keys:
            parent = main if field == "sub" else f"{main}/{sub or '(none)'}"
            print(console_safe(f"SPIKE {field}: cabinet {parent}"), flush=True)
            for rec in records:
                if kebab(rec.get("main")) != main:
                    continue
                if field == "detail" and kebab(rec.get("sub")) != (sub or ""):
                    continue
                rel = str(rec.get("rel_path") or "")
                if rec.get(field) and rec.get("status") == "done" and not force:
                    continue
                done += 1
                progress.tick(done, rel)
                try:
                    live = list(by_path.values())
                    if field == "sub":
                        existing = existing_children(live, main=main)
                    else:
                        existing = existing_children(live, main=main, sub=sub or "")
                    text = (_doc_text(cfg, rel) or "")[:SPIKE_DOC_CAP]
                    if not text:
                        rec[field] = ""
                        rec["summary"] = rec.get("summary") or "extract missing"
                    else:
                        raw = _ask(
                            cfg,
                            [
                                {"role": "system", "content": CHILD_TAG_SYSTEM},
                                {
                                    "role": "user",
                                    "content": child_user_prompt(
                                        parent=parent,
                                        rel_path=rel,
                                        text=text,
                                        existing=existing,
                                    ),
                                },
                            ],
                            step=f"{stage}:{rel}",
                        )
                        name = coerce_open_id(raw.get("name") or raw.get(field))
                        if name == kebab(parent.split("/")[-1]):
                            name = ""
                        rec[field] = name
                        if raw.get("summary"):
                            rec["summary"] = str(raw.get("summary"))[:500]
                    rec["status"] = "done"
                    rec["at"] = utc_now()
                    print(
                        console_safe(f"  {field} {rel} → {parent}/{rec.get(field) or ''}"),
                        flush=True,
                    )
                except OPERATOR_STOP:
                    raise
                except Exception as exc:
                    note_file_failure(cfg, None, None, stage=stage, exc=exc, rel_path=rel)
                    rec[field] = ""
                    rec["status"] = "done"
                    rec["at"] = utc_now()
                save_spike_state(cfg, by_path)
    finally:
        progress.finish(len(pending_rels))
        save_spike_state(cfg, by_path)


def _combine_subs(cfg: dict, records: list[dict]) -> None:
    mains = [name for name, _n in counts_for(records, "main")]
    for main in mains:
        subs = counts_for(records, "sub", main=main)
        ids = [name for name, _n in subs]
        if len(ids) < 2:
            continue
        n_files = sum(n for _name, n in subs)
        print(f"SPIKE combine-subs: {main} ({len(ids)} drawers)", flush=True)
        raw = _ask(
            cfg,
            [
                {"role": "system", "content": SUB_SYSTEM},
                {"role": "user", "content": subs_user_prompt(main, n_files, subs)},
            ],
            step=f"spike-combine-subs:{main}",
        )
        groups = coerce_groups(raw, ids, leave_one=True)
        mapping = apply_groups(ids, groups)
        changed = apply_field_map(records, "sub", mapping, main=main)
        print(f"  groups {len(groups)}, files remapped {changed}", flush=True)
        for merge, into in groups:
            print(console_safe(f"  {main}: {list(merge)} → {into}"), flush=True)


def _combine_details(cfg: dict, records: list[dict]) -> None:
    drawers = list(
        dict.fromkeys(
            (kebab(r.get("main")), kebab(r.get("sub")))
            for r in records
            if kebab(r.get("main")) and kebab(r.get("sub"))
        )
    )
    for main, sub in drawers:
        details = existing_children(records, main=main, sub=sub)
        ids = [name for name, _n in details]
        if len(ids) < 2:
            continue
        n_files = sum(n for _nme, n in details)
        print(f"SPIKE combine-details: {main}/{sub} ({len(ids)})", flush=True)
        raw = _ask(
            cfg,
            [
                {"role": "system", "content": SUB_SYSTEM},
                {"role": "user", "content": details_user_prompt(main, sub, n_files, details)},
            ],
            step=f"spike-combine-details:{main}/{sub}",
        )
        groups = coerce_groups(raw, ids, leave_one=True)
        mapping = apply_groups(ids, groups)
        changed = apply_field_map(records, "detail", mapping, main=main, sub=sub)
        print(f"  groups {len(groups)}, files remapped {changed}", flush=True)


def run_spike(
    cfg: dict,
    *,
    limit: int | None = None,
    force: bool = False,
    until: str | None = None,
) -> list[dict]:
    """Run stages in order. ``until`` stops after that stage (inclusive)."""
    from burling.stitch_tags import load_tag_records

    assert_cloud_allowed(cfg)
    until = (until or "combine-details").strip()
    if until not in ALL_STAGES:
        raise RuntimeError(f"Unknown spike stage {until!r}. Choose one of: {', '.join(ALL_STAGES)}")
    stop_at = ALL_STAGES.index(until)

    out = output_dir(cfg)
    out.mkdir(parents=True, exist_ok=True)
    tags_path = Path(cfg.get("paths", {}).get("tags_json") or (out / "tags.json"))
    source = load_tag_records(cfg, tags_path if tags_path.is_file() else None)
    if not source:
        raise RuntimeError(f"No document list at {tags_path} (need tags.json for the file list).")
    if limit is not None:
        source = source[: max(0, limit)]

    by_path = {} if force else load_spike_state(cfg)
    for rec in source:
        rel = str(rec.get("rel_path") or "")
        if rel and rel not in by_path:
            by_path[rel] = _blank_rec(rel)
    save_spike_state(cfg, by_path)

    rels = [str(r.get("rel_path") or "") for r in source if r.get("rel_path")]
    print(
        f"SPIKE: {len(rels)} files, model {(cfg.get('ollama') or {}).get('model')}, "
        f"until {until}",
        flush=True,
    )

    if stop_at >= 0:
        print("SPIKE stage main — tag every file, main only", flush=True)
        pending = [
            rel
            for rel in rels
            if force or not kebab(by_path[rel].get("main"))
        ]
        _tag_mains(cfg, by_path, pending, force=force)

    records = _records_list(by_path, source)
    if stop_at >= 1:
        print("SPIKE stage combine-mains — fold after all mains exist", flush=True)
        _combine_mains(cfg, records)
        save_spike_state(cfg, by_path)

    if stop_at >= 2:
        print("SPIKE stage sub — one main at a time, reuse drawers", flush=True)
        _tag_children(cfg, by_path, records, field="sub", force=force)
        records = _records_list(by_path, source)

    if stop_at >= 3:
        print("SPIKE stage combine-subs — review each cabinet", flush=True)
        _combine_subs(cfg, records)
        save_spike_state(cfg, by_path)

    if stop_at >= 4:
        print("SPIKE stage detail — one drawer at a time", flush=True)
        _tag_children(cfg, by_path, records, field="detail", force=force)
        records = _records_list(by_path, source)

    if stop_at >= 5:
        print("SPIKE stage combine-details — review same process", flush=True)
        _combine_details(cfg, records)
        save_spike_state(cfg, by_path)

    records = _records_list(by_path, source)
    mains = counts_for(records, "main")
    print(
        f"SPIKE done until {until}: {len(records)} files, {len(mains)} mains → {out / 'spike-tags.json'}",
        flush=True,
    )
    return records
