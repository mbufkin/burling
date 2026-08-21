"""Census organize: mains first (counts only), then one sub dive.

Tagging already happened (``--layers``). The mains call does **not** see
files, subs, or summaries — showing those made the 30B greedy (hockey
folded on a main call). Same lesson as ``rollup_user_prompt``.

1. Fold MAIN ids toward about 12 browse roots. Inventory only.
2. Dive into one fat main and fold its SUB ids. Inventory only.

If a name is ambiguous, leave it unmerged. There are no filenames in
these windows, so the model cannot peek a body on this pass.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from burling.file_plan import is_banned_head
from burling.io_util import atomic_write, atomic_write_json
from burling.layer_plan import (
    _VAGUE_PARENT,
    _doc_text,
    kebab,
)
from burling.ollama_client import chat
from burling.paths import output_dir
from burling.progress import console_safe
from burling.trace import utc_now

TARGET_ROOTS = 12
MAX_PEEK_FILES = 8
PEEK_CHARS = 6_000
SUMMARY_CHARS = 160

MAIN_SYSTEM = """You are building a browse map a stranger can walk.
You will see MAIN ids and file counts only. You will not see files,
sub tags, or summaries. Fold those mains toward about 12 browse roots.

Output ONLY a valid JSON object:
{
  "reasoning": "astronomy, space, and spaceflight are the same kind of thing.",
  "groups": [
    {"merge": ["existing-main", "existing-main"], "into": "kebab-id"}
  ]
}

Rules:
- merge ids MUST be copied from the MAINS list. Do not invent an id.
- into is the broader root. It may be new or one of the merged mains.
- Aim for about 12 roots. Do not dump leftovers into misc / other / general.
- Do not mention files, subs, or hockey-style child names. You cannot see them.
- If two mains might belong together but you cannot tell from the names
  and counts, do not merge them.
- Year, email, and usenet names are not roots.
"""

SUB_SYSTEM = """You are a records clerk looking at ONE parent folder.
A stranger has to walk these drawers. You will see SUB ids and file
counts only.

THE PROBLEM
Tagging minted too many drawers. Some ids are the same kind of thing
written twice (singular vs plural, spelling, hyphenation, obvious
synonyms). Some ids are different kinds of thing and must stay apart.
Returning one tiny group and leaving a 90-drawer bush is a failure.

YOUR JOB
Fold every set of ids that are the same kind of thing. Stop when the
ids that remain are different kinds of thing (cars vs crypto, printers
vs operating systems). Do not rename the parent.

Output ONLY a valid JSON object:
{
  "reasoning": "1. window/windows are the same drawer (singular/plural). 2. color/colour are spelling variants. 3. cars vs encryption are unlike — do not mix.",
  "groups": [
    {"merge": ["existing-sub", "existing-sub"], "into": "kebab-id"}
  ]
}

MUST:
- merge ids MUST be copied from the SUBS list, character for character.
- Singular/plural, spelling variants, and hyphenation variants ARE the
  same kind of thing. They must share a group.
- into is the broader drawer. It may be new or one of the merged ids.
- Leave unlike drawers unmerged. Leave at least one sub out of the
  groups (merging everyone is a rename of the parent).

NOT ALLOWED:
- groups: [] when any two ids are the same kind of thing.
- One cosmetic group while obvious variants remain on the list.
- Mixing unlike kinds in one group.
- into = the parent name, or misc / other / general / hardware /
  computing / tech / discussion.
- Inventing a merge id that is not on the SUBS list.
- Year, email, and usenet names as drawers.
"""


def load_census_records(cfg: dict) -> list[dict]:
    """Reuse the already-tagged 400. Do not re-tag."""
    raw = (cfg.get("paths") or {}).get("layer_tags_json")
    path = Path(raw) if raw else (output_dir(cfg) / "layer-tags.json")
    if not path.is_file():
        raise RuntimeError(f"No layer-tags.json at {path} (run --layers first).")
    data = json.loads(path.read_text(encoding="utf-8"))
    docs = [r for r in (data.get("documents") or []) if isinstance(r, dict) and r.get("rel_path")]
    if not docs:
        raise RuntimeError(f"layer-tags.json at {path} has no documents.")
    return docs


def roster_lines(records: list[dict], *, main: str | None = None) -> list[str]:
    """Filename + tags + the existing one-line summary. Not the file body."""
    lines: list[str] = []
    for rec in records:
        rec_main = kebab(rec.get("main"))
        if main is not None and rec_main != main:
            continue
        rel = str(rec.get("rel_path") or "")
        sub = kebab(rec.get("sub"))
        detail = kebab(rec.get("detail"))
        path = "/".join(p for p in (rec_main, sub, detail) if p) or "(untagged)"
        summary = " ".join(str(rec.get("summary") or "").split())[:SUMMARY_CHARS]
        extra = f"  |  {summary}" if summary else ""
        lines.append(f"{rel}  {path}{extra}")
    return lines


def counts_for(records: list[dict], field: str, *, main: str | None = None) -> list[tuple[str, int]]:
    tallies: Counter[str] = Counter()
    for rec in records:
        rec_main = kebab(rec.get("main"))
        if main is not None and rec_main != main:
            continue
        name = kebab(rec.get(field))
        if name:
            tallies[name] += 1
    return tallies.most_common()


def effective_main(rec: dict, main_map: dict[str, str]) -> str:
    """Main after the fold. astronomy → science if that group was accepted."""
    orig = kebab(rec.get("main"))
    return kebab(main_map.get(orig) or orig)


def counts_under_root(
    records: list[dict],
    main_map: dict[str, str],
    root: str,
    *,
    field: str = "sub",
) -> list[tuple[str, int]]:
    """Sub (or detail) counts for every file whose *mapped* main is root.

    Best practice: after astronomy + spaceflight fold into science, stars
    and shuttle sit in the same inventory. The model sees ids and counts
    only — not which original main they came from.
    """
    root = kebab(root)
    tallies: Counter[str] = Counter()
    for rec in records:
        if effective_main(rec, main_map) != root:
            continue
        name = kebab(rec.get(field))
        if name:
            tallies[name] += 1
    return tallies.most_common()


def sources_of_root(main_map: dict[str, str], root: str) -> list[str]:
    """Original mains that now live under this root."""
    root = kebab(root)
    return sorted(orig for orig, dest in main_map.items() if kebab(dest) == root)


def pick_dive_root(
    main_map: dict[str, str],
    records: list[dict],
    *,
    named: str | None = None,
) -> str:
    """Prefer a root that actually absorbed sibling mains (the science case).

    Fat original hardware is a bush we already sampled. The open question
    is whether astronomy's children and spaceflight's children should
    combine now that they share a parent.
    """
    if named:
        # Follow the fold: hardware may now live under tech.
        key = kebab(named)
        return kebab(main_map.get(key) or key)
    sources: dict[str, set[str]] = defaultdict(set)
    for orig, dest in main_map.items():
        sources[kebab(dest)].add(kebab(orig))
    files: Counter[str] = Counter(effective_main(r, main_map) for r in records)
    merged = [(root, srcs) for root, srcs in sources.items() if len(srcs) >= 2]
    merged.sort(key=lambda item: (-len(item[1]), files[item[0]], item[0]))
    if merged:
        return merged[0][0]
    return files.most_common(1)[0][0] if files else ""


def _valid_head(name: str) -> bool:
    if not name:
        return False
    if is_banned_head(name, name):
        return False
    if _VAGUE_PARENT.match(name):
        return False
    return True


def coerce_groups(
    raw: object,
    allowed: list[str],
    *,
    leave_one: bool,
) -> list[tuple[tuple[str, ...], str]]:
    """Keep a group only when merge ids exist on the list.

    Best practice: the model proposes; code is the records office. Vague
    into names and (when leave_one) merging everyone die here.
    """
    allowed_set = {kebab(s) for s in allowed if kebab(s)}
    obj = raw if isinstance(raw, dict) else {}
    groups = obj.get("groups")
    if not isinstance(groups, list):
        groups = [obj] if obj.get("merge") or obj.get("into") else []

    out: list[tuple[tuple[str, ...], str]] = []
    claimed: set[str] = set()
    for group in groups:
        if not isinstance(group, dict):
            continue
        into = kebab(group.get("into") or group.get("name"))
        merge = [kebab(c) for c in (group.get("merge") or []) if kebab(c) in allowed_set]
        if into in allowed_set and into not in merge:
            merge.append(into)
        merge = [m for m in dict.fromkeys(merge) if m not in claimed]
        leftover = allowed_set - claimed - set(merge)
        if len(merge) < 2 or not _valid_head(into):
            continue
        if leave_one and not leftover:
            continue
        claimed.update(merge)
        out.append((tuple(merge), into))
    return out


def coerce_need_files(raw: object, known: list[str], *, limit: int = MAX_PEEK_FILES) -> list[str]:
    """Filenames the model asked to read. Unknown paths are dropped."""
    obj = raw if isinstance(raw, dict) else {}
    wanted = obj.get("need_files") or obj.get("peek") or []
    if isinstance(wanted, str):
        wanted = [wanted]
    known_set = set(known)
    out: list[str] = []
    for name in wanted:
        rel = str(name or "").strip().lstrip("./")
        if rel in known_set and rel not in out:
            out.append(rel)
        if len(out) >= limit:
            break
    return out


def apply_groups(ids: list[str], groups: list[tuple[tuple[str, ...], str]]) -> dict[str, str]:
    """Map each id to itself or to the into it was merged under."""
    mapping = {i: i for i in ids}
    for merge, into in groups:
        for name in merge:
            if name in mapping:
                mapping[name] = into
    return mapping


def _ask(cfg: dict, messages: list[dict], step: str) -> dict:
    try:
        raw = chat(cfg, messages, step=step)
        return raw if isinstance(raw, dict) else {}
    except Exception as exc:
        print(f"  census {step} failed: {exc}", flush=True)
        return {}


def _inventory_block(label: str, pairs: list[tuple[str, int]]) -> str:
    lines = [f"{label} (id: files):"]
    for name, n in pairs:
        lines.append(f"- {name}: {n}")
    return "\n".join(lines)


def mains_user_prompt(n_docs: int, mains: list[tuple[str, int]]) -> str:
    """Mains and counts only.

    Best practice: do not attach the file roster here. Showing subs made
    the 30B merge hockey on a call that was only allowed to copy mains.
    """
    return (
        f"CORPUS: {n_docs} documents, {len(mains)} unique mains. "
        f"Fold mains toward about {TARGET_ROOTS} browse roots.\n\n"
        + _inventory_block("MAINS", mains)
    )


def subs_user_prompt(parent: str, n_files: int, subs: list[tuple[str, int]]) -> str:
    """Sub ids and counts only. Spell out the bush so the 30B cannot coast."""
    n = len(subs)
    return (
        f"PARENT: {parent}. {n_files} files, {n} unique subs.\n"
        f"A stranger cannot walk {n} drawers. Fold same-kind ids "
        f"(including singular/plural and spelling variants). Leave unlike "
        f"kinds apart. Do not dump the leftover into {parent} or misc.\n\n"
        + _inventory_block("SUBS", subs)
    )


def _roster_block(lines: list[str]) -> str:
    return "ROSTER (filename  main/sub/detail  |  summary):\n" + "\n".join(lines)


def _peek_block(cfg: dict, rels: list[str]) -> str:
    """Extracted text for files the model said it could not judge from tags."""
    chunks = [
        f"FILE PEEKS ({len(rels)}). Use these only for the ids you were unsure about."
    ]
    for rel in rels:
        text = _doc_text(cfg, rel)[:PEEK_CHARS]
        chunks.append(f"--- FILE: {rel} ---\n{text or '(extract missing)'}")
    return "\n\n".join(chunks)


def _ask_with_peek(
    cfg: dict,
    *,
    system: str,
    user: str,
    step: str,
    known_files: list[str],
) -> dict:
    """One set task. If the model names files, peek once and ask again."""
    raw = _ask(
        cfg,
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        step=step,
    )
    need = coerce_need_files(raw, known_files)
    if not need:
        return {"raw": raw, "peeked": [], "retried": False}
    print(
        console_safe(f"  census {step}: peeking {len(need)} file(s)"),
        flush=True,
    )
    retry_user = user + "\n\n" + _peek_block(cfg, need)
    retried = _ask(
        cfg,
        [{"role": "system", "content": system}, {"role": "user", "content": retry_user}],
        step=f"{step}-peek",
    )
    return {"raw": retried or raw, "peeked": need, "retried": True, "first": raw}


def run_census(
    cfg: dict,
    *,
    dive_main: str | None = None,
) -> dict:
    """Two model calls on the already-tagged 400. Writes a new output folder."""
    records = load_census_records(cfg)
    out = output_dir(cfg)
    out.mkdir(parents=True, exist_ok=True)
    mains = counts_for(records, "main")
    main_ids = [name for name, _n in mains]
    main_user = mains_user_prompt(len(records), mains)

    print(
        f"CENSUS: {len(records)} files, {len(main_ids)} mains, "
        f"mains-only window {len(main_user)} chars, target ~{TARGET_ROOTS} roots",
        flush=True,
    )

    print("CENSUS: asking mains (ids and counts only, no roster)...", flush=True)
    main_raw = _ask(
        cfg,
        [{"role": "system", "content": MAIN_SYSTEM}, {"role": "user", "content": main_user}],
        step="census-mains",
    )
    main_call = {"raw": main_raw, "peeked": [], "retried": False}
    main_groups = coerce_groups(main_call["raw"], main_ids, leave_one=False)
    main_map = apply_groups(main_ids, main_groups)
    roots = sorted(set(main_map.values()))
    print(
        console_safe(
            f"CENSUS mains: {len(main_ids)} → {len(roots)} roots, "
            f"{len(main_groups)} groups, peeked {len(main_call.get('peeked') or [])}"
        ),
        flush=True,
    )

    # Dive one *mapped* root. astronomy's stars and spaceflight's shuttle
    # are now siblings; this call asks whether any of those drawers combine.
    chosen = pick_dive_root(main_map, records, named=dive_main)
    absorbed = sources_of_root(main_map, chosen)
    sub_pairs = counts_under_root(records, main_map, chosen, field="sub")
    sub_ids = [name for name, _n in sub_pairs]
    sub_n = sum(1 for r in records if effective_main(r, main_map) == chosen)
    print(
        console_safe(
            f"CENSUS: dive {chosen} (absorbed {', '.join(absorbed) or chosen})"
        ),
        flush=True,
    )
    sub_call: dict = {"raw": {}, "peeked": [], "retried": False}
    sub_groups: list[tuple[tuple[str, ...], str]] = []
    sub_map: dict[str, str] = {}
    if sub_ids:
        print(
            f"CENSUS: asking subs inside {chosen} "
            f"({sub_n} tagged files, {len(sub_ids)} subs, inventory only)...",
            flush=True,
        )
        sub_user = subs_user_prompt(chosen, sub_n, sub_pairs)
        sub_raw = _ask(
            cfg,
            [{"role": "system", "content": SUB_SYSTEM}, {"role": "user", "content": sub_user}],
            step=f"census-subs:{chosen}",
        )
        sub_call = {"raw": sub_raw, "peeked": [], "retried": False}
        sub_groups = coerce_groups(sub_call["raw"], sub_ids, leave_one=True)
        sub_map = apply_groups(sub_ids, sub_groups)
        print(
            console_safe(
                f"CENSUS subs/{chosen}: {len(sub_ids)} → {len(set(sub_map.values()) or sub_ids)} "
                f"heads, {len(sub_groups)} groups, peeked {len(sub_call.get('peeked') or [])}"
            ),
            flush=True,
        )
    else:
        print(f"CENSUS: {chosen} has no sub tags — skipping sub call", flush=True)

    payload = {
        "meta": {
            "method": "census-organize",
            "documents": len(records),
            "mains_before": len(main_ids),
            "mains_after": len(roots),
            "target_roots": TARGET_ROOTS,
            "dive_main": chosen,
            "dive_absorbed": absorbed,
            "subs_before": len(sub_ids),
            "subs_after": len(set(sub_map.values())) if sub_map else len(sub_ids),
            "built_at": utc_now(),
        },
        "mains": {
            "inventory": [{"id": n, "count": c} for n, c in mains],
            "groups": [{"merge": list(m), "into": into} for m, into in main_groups],
            "mapping": main_map,
            "peeked": main_call.get("peeked") or [],
            "raw": main_call.get("raw") or {},
            "first_raw": main_call.get("first"),
        },
        "subs": {
            "parent": chosen,
            "absorbed_mains": absorbed,
            "inventory": [{"id": n, "count": c} for n, c in sub_pairs],
            "groups": [{"merge": list(m), "into": into} for m, into in sub_groups],
            "mapping": sub_map,
            "peeked": sub_call.get("peeked") or [],
            "raw": sub_call.get("raw") or {},
            "first_raw": sub_call.get("first"),
        },
    }
    atomic_write_json(out / "census.json", payload)
    atomic_write(out / "CENSUS.md", _report(payload))
    print(f"CENSUS done → {out / 'CENSUS.md'}", flush=True)
    return payload["meta"]


def _report(payload: dict) -> str:
    meta = payload["meta"]
    mains = payload["mains"]
    subs = payload["subs"]
    lines = [
        "# Census organize (one window, then one dive)",
        "",
        "Tagged files were already on disk. The mains call saw **ids and",
        "counts only** — no file roster, no sub tags — so it cannot merge",
        f"hockey on a main job. Target about {meta['target_roots']} roots,",
        f"then fold subs under `{subs['parent']}` the same way (ids and counts).",
        "No file bodies on this pass.",
        "",
        f"- Documents: {meta['documents']}",
        f"- Mains: {meta['mains_before']} → {meta['mains_after']} (target ~{meta['target_roots']})",
        f"- Dive: `{subs['parent']}` (absorbed {', '.join(subs.get('absorbed_mains') or [subs['parent']])})",
        f"- Subs: {meta['subs_before']} → {meta['subs_after']}",
        f"- Peeked on mains: {', '.join(mains['peeked']) or '(none)'}",
        f"- Peeked on subs: {', '.join(subs['peeked']) or '(none)'}",
        "",
        "## Main groups (coerced)",
        "",
    ]
    if not mains["groups"]:
        lines.append("(none accepted)")
    for g in mains["groups"]:
        lines.append(f"- {', '.join(g['merge'])} → **{g['into']}**")
    lines += ["", "## Sub groups (coerced)", ""]
    if not subs["groups"]:
        lines.append("(none accepted)")
    for g in subs["groups"]:
        lines.append(f"- {', '.join(g['merge'])} → **{g['into']}**")
    lines += [
        "",
        "## Model reasoning (mains)",
        "",
        str((mains.get("raw") or {}).get("reasoning") or "(none)"),
        "",
        "## Model reasoning (subs)",
        "",
        str((subs.get("raw") or {}).get("reasoning") or "(none)"),
        "",
    ]
    return "\n".join(lines) + "\n"
