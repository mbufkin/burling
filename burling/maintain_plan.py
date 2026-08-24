"""Supervisor combine: one set task on a folder, after the letter is home.

Filing (walk_one) only answers “where does THIS document go.” Combine is a
different job: look at sibling drawers and merge the ones that are the same
kind of thing. The 30B proposes groups; code is the records office.

Best practice: the combine window is folder names and counts, not document
text. Sending the letter would smuggle a second set task back into this call.
Invalid groups die in coerce_merges. Rehome is WalkState.rehome so filing
and maintain cannot drift.
"""

from __future__ import annotations

from typing import Callable

from burling.file_plan import UNMAPPED_ID
from burling.layer_plan import FAT_MIN, kebab
from burling.progress import console_safe
from burling.walk_plan import WalkState, _ask, _split_proposal, _valid_child

Chooser = Callable[..., dict]

# One group: two or more *existing* child ids, a broader into, and at least
# one sibling left behind (merging everyone is a rename, not a combine).
MergeGroup = tuple[tuple[str, ...], str]

COMBINE_SYSTEM = """You are looking at ONE folder on a workplace file plan.
Some child drawers may be the same kind of thing. Combine those. Do not
file a document. Do not rename the parent.

Output ONLY a valid JSON object:
{
  "reasoning": "windows and macos are both operating systems.",
  "groups": [
    {"merge": ["existing-id", "existing-id"], "into": "kebab-id"}
  ]
}

Rules:
- merge ids MUST be copied from EXISTING CHILDREN.
- into is the broader folder. It may be new or one of the merged ids.
- Leave at least one child out of each group. Merging every child is a rename.
- Return {"groups": []} if nothing should combine.
- Year, email, usenet, unmapped, and the approved mains are not child names.
"""


def _parent_stats(state: WalkState, prefix: list[str]) -> tuple[int, dict[str, int]]:
    """How many files sit under prefix, and the immediate child counts."""
    depth = len(prefix)
    n_files = 0
    children: dict[str, int] = {}
    for home in state.homes.values():
        if len(home) < depth or home[:depth] != prefix:
            continue
        n_files += 1
        if len(home) > depth:
            child = home[depth]
            if child and child != UNMAPPED_ID:
                children[child] = children.get(child, 0) + 1
    return n_files, children


def parent_is_maintainable(
    state: WalkState,
    prefix: list[str],
    *,
    fat_min: int = FAT_MIN,
) -> bool:
    """Fat and mixed, and not the tree root.

    Thin piles and single-child fat piles are skipped — combining then is
    a guess on a handful of letters. Closed series stay roots, so prefix
    [] is never maintainable.
    """
    if not prefix or prefix[0] == UNMAPPED_ID:
        return False
    n_files, children = _parent_stats(state, prefix)
    return n_files >= fat_min and len(children) >= 2


def folders_needing_maintain(
    state: WalkState,
    *,
    fat_min: int = FAT_MIN,
) -> list[list[str]]:
    """Every non-root parent that is currently fat and mixed."""
    prefixes: set[tuple[str, ...]] = set()
    for home in state.homes.values():
        if not home or home[0] == UNMAPPED_ID:
            continue
        if len(home) >= 1:
            prefixes.add(tuple(home[:1]))
        if len(home) >= 2:
            prefixes.add(tuple(home[:2]))
    out: list[list[str]] = []
    for prefix in sorted(prefixes, key=lambda t: (len(t), t)):
        path = list(prefix)
        if parent_is_maintainable(state, path, fat_min=fat_min):
            out.append(path)
    return out


def coerce_merges(raw: object, siblings: list[str]) -> list[MergeGroup]:
    """Keep a group only when it names two+ existing siblings and leaves one behind.

    Best practice: the model proposes; code is the records office. A one-child
    group is an invent in disguise. Merging everyone is a rename. Both die here.
    """
    sibling_set = {kebab(s) for s in siblings if kebab(s)}
    obj = raw if isinstance(raw, dict) else {}
    groups = obj.get("groups")
    if not isinstance(groups, list):
        # 30B often forgets the wrapper and emits one group at the top level.
        if isinstance(obj, dict) and (obj.get("merge") or obj.get("into")):
            groups = [obj]
        else:
            groups = []

    out: list[MergeGroup] = []
    claimed: set[str] = set()
    for group in groups:
        if not isinstance(group, dict):
            continue
        into = kebab(group.get("into") or group.get("name"))
        merge = [kebab(c) for c in (group.get("merge") or []) if kebab(c) in sibling_set]
        if into in sibling_set and into not in merge:
            merge.append(into)
        # One sibling cannot sit in two groups in the same answer.
        merge = [m for m in dict.fromkeys(merge) if m not in claimed]
        leftover = sibling_set - claimed - set(merge)
        if len(merge) < 2 or not leftover or not _valid_child(into):
            continue
        claimed.update(merge)
        out.append((tuple(merge), into))
    return out


def apply_merges(
    state: WalkState,
    prefix: list[str],
    groups: list[MergeGroup],
    *,
    reasoning: str = "",
) -> int:
    """Accepted groups rehome through WalkState.rehome.

    Best practice: one function so filing and maintain cannot drift.
    The combine window is names and counts; reasoning is stored on the
    log so a later reader can see why drawers moved.
    """
    moved = 0
    for merge, into in groups:
        moved += state.rehome(
            prefix, list(merge), into, reasoning=reasoning
        )
    return moved


def _combine_user(prefix: list[str], siblings: list[tuple[str, int]]) -> str:
    folder = "/".join(prefix) or "(root)"
    lines = [f"- {name}: {n}" for name, n in siblings]
    return (
        f"CURRENT FOLDER: {folder}\n\n"
        f"EXISTING CHILDREN (name: files):\n" + "\n".join(lines)
    )


def choose_combine_model(
    cfg: dict,
    *,
    prefix: list[str],
    siblings: list[tuple[str, int]],
    **_kw: object,
) -> dict:
    """Fresh window: this folder's children, no document text."""
    user = _combine_user(prefix, siblings)
    return _ask(
        cfg,
        [{"role": "system", "content": COMBINE_SYSTEM}, {"role": "user", "content": user}],
        step=f"walk-maintain:{'/'.join(prefix)}",
    )


def maintain_after_place(
    state: WalkState,
    home: list[str],
    *,
    choose_combine: Chooser,
    fat_min: int = FAT_MIN,
) -> int:
    """After this letter is home, maybe ask to combine its parent drawers.

    Only the prefixes this file just landed in are considered. Cousin
    folders did not change. Best practice: do not even call the model
    until parent_is_maintainable is true.
    """
    if not home or home[0] == UNMAPPED_ID:
        return 0
    prefixes: list[list[str]] = [home[:1]]
    if len(home) >= 2:
        prefixes.append(home[:2])

    moved = 0
    for prefix in prefixes:
        if not parent_is_maintainable(state, prefix, fat_min=fat_min):
            continue
        siblings = state.children(prefix)
        print(
            console_safe(
                f"  maintain {'/'.join(prefix)}: {sum(n for _n, n in siblings)} in "
                f"{len(siblings)} children"
            ),
            flush=True,
        )
        raw = choose_combine(prefix=prefix, siblings=siblings)
        groups = coerce_merges(raw, [name for name, _n in siblings])
        obj = raw if isinstance(raw, dict) else {}
        why = str(obj.get("reasoning") or "")[:800]
        n = apply_merges(state, prefix, groups, reasoning=why)
        if n:
            for merge, into in groups:
                print(
                    console_safe(
                        f"  combine {'/'.join(prefix)}: {', '.join(merge)} → {into}"
                    ),
                    flush=True,
                )
            if why:
                print(console_safe(f"  why: {why[:240]}"), flush=True)
        moved += n
    return moved


def sweep_combines(
    state,
    choose_combine: Callable[..., dict],
    *,
    min_children: int = 2,
) -> int:
    """Post-walk pass: offer EVERY parent with enough children to the combiner.

    Filing-time maintain only fires at FAT_MIN, so on small-to-medium dumps
    the fragmentation the walk created (one-file drawers) never gets a
    cleanup window. The sweep walks every depth-1 and depth-2 prefix with
    >= min_children children and applies whatever merges survive coercion.
    """
    prefixes: list[list[str]] = []
    seen: set[tuple[str, ...]] = set()
    for home in state.homes.values():
        for depth in (1, 2):
            if len(home) > depth:
                prefix = tuple(home[:depth])
                if prefix not in seen and prefix[0] != UNMAPPED_ID:
                    seen.add(prefix)
                    prefixes.append(list(prefix))

    moved = 0
    for prefix in sorted(prefixes):
        children = state.children(prefix)
        # Re-read after earlier merges may have rehomed these files away.
        children = [(n, c) for n, c in children if c > 0]
        if len(children) < min_children:
            continue
        raw = choose_combine(prefix=prefix, siblings=children)
        obj = raw if isinstance(raw, dict) else {}
        why = str(obj.get("reasoning") or "")[:800]
        merges_raw, dissolves = _split_proposal(raw, prefix, children)
        n = 0
        for child in dissolves:
            d = state.promote(prefix, child, reasoning=why or "combine sweep")
            if d:
                print(
                    console_safe(
                        f"  sweep {'/'.join(prefix)}: dissolve {child} ({d} file(s) up)"
                    ),
                    flush=True,
                )
            n += d
        groups = coerce_merges({"groups": merges_raw}, [name for name, _n in children])
        m = apply_merges(state, prefix, groups, reasoning=why or "combine sweep")
        if m:
            print(
                console_safe(
                    f"  sweep {'/'.join(prefix)}: "
                    + "; ".join(f"{', '.join(m2)} → {into}" for m2, into in groups)
                ),
                flush=True,
            )
        moved += n + m
    return moved
