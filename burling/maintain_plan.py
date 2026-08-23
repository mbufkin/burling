"""Folder-maintenance pass: combine is a supervisor step, not filing.

The clerk files one letter at a time. A later pass looks at fat, mixed
parents and asks whether some siblings are the same kind of thing.
The model proposes groups. This module keeps or drops them, then
rehomes through WalkState.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from burling.layer_plan import FAT_MIN, kebab
from burling.walk_plan import WalkState


@dataclass(frozen=True)
class Merge:
    """One accepted combine: existing siblings nest under a broader folder."""

    merge: tuple[str, ...]
    into: str


def coerce_merges(raw: object, siblings: list[str]) -> list[Merge]:
    """Model proposes groups; code is the records office.

    Keep a merge only when it names two or more *existing* siblings and
    leaves at least one sibling behind. A one-child merge is dropped.
    Merging every sibling is a rename, not a combine.
    """
    obj = raw if isinstance(raw, dict) else {}
    proposed = obj.get("merges")
    if not isinstance(proposed, list):
        return []

    sibling_set = {kebab(s) for s in siblings if kebab(s)}
    kept: list[Merge] = []
    for group in proposed:
        if not isinstance(group, dict):
            continue
        into = kebab(group.get("into"))
        # Only ids that already exist under this parent can move.
        merge = [kebab(c) for c in (group.get("merge") or []) if kebab(c) in sibling_set]
        # Deduplicate while keeping the model's order.
        seen: set[str] = set()
        merge = [c for c in merge if not (c in seen or seen.add(c))]
        if not into or len(merge) < 2:
            continue
        if set(merge) == sibling_set:
            continue
        kept.append(Merge(merge=tuple(merge), into=into))
    return kept


def folders_needing_maintain(state: WalkState) -> list[list[str]]:
    """Parents that are fat enough and mixed enough to ask about combines.

    Root is skipped: closed workplace series stay roots (Navy does not
    merge 2000 with 7000). A parent is fat at FAT_MIN files and mixed
    when it has two or more children. Thin or single-child piles stay.
    """
    files_under: Counter[tuple[str, ...]] = Counter()
    children_of: dict[tuple[str, ...], set[str]] = {}
    for home in state.homes.values():
        if not home:
            continue
        for depth in range(1, len(home)):
            parent = tuple(home[:depth])
            files_under[parent] += 1
            children_of.setdefault(parent, set()).add(home[depth])
        # A file sitting on the folder itself still counts toward fat.
        files_under[tuple(home)] += 1

    needed: list[list[str]] = []
    for parent, n_files in files_under.items():
        if n_files < FAT_MIN:
            continue
        if len(children_of.get(parent, set())) < 2:
            continue
        needed.append(list(parent))
    needed.sort()
    return needed


def apply_merges(
    state: WalkState,
    prefix: list[str],
    merges: list[Merge],
) -> int:
    """Rehome each accepted group. Returns how many files moved.

    WalkState.rehome is the Navy closest-folder move: old sibling names
    nest under ``into`` when depth allows. This pass records combines;
    filing does not.
    """
    moved = 0
    for group in merges:
        moved += state.rehome(prefix, list(group.merge), group.into)
    return moved
