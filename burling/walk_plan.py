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

Andon stop (research ticket #37, jidoka): a high-severity file the
clerk cannot place is never dumped into ``unmapped``. It is kept where
it is and the line stops until the cause is fixed and it re-files. Low
severity leftovers bin as before. Disable with ``walk.andon_stop: false``.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from burling.file_plan import (
    UNMAPPED_ID,
    approved_children,
    ensure_unmapped,
    is_banned_head,
)
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
- Decide in this order: (1) Is there any existing child that could hold
  this file, even loosely? Reuse it. (2) Only if NO existing child covers
  the subject at all, invent.
- One-file drawers are a filing failure. Before inventing, ask: "would a
  clerk filing ten similar documents put them here again?" If not,
  reuse the closest existing child instead.
- Do not invent a near-duplicate of an existing child; reuse the closest name.
- Two files about neighboring subjects share a drawer; the drawer name is
  the broader category (e.g. invoices, incidents, policies), never the
  specific document.
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
    # rel_path → reason for high-severity files kept in place (andon).
    # Transient by design: never a folder, cleared on successful re-file.
    andon_keeps: dict[str, str] = field(default_factory=dict)

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

    def rehome(
        self,
        prefix: list[str],
        merge: list[str],
        into: str,
        *,
        reasoning: str = "",
    ) -> int:
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
            members = sorted(merge_set)
            self.combines.append(
                {
                    "at": utc_now(),
                    "prefix": list(prefix),
                    "from": members,
                    "merge": members,
                    "into": into,
                    "reasoning": (reasoning or "")[:800],
                    "moved": moved,
                }
            )
        return moved

    def promote(self, prefix: list[str], child: str, *, reasoning: str = "") -> int:
        """Dissolve drawer prefix+child: its files move up to prefix.

        The combine sweep's answer to one-file drawers — navigation depth
        without retrieval value. Guarded by the caller (thin drawers only).
        """
        child = kebab(child)
        if not child or not prefix:
            return 0
        depth = len(prefix)
        moved = 0
        for rel, home in list(self.homes.items()):
            if len(home) <= depth or home[:depth] != list(prefix):
                continue
            if home[depth] != child:
                continue
            self.homes[rel] = home[:depth] + home[depth + 1 :]
            rec = self.records.get(rel) or {}
            new = self.homes[rel]
            rec["main"] = new[0] if new else ""
            rec["sub"] = new[1] if len(new) > 1 else ""
            rec["detail"] = new[2] if len(new) > 2 else ""
            rec["facet"] = self.facets.get(rel) or rec.get("facet") or ""
            self.records[rel] = rec
            moved += 1
        if moved:
            self.combines.append(
                {
                    "at": utc_now(),
                    "prefix": list(prefix),
                    "from": [child],
                    "merge": [child],
                    "into": "/".join(prefix) or "(root)",
                    "dissolve": True,
                    "reasoning": (reasoning or "")[:800],
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
        severity: str = "low",
    ) -> list[str]:
        """File this document only. Siblings stay put.

        Best practice: combining drawers is a later set task
        (maintain_plan). Filing must not rewrite the tree.

        Andon: a high-severity document that would land in unmapped is
        auto-kept in its current home instead — filed nowhere, binned
        nowhere — and the caller stops the line.
        """
        if not main:
            if severity == "high":
                self.andon_keeps[rel_path] = reason or "no topical substance"
                self.records[rel_path] = {
                    "rel_path": rel_path,
                    "main": "",
                    "sub": "",
                    "detail": "",
                    "summary": summary,
                    "reason": (
                        f"andon: high-severity file kept in place "
                        f"({reason or 'no topical substance'})"
                    ),
                    "status": "andon-keep",
                    "at": utc_now(),
                }
                return []
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
        self.andon_keeps.pop(rel_path, None)  # re-filed: clear the stop.
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
            "andon_keeps": len(state.andon_keeps),
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


def walk_source_records(cfg: dict) -> list[dict]:
    """Files to walk. After a review run the ledger exists; tags.json may not.

    Order: ledger documents → queue.json → tags.json → intake listing.
    Best practice: the clerk files the dump that was queued, not a
    leftover stitch roster from a previous experiment.
    """
    from burling.extract import iter_source_files
    from burling.ledger import load_ledger
    from burling.paths import intake_dir as config_intake
    from burling.queue import load_queue
    from burling.stitch_tags import load_tag_records

    seen: set[str] = set()
    rows: list[dict] = []

    def _add(rel: object) -> None:
        path = str(rel or "").strip()
        if path and path not in seen:
            seen.add(path)
            rows.append({"rel_path": path})

    ledger = load_ledger(cfg)
    for rec in (ledger.get("documents") or {}).values():
        if isinstance(rec, dict):
            _add(rec.get("rel_path"))
    if rows:
        rows.sort(key=lambda item: item["rel_path"])
        return rows

    for item in (load_queue(cfg).get("items") or []):
        if isinstance(item, dict):
            _add(item.get("rel_path"))
    if rows:
        return rows

    tags_path = Path(cfg.get("paths", {}).get("tags_json") or (output_dir(cfg) / "tags.json"))
    if tags_path.is_file():
        for rec in load_tag_records(cfg, tags_path):
            if isinstance(rec, dict):
                _add(rec.get("rel_path"))
        if rows:
            return rows

    intake = config_intake(cfg)
    if intake.is_dir():
        for path in iter_source_files(intake):
            _add(path.relative_to(intake).as_posix())
    return rows


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
        andon_keeps={
            str(k): str(v)
            for k, v in (data.get("andon_keeps") or {}).items()
            if isinstance(v, str)
        },
    )


def save_walk_state(cfg: dict, state: WalkState) -> None:
    atomic_write_json(
        _state_path(cfg),
        {
            "homes": state.homes,
            "facets": state.facets,
            "records": state.records,
            "combines": state.combines,
            "andon_keeps": state.andon_keeps,
            "method": "walk-file-plan",
        },
    )


WALK_CALLS_NAME = "walk-decisions.jsonl"


def _log_walk_call(
    cfg: dict,
    step: str,
    messages: list[dict],
    raw: object,
    error: str | None = None,
) -> None:
    """Append one walk model call to output/walk-decisions.jsonl.

    Decision context only: folder, siblings, and the raw answer. The
    DOCUMENT TEXT section of the prompt is stripped — trace.py's rule:
    never create a second PII store. Log I/O must not kill the run.
    """
    try:
        user = next((m.get("content") or "" for m in messages if m.get("role") == "user"), "")
        head = user.split("DOCUMENT TEXT:")[0].strip()
        rec = {
            "at": utc_now(),
            "step": step,
            "context": head,
            "raw": raw if isinstance(raw, dict) else str(raw or "")[:500],
        }
        if error:
            rec["error"] = error
        path = output_dir(cfg) / WALK_CALLS_NAME
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception as exc:
        from burling.progress import console_safe

        print(console_safe(f"  NOTED [walk-log] {step}: {exc}"), flush=True)


DISSOLVE_MAX_FILES = 1


def _split_proposal(
    raw: object,
    prefix: list[str],
    children: list[tuple[str, int]],
) -> tuple[list[dict], list[str]]:
    """Split raw combine groups into sideways merges and dissolves.

    A group whose `into` names the folder itself means "these drawers are
    thinner than the tree needs — promote their files up here." Only thin
    drawers (<= DISSOLVE_MAX_FILES files) may dissolve; fat ones stay put.
    """
    obj = raw if isinstance(raw, dict) else {}
    raw_groups = obj.get("groups")
    if not isinstance(raw_groups, list):
        if obj.get("merge") or obj.get("into"):
            raw_groups = [obj]
        else:
            raw_groups = []
    sibling_names = {kebab(n) for n, _c in children}
    counts = {kebab(n): c for n, c in children}
    parent_name = kebab(prefix[-1]) if prefix else ""

    merges_raw: list[dict] = []
    dissolves: set[str] = set()
    for group in raw_groups:
        if not isinstance(group, dict):
            continue
        into = kebab(group.get("into") or group.get("name"))
        merge = [kebab(c) for c in (group.get("merge") or []) if kebab(c) in sibling_names]
        merge = list(dict.fromkeys(merge))
        if into == parent_name and parent_name:
            # Dissolve request. Thin drawers only; fat ones are refused.
            for child in merge:
                if counts.get(child, 0) <= DISSOLVE_MAX_FILES:
                    dissolves.add(child)
        elif merge:
            merges_raw.append(group)
    return merges_raw, sorted(dissolves)


def _ask(cfg: dict, messages: list[dict], step: str) -> dict:
    """One fresh-window JSON call. Empty dict on failure so the clerk can retry."""
    try:
        raw = chat(cfg, messages, step=step)
        raw = raw if isinstance(raw, dict) else {}
        _log_walk_call(cfg, step, messages, raw)
        return raw
    except Exception as exc:
        print(f"  walk {step} failed: {exc}", flush=True)
        _log_walk_call(cfg, step, messages, {}, error=f"{type(exc).__name__}: {exc}")
        return {}


def _child_user(
    rel_path: str,
    text: str,
    prefix: list[str],
    siblings: list[tuple[str, int]],
    approved: set[str] | None = None,
) -> str:
    folder = "/".join(prefix) or "(root)"
    if siblings:
        lines = [f"- {name}: {n}" for name, n in siblings]
        existing = "EXISTING CHILDREN (name: files):\n" + "\n".join(lines)
    else:
        existing = "EXISTING CHILDREN: none. Invent the first child, or empty if none fits."
    menu = ""
    if approved:
        menu = (
            "\n\nAPPROVED CHILDREN for this folder (pick from these when one fits; "
            "invent only if none covers the subject):\n- "
            + "\n- ".join(sorted(approved))
        )
    return (
        f"FILE: {rel_path}\n"
        f"CURRENT FOLDER: {folder}\n\n"
        f"{existing}{menu}\n\n"
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
    approved: set[str] | None = None,
) -> dict:
    user = _child_user(rel_path, text, prefix, siblings, approved=approved)
    return _ask(
        cfg,
        [{"role": "system", "content": CHILD_SYSTEM}, {"role": "user", "content": user}],
        step=f"walk-child:{'/'.join(prefix)}:{rel_path}",
    )


def _coerce_with_menu(raw: object, children: list, approved: set[str] | None) -> ChildChoice:
    """Coerce a child proposal; off-menu inventions fall back to empty.

    The menu is the poka-yoke: a drawer outside the org's plan is not a
    drawer we want, however plausible the name. Staying at the main level
    is the honest miss.
    """
    choice = coerce_child_choice(
        raw, [n for n, _c in children], allow_empty=True
    )
    if approved is None or choice.action != "invent" or not choice.name:
        return choice
    return ChildChoice("empty", "") if kebab(choice.name) not in approved else choice


def walk_one(
    state: WalkState,
    *,
    rel_path: str,
    text: str,
    choose_main: Chooser,
    choose_child: Chooser,
    severity: str = "low",
    cfg: dict | None = None,
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
            severity=severity,
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
            summary=summary, reason=reason or "no topical substance", severity=severity,
        )

    approved = approved_children(cfg, main) if cfg is not None else None
    sub_raw = choose_child(
        rel_path=rel_path,
        text=text,
        prefix=[main],
        siblings=state.children([main]),
        approved=approved,
    )
    sub = _coerce_with_menu(sub_raw, state.children([main]), approved)
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


def _severity_map(cfg: dict) -> dict[str, str]:
    """rel_path → prior_severity from the ledger. Missing file/field = low."""
    # priors live on ledger rows (queue.json carries only the item roster).
    from burling.ledger import load_ledger

    try:
        data = load_ledger(cfg)
    except Exception:
        return {}
    out: dict[str, str] = {}
    for row in (data.get("documents") or {}).values():
        if not isinstance(row, dict):
            continue
        rel = row.get("rel_path")
        sev = row.get("prior_severity")
        if rel and sev:
            out[str(rel)] = str(sev)
    return out


def _andon_banner(state: WalkState) -> str:
    lines = [
        f"ANDON STOP: {len(state.andon_keeps)} high-severity file(s) could not be "
        "filed and were kept in their current home — never binned, never deleted.",
    ]
    lines += [f"  - {console_safe(rel)}" for rel in sorted(state.andon_keeps)]
    lines.append(
        "The line is stopped. Fix the cause (extraction/tagging), then resume with "
        "--walk --resume: kept files retry first and clear the stop when they file."
    )
    return "\n".join(lines)


def run_walk_plan(
    cfg: dict,
    *,
    resume: bool = False,
    limit: int | None = None,
    force: bool = False,
    choose_main: Chooser | None = None,
    choose_child: Chooser | None = None,
    choose_combine: Chooser | None = None,
) -> dict:
    """Walk every listed file. Writes a new output folder. Resume-safe.

    Filing places this letter. Maintain may combine fat mixed drawers
    after it is home. Inject choosers in tests so CI never needs a GPU.
    """
    from burling.maintain_plan import choose_combine_model, maintain_after_place
    from burling.ralp import persist_payload

    out = output_dir(cfg)
    out.mkdir(parents=True, exist_ok=True)
    source = walk_source_records(cfg)
    if not source:
        raise RuntimeError(
            "No document list for --walk (need a ledger, queue, tags.json, or intake files)."
        )

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
    combine_fn = choose_combine or (lambda **kw: choose_combine_model(cfg, **kw))
    andon_on = bool(cfg.get("walk", {}).get("andon_stop", True))
    sevs = _severity_map(cfg) if andon_on else {}
    # Kept files retry first: the stop clears the moment they re-file.
    pending.sort(
        key=lambda r: (
            0 if state.records.get(str(r.get("rel_path") or ""), {}).get("status") == "andon-keep" else 1
        )
    )

    progress = Progress(cfg, "walk", len(pending))
    try:
        for i, rec in enumerate(pending, start=1):
            rel = str(rec.get("rel_path") or "")
            # Andon gate: an unresolved high-severity keep stops the line.
            if state.andon_keeps and rel not in state.andon_keeps:
                print(_andon_banner(state), flush=True)
                break
            progress.tick(i, rel)
            try:
                text = _doc_text(cfg, rel)
                home = walk_one(
                    state,
                    rel_path=rel,
                    text=text,
                    choose_main=main_fn,
                    choose_child=child_fn,
                    severity=sevs.get(rel, "low"),
                    cfg=cfg,
                )
                print(
                    console_safe(f"  walk {rel} → {'/'.join(home)}"),
                    flush=True,
                )
                # Combine is a later set task. Do not smuggle it into filing.
                maintain_after_place(state, home, choose_combine=combine_fn)
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
                    severity=sevs.get(rel, "low"),
                )
            if state.records.get(rel, {}).get("status") == "andon-keep":
                print(_andon_banner(state), flush=True)
                break
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
