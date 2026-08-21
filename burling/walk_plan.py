"""Tree-walk clerk: locked main, then reuse / invent at each child.

The 30B never writes the tree. It answers one set task at a time:

1. Which approved series does this file belong in?
2. Given the children already in that folder — reuse one, invent the
   first, or stay (empty)?
3. Same question one level down (detail).

Combine is a *later* call (``maintain_plan``), after this letter is
home. Filing does not rewrite the tree. Unmapped only when the body has
no substance, and then a reason is required. Spec:
``docs/file-plan-layers.md``.

Everyday organize is this module (``--walk``), not ``--ralp``.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from burling.file_plan import UNMAPPED_ID, ensure_unmapped, is_banned_head
from burling.isolate import OPERATOR_STOP, note_file_failure
from burling.io_util import atomic_write_json
from burling.layer_plan import (
    LAYER_DOC_CAP,
    MAX_BROWSE_DEPTH,
    WORKPLACE_MAINS,
    _VAGUE_PARENT,
    _doc_text,
    coerce_main,
    human_label,
    kebab,
    node_id,
)
from burling.ollama_client import chat
from burling.paths import output_dir
from burling.progress import Progress, console_safe
from burling.trace import utc_now

# Closed series stay roots. A child named "unmapped" was the workplace-run smell.
_RESERVED_CHILD = frozenset(WORKPLACE_MAINS) | {UNMAPPED_ID}

MAIN_SYSTEM = """You are a records clerk. One employee has left. Pick the ONE
approved workplace series this document belongs in.

Output ONLY a valid JSON object:
{
  "reasoning": "The work function is X.",
  "main": "approved-id",
  "reason": ""
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
- unmapped: no topical substance (unsubscribe, test post, empty, "me too")

Rules:
- main is one approved id. Do not invent a 14th series.
- unmapped only when the text has no subject. Then reason must say what is missing.
- If the text has a subject but it is not work, main is personal, not unmapped.
- Hardware and physical gear are facilities. Software and protocols are technology.
- Year, email address, newsgroup, and filename are never a series.
"""

CHILD_SYSTEM = """You are walking one folder on a workplace file plan.
Decide the NEXT folder for THIS document only. Look at the children that
already exist. Do not rename the parent. Do not merge other files.

Output ONLY a valid JSON object:
{
  "reasoning": "1. Existing children are A, B. 2. This file belongs with X.",
  "action": "reuse" | "invent" | "empty",
  "name": "kebab-id"
}

Actions:
- reuse: name MUST be copied from the EXISTING CHILDREN list.
- invent: name a new child. Use when the folder is empty, or when no
  existing child fits.
- empty: stay in the current folder. Only when the text has no narrower
  category.

Rules:
- Prefer reuse over invent when an existing child already fits.
- Do not invent a near-duplicate of an existing child; reuse the closest name.
- Year, email, usenet, unmapped, and the approved mains are not child names.
- Hardware may be a child of facilities or technology. It is never a main.
"""

Chooser = Callable[..., dict]


@dataclass(frozen=True)
class ChildChoice:
    """One step down the tree. Code accepts or rejects what the model proposed."""

    action: str  # reuse | invent | empty  (combine is a later maintain call)
    name: str
    merge: tuple[str, ...] = ()


@dataclass
class WalkState:
    """Live browse tree. Homes are the source of truth; children are derived.

    Best practice: one home per file, always. Filing places this letter.
    Maintain (later) may rehome siblings so the tree a later file sees
    is the tree a stranger would walk.
    """

    homes: dict[str, list[str]] = field(default_factory=dict)
    facets: dict[str, str] = field(default_factory=dict)
    records: dict[str, dict] = field(default_factory=dict)
    combines: list[dict] = field(default_factory=list)

    def children(self, prefix: list[str]) -> list[tuple[str, int]]:
        """Immediate child ids under prefix, fattest first, with file counts."""
        counts: Counter[str] = Counter()
        depth = len(prefix)
        for home in self.homes.values():
            if len(home) > depth and home[:depth] == prefix:
                child = home[depth]
                if child and child != UNMAPPED_ID:
                    counts[child] += 1
        return counts.most_common()

    def rehome(self, prefix: list[str], merge: list[str], into: str) -> int:
        """Move files under prefix+old into prefix+into.

        Old sibling names nest as the next layer when depth allows
        (technology/windows → technology/operating-systems/windows).
        At depth 3 the old name becomes a facet, never a fourth folder.
        """
        into = kebab(into)
        merge_set = {kebab(m) for m in merge if kebab(m)}
        if not into or len(merge_set) < 2:
            return 0
        moved = 0
        for rel, home in list(self.homes.items()):
            if len(home) <= len(prefix) or home[: len(prefix)] != prefix:
                continue
            old = home[len(prefix)]
            if old not in merge_set:
                continue
            rest = home[len(prefix) + 1 :]
            new = list(prefix) + [into]
            if old != into and len(new) < MAX_BROWSE_DEPTH:
                new.append(old)
            elif old != into:
                self.facets[rel] = old
            if rest:
                leftover = rest[0]
                if len(new) < MAX_BROWSE_DEPTH and leftover not in new:
                    new.append(leftover)
                else:
                    self.facets[rel] = leftover
            self.homes[rel] = new[:MAX_BROWSE_DEPTH]
            rec = self.records.get(rel) or {}
            rec["main"] = self.homes[rel][0] if self.homes[rel] else ""
            rec["sub"] = self.homes[rel][1] if len(self.homes[rel]) > 1 else ""
            rec["detail"] = self.homes[rel][2] if len(self.homes[rel]) > 2 else ""
            rec["facet"] = self.facets.get(rel) or rec.get("facet") or ""
            self.records[rel] = rec
            moved += 1
        if moved:
            self.combines.append(
                {
                    "at": utc_now(),
                    "prefix": list(prefix),
                    "merge": sorted(merge_set),
                    "into": into,
                    "moved": moved,
                }
            )
        return moved

    def place(
        self,
        rel_path: str,
        *,
        main: str,
        sub: ChildChoice,
        detail: ChildChoice,
        summary: str = "",
        reason: str = "",
    ) -> list[str]:
        """File this document only. Siblings stay put.

        Best practice: combining drawers is a later set task
        (maintain_plan). Filing must not rewrite the tree.
        """
        if not main:
            home = [UNMAPPED_ID]
            self.homes[rel_path] = home
            self.records[rel_path] = {
                "rel_path": rel_path,
                "main": "",
                "sub": "",
                "detail": "",
                "summary": summary,
                "reason": reason or "no topical substance",
                "status": "done",
                "at": utc_now(),
            }
            return home

        path = [main]
        if sub.action != "empty" and sub.name:
            path.append(sub.name)

        if detail.action != "empty" and detail.name and len(path) < MAX_BROWSE_DEPTH:
            if detail.name != path[-1]:
                path.append(detail.name)

        home = path[:MAX_BROWSE_DEPTH]
        self.homes[rel_path] = home
        self.records[rel_path] = {
            "rel_path": rel_path,
            "main": home[0] if home else "",
            "sub": home[1] if len(home) > 1 else "",
            "detail": home[2] if len(home) > 2 else "",
            "facet": self.facets.get(rel_path) or "",
            "summary": summary,
            "reason": reason,
            "status": "done",
            "at": utc_now(),
        }
        return home


def _valid_child(name: str) -> bool:
    """Reserved words and channel/year never become a drawer."""
    if not name or name in _RESERVED_CHILD:
        return False
    if is_banned_head(name, name):
        return False
    if _VAGUE_PARENT.match(name):
        return False
    return True


def coerce_main_choice(raw: object, *, text: str) -> tuple[str, str]:
    """Approved series, or unmapped-with-reason. Never a 14th type.

    Returns (main, reason). Empty main means unmapped. ``invalid`` mains
    with real text stay empty so the runner can retry — they do not
    become leftovers just because the model named cryptography.
    """
    if not (text or "").strip():
        return "", "extract missing"
    obj = raw if isinstance(raw, dict) else {}
    main = kebab(obj.get("main"))
    reason = str(obj.get("reason") or obj.get("unmapped_reason") or "").strip()[:400]
    if main == UNMAPPED_ID:
        # unmapped is honest only when the body has no subject.
        if _looks_empty(text, reason):
            return "", reason or "no topical substance"
        return "", ""  # retry: model used the leftover bin as "doesn't fit"
    approved = coerce_main(main)
    if approved:
        return approved, reason
    return "", ""


def _looks_empty(text: str, reason: str) -> bool:
    body = " ".join((text or "").strip().split())
    if len(body) < 40:
        return True
    blob = f"{reason} {body}".lower()
    return any(
        tok in blob
        for tok in ("unsubscribe", "unmapped", "no substance", "test post", "me too", "ignore")
    )


def coerce_child_choice(
    raw: object,
    siblings: list[str],
    *,
    allow_empty: bool,
) -> ChildChoice:
    """Model proposes; code is the records office.

    Best practice: infer action from the ids when the model forgets the
    verb. A combine with fewer than two *existing* siblings is dropped.
    """
    obj = raw if isinstance(raw, dict) else {}
    sibling_set = {kebab(s) for s in siblings if kebab(s)}
    name = kebab(obj.get("name") or obj.get("use") or obj.get("into"))
    merge = [kebab(c) for c in (obj.get("merge") or []) if kebab(c) in sibling_set]
    into = kebab(obj.get("into") or name)
    action = str(obj.get("action") or "").strip().lower()
    if action not in {"reuse", "invent", "combine", "empty"}:
        if len(merge) >= 2:
            action = "combine"
        elif name in sibling_set:
            action = "reuse"
        elif name:
            action = "invent"
        else:
            action = "empty" if allow_empty else "invent"

    if action == "empty":
        return ChildChoice("empty", "", ()) if allow_empty else ChildChoice("empty", "", ())

    if action == "combine":
        if into in sibling_set and into not in merge:
            merge.append(into)
        if len(merge) >= 2 and _valid_child(into):
            return ChildChoice("combine", into, tuple(merge))
        if into in sibling_set:
            return ChildChoice("reuse", into, ())
        if _valid_child(into):
            return ChildChoice("invent", into, ())
        return ChildChoice("empty", "", ())

    if action == "reuse":
        if name in sibling_set:
            return ChildChoice("reuse", name, ())
        if _valid_child(name):
            return ChildChoice("invent", name, ())
        return ChildChoice("empty", "", ())

    # invent
    if name in sibling_set:
        return ChildChoice("reuse", name, ())
    if _valid_child(name):
        return ChildChoice("invent", name, ())
    return ChildChoice("empty", "", ())


def build_walk_regions(state: WalkState) -> dict:
    """Python tree from walked homes. One home per file. No collapse.

    Thin first-children stay. The walk created them on purpose — the
    first file in a series invents a sub even if it is the only one.
    """
    trie: dict = {}
    for home in state.homes.values():
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
    for rel, home in state.homes.items():
        rec = state.records.get(rel) or {}
        hid = node_id(home)
        top = node_id(home[:1]) if home else UNMAPPED_ID
        assignments.append(
            {
                "rel_path": rel,
                "region_ids": [hid],
                "top_level_regions": [top],
                "summary": rec.get("summary") or "",
                "facet": state.facets.get(rel) or rec.get("facet") or "",
                "layer_path": "/".join(home),
                "reason": rec.get("reason") or "",
            }
        )
    assignments.sort(key=lambda a: a["rel_path"])

    n_homes = [len(a["region_ids"]) for a in assignments]
    unmapped = sum(1 for a in assignments if a["region_ids"] == [UNMAPPED_ID])
    return {
        "meta": {
            "method": "walk-file-plan",
            "documents": len(assignments),
            "top_level": len([r for r in regions if r.get("id") != UNMAPPED_ID]),
            "nodes": _count_nodes(regions),
            "docs_mapped": len(assignments) - unmapped,
            "unmapped": unmapped,
            "homes_mean": round(sum(n_homes) / len(n_homes), 2) if n_homes else 0,
            "combines": len(state.combines),
            "max_browse_depth": MAX_BROWSE_DEPTH,
            "built_at": utc_now(),
        },
        "regions": regions,
        "assignments": assignments,
        "combines": list(state.combines),
    }


def _count_nodes(nodes: list) -> int:
    n = 0
    for node in nodes or []:
        if not isinstance(node, dict):
            continue
        n += 1
        n += _count_nodes(node.get("children") or [])
    return n


def _state_path(cfg: dict) -> Path:
    return output_dir(cfg) / "walk-state.json"


def load_walk_state(cfg: dict) -> WalkState:
    path = _state_path(cfg)
    if not path.is_file():
        return WalkState()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return WalkState()
    homes = {
        str(k): [kebab(s) for s in v if kebab(s)]
        for k, v in (data.get("homes") or {}).items()
    }
    return WalkState(
        homes=homes,
        facets={str(k): kebab(v) for k, v in (data.get("facets") or {}).items() if kebab(v)},
        records={str(k): v for k, v in (data.get("records") or {}).items() if isinstance(v, dict)},
        combines=list(data.get("combines") or []),
    )


def save_walk_state(cfg: dict, state: WalkState) -> None:
    atomic_write_json(
        _state_path(cfg),
        {
            "homes": state.homes,
            "facets": state.facets,
            "records": state.records,
            "combines": state.combines,
            "method": "walk-file-plan",
        },
    )


def _ask(cfg: dict, messages: list[dict], step: str) -> dict:
    """One fresh-window JSON call. Empty dict on failure so the clerk can retry."""
    try:
        raw = chat(cfg, messages, step=step)
        return raw if isinstance(raw, dict) else {}
    except Exception as exc:
        print(f"  walk {step} failed: {exc}", flush=True)
        return {}


def _child_user(rel_path: str, text: str, prefix: list[str], siblings: list[tuple[str, int]]) -> str:
    folder = "/".join(prefix) or "(root)"
    if siblings:
        lines = [f"- {name}: {n}" for name, n in siblings]
        existing = "EXISTING CHILDREN (name: files):\n" + "\n".join(lines)
    else:
        existing = "EXISTING CHILDREN: none. Invent the first child, or empty if none fits."
    return (
        f"FILE: {rel_path}\n"
        f"CURRENT FOLDER: {folder}\n\n"
        f"{existing}\n\n"
        f"DOCUMENT TEXT:\n{text[:LAYER_DOC_CAP]}"
    )


def choose_main_model(cfg: dict, *, rel_path: str, text: str) -> dict:
    user = f"FILE: {rel_path}\n\nDOCUMENT TEXT:\n{text[:LAYER_DOC_CAP]}"
    raw = _ask(
        cfg,
        [{"role": "system", "content": MAIN_SYSTEM}, {"role": "user", "content": user}],
        step=f"walk-main:{rel_path}",
    )
    main, reason = coerce_main_choice(raw, text=text)
    if main or (not main and reason):
        raw = dict(raw)
        raw["main"] = main or UNMAPPED_ID
        raw["reason"] = reason
        return raw
    # Retry once: unknown id or unmapped-as-doesn't-fit, but the body has a subject.
    retry_user = (
        user
        + "\n\nThat main is not on the approved list. Pick one approved id. "
        "unmapped only if the text has no subject."
    )
    raw = _ask(
        cfg,
        [{"role": "system", "content": MAIN_SYSTEM}, {"role": "user", "content": retry_user}],
        step=f"walk-main-retry:{rel_path}",
    )
    main, reason = coerce_main_choice(raw, text=text)
    if main or reason:
        raw = dict(raw) if isinstance(raw, dict) else {}
        raw["main"] = main or UNMAPPED_ID
        raw["reason"] = reason
        return raw
    # Last resort: the work itself. Do not mint a series. Do not dump to unmapped.
    return {
        "main": "operations",
        "reason": "fallback: model did not pick an approved series",
        "summary": str((raw or {}).get("summary") or ""),
        "reasoning": str((raw or {}).get("reasoning") or ""),
    }


def choose_child_model(
    cfg: dict,
    *,
    rel_path: str,
    text: str,
    prefix: list[str],
    siblings: list[tuple[str, int]],
) -> dict:
    user = _child_user(rel_path, text, prefix, siblings)
    return _ask(
        cfg,
        [{"role": "system", "content": CHILD_SYSTEM}, {"role": "user", "content": user}],
        step=f"walk-child:{'/'.join(prefix)}:{rel_path}",
    )


def walk_one(
    state: WalkState,
    *,
    rel_path: str,
    text: str,
    choose_main: Chooser,
    choose_child: Chooser,
) -> list[str]:
    """File one document against the live tree. Testable: inject the choosers."""
    if not (text or "").strip():
        return state.place(
            rel_path,
            main="",
            sub=ChildChoice("empty", ""),
            detail=ChildChoice("empty", ""),
            summary="",
            reason="extract missing",
        )
    raw_main = choose_main(rel_path=rel_path, text=text)
    main, reason = coerce_main_choice(raw_main, text=text)
    if not main and not reason:
        # Injected chooser already returned a fallback main.
        main = coerce_main((raw_main or {}).get("main")) if isinstance(raw_main, dict) else ""
        reason = str((raw_main or {}).get("reason") or "") if isinstance(raw_main, dict) else ""
    summary = str((raw_main or {}).get("summary") or (raw_main or {}).get("reasoning") or "")[:500]

    if not main:
        return state.place(
            rel_path, main="", sub=ChildChoice("empty", ""), detail=ChildChoice("empty", ""),
            summary=summary, reason=reason or "no topical substance",
        )

    sub_raw = choose_child(
        rel_path=rel_path,
        text=text,
        prefix=[main],
        siblings=state.children([main]),
    )
    sub = coerce_child_choice(sub_raw, [n for n, _c in state.children([main])], allow_empty=True)
    if sub.action == "combine" and sub.merge:
        state.rehome([main], list(sub.merge), sub.name)
        sub = ChildChoice("reuse", sub.name, ())

    path = [main]
    if sub.name:
        path.append(sub.name)

    detail = ChildChoice("empty", "")
    if len(path) >= 2:
        det_raw = choose_child(
            rel_path=rel_path,
            text=text,
            prefix=path,
            siblings=state.children(path),
        )
        detail = coerce_child_choice(
            det_raw, [n for n, _c in state.children(path)], allow_empty=True
        )
        if detail.action == "combine" and detail.merge:
            state.rehome(path, list(detail.merge), detail.name)
            detail = ChildChoice("reuse", detail.name, ())

    if not summary:
        summary = str((sub_raw or {}).get("reasoning") or "")[:500]
    return state.place(
        rel_path, main=main, sub=sub, detail=detail, summary=summary, reason=reason
    )


def run_walk_plan(
    cfg: dict,
    *,
    resume: bool = False,
    limit: int | None = None,
    force: bool = False,
    choose_main: Chooser | None = None,
    choose_child: Chooser | None = None,
) -> dict:
    """Walk every listed file. Writes a new output folder. Resume-safe."""
    from burling.ralp import persist_payload
    from burling.stitch_tags import load_tag_records

    out = output_dir(cfg)
    out.mkdir(parents=True, exist_ok=True)
    tags_path = Path(cfg.get("paths", {}).get("tags_json") or (out / "tags.json"))
    source = load_tag_records(cfg, tags_path if tags_path.is_file() else None)
    if not source:
        raise RuntimeError(f"No document list at {tags_path} (need tags.json for the file list).")

    state = WalkState() if force else load_walk_state(cfg)
    pending = [
        r
        for r in source
        if r.get("rel_path")
        and (force or state.records.get(r["rel_path"], {}).get("status") != "done")
    ]
    if limit is not None:
        pending = pending[: max(0, limit)]
    print(
        f"WALK: {len(state.homes)} already filed, {len(pending)} to walk",
        flush=True,
    )

    main_fn = choose_main or (lambda **kw: choose_main_model(cfg, **kw))
    child_fn = choose_child or (lambda **kw: choose_child_model(cfg, **kw))

    progress = Progress(cfg, "walk", len(pending))
    try:
        for i, rec in enumerate(pending, start=1):
            rel = str(rec.get("rel_path") or "")
            progress.tick(i, rel)
            try:
                text = _doc_text(cfg, rel)
                home = walk_one(
                    state,
                    rel_path=rel,
                    text=text,
                    choose_main=main_fn,
                    choose_child=child_fn,
                )
                print(
                    console_safe(f"  walk {rel} → {'/'.join(home)}"),
                    flush=True,
                )
            except OPERATOR_STOP:
                raise
            except Exception as exc:
                note_file_failure(cfg, None, None, stage="walk", exc=exc, rel_path=rel)
                state.place(
                    rel,
                    main="",
                    sub=ChildChoice("empty", ""),
                    detail=ChildChoice("empty", ""),
                    summary=f"{type(exc).__name__}: {exc}",
                    reason=f"{type(exc).__name__}: {exc}",
                )
            save_walk_state(cfg, state)
            # Regions/HTML are for the operator, not the clerk. Every 20
            # files is enough to watch; every file would rewrite the map 400×.
            if i == 1 or i % 20 == 0 or i == len(pending):
                persist_payload(cfg, build_walk_regions(state))
    finally:
        progress.finish(len(pending))
        save_walk_state(cfg, state)

    payload = build_walk_regions(state)
    persist_payload(cfg, payload)
    records = [state.records[k] for k in sorted(state.records)]
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
        f"WALK done: {meta['documents']} files, {meta['top_level']} roots, "
        f"{meta['nodes']} nodes, {meta['unmapped']} unmapped, "
        f"{meta['combines']} combines, homes/file {meta['homes_mean']} "
        f"→ {out / 'regions.json'}",
        flush=True,
    )
    return meta
