"""Pass B steps A then B: normalize synonyms, then cluster concepts.

Best practice (ISO 25964-1 / SKOS + TaxoGen / Microsoft cluster-then-label):

1. **A — preferred vs non-preferred.** ``curriculum_admin`` and
   ``curriculum-admin`` are one concept, not two nodes. Do this *before*
   any hierarchy (ISO: equivalence first, then BT/NT).
2. **B — cluster concepts.** Group concepts that co-occur on the same
   documents *and* share a content token. Co-occurrence alone would glue
   ``curriculum-admin`` to ``work-email`` (related, not the same idea).
   Token overlap is the stdlib stand-in for TaxoGen's "coherent term cluster."

Nemotron then sees **cluster labels**, not 3515 raw strings. The long tail
of singleton concepts is kept as its own cluster (or left for the leftover
mapper) so we do not invent singularities as first-class nodes.

Stdlib only. No embeddings in this step — that is optional later (BERTopic).
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

# Tokens that never distinguish a CTE concept. Dropping them lets
# ``cte-middle-school`` and ``middle-school-cte`` become the same concept.
_GENERIC_TOKENS = frozenset(
    {
        "and",
        "cte",
        "dallas",
        "disd",
        "doc",
        "document",
        "form",
        "isd",
        "or",
        "pdf",
        "school",
        "the",
        "year",
    }
)

# Conservative ISO-style equivalence, not a full stemmer.
# Over-merge of quasi-synonyms is a vocabulary *decision* — keep this list tight.
_TOKEN_EQUIV = {
    "administration": "admin",
    "administrations": "admin",
    "admins": "admin",
    "certifications": "certification",
    "records": "record",
    "trainings": "training",
    "quotes": "quote",
    "vendors": "vendor",
    "forms": "form",
}

# Co-occurrence thresholds. Jaccard-only hairballs; shared-docs-only is too loose.
# Require both a real overlap *and* a shared content word (TaxoGen coherence).
CLUSTER_MIN_JACCARD = 0.25
CLUSTER_MIN_SHARED = 2
CLUSTER_MAX_MEMBERS = 16


@dataclass
class Concept:
    """One SKOS concept: a preferred label plus the raw tag strings that mean it."""

    preferred: str
    aliases: list[str]
    count: int
    docs: frozenset[str]


@dataclass
class Cluster:
    """A TaxoGen-style node: a coherent group of concepts, labeled by its head."""

    label: str
    members: list[Concept]
    count: int
    aliases: list[str] = field(default_factory=list)
    docs: frozenset[str] = field(default_factory=frozenset)


def kebab_pref(tag: str) -> str:
    """SKOS-style prefLabel: lowercase kebab, punctuation collapsed.

    Best practice: one preferred form per concept so later steps never see
    ``curriculum_admin`` and ``curriculum-admin`` as rivals.
    """
    s = str(tag).strip().lower()
    s = re.sub(r"[\s_/]+", "-", s)
    s = re.sub(r"[^a-z0-9-]+", "-", s)
    s = re.sub(r"-{2,}", "-", s)
    return s.strip("-")


def content_tokens(tag: str) -> frozenset[str]:
    """Content words after equivalence mapping. Empty ⇒ treat the kebab as one token."""
    parts = []
    for raw in re.split(r"[-_/\s]+", kebab_pref(tag)):
        if len(raw) <= 2 or raw in _GENERIC_TOKENS or raw.isdigit():
            continue
        parts.append(_TOKEN_EQUIV.get(raw, raw))
    return frozenset(parts) if parts else frozenset([kebab_pref(tag) or str(tag)])


def normalize_concepts(
    counts: Counter[str], docs_by_tag: dict[str, list[str]]
) -> list[Concept]:
    """Step A: collapse raw tag strings into preferred / non-preferred concepts.

    Two tags become one concept when:
    - they share a kebab form (underscore vs hyphen vs spaces), or
    - their content-token sets are equal (``middle-school-cte`` /
      ``cte-middle-school``; ``curriculum-admin`` / ``curriculum-administration``).
    """
    groups: dict[frozenset[str], list[str]] = defaultdict(list)
    for tag in counts:
        groups[content_tokens(tag)].append(tag)

    concepts: list[Concept] = []
    for _key, aliases in groups.items():
        # Preferred label = kebab of the most frequent alias (ISO: humans
        # usually pick the term; frequency is the local proxy).
        head = max(aliases, key=lambda t: (counts[t], -len(t), t))
        docs: set[str] = set()
        for alias in aliases:
            docs.update(docs_by_tag.get(alias) or [])
        concepts.append(
            Concept(
                preferred=kebab_pref(head) or str(head),
                aliases=sorted(set(aliases), key=lambda t: (-counts[t], t)),
                count=len(docs),
                docs=frozenset(docs),
            )
        )
    concepts.sort(key=lambda c: (-c.count, c.preferred))
    return concepts


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    if not inter:
        return 0.0
    return inter / len(a | b)


def cluster_concepts(
    concepts: list[Concept],
    *,
    min_jaccard: float = CLUSTER_MIN_JACCARD,
    min_shared: int = CLUSTER_MIN_SHARED,
    max_members: int = CLUSTER_MAX_MEMBERS,
) -> list[Cluster]:
    """Step B: greedy co-occurrence clusters, seeded by frequent concepts.

    Greedy (not single-linkage) so a chain of weak edges cannot collapse the
    whole inventory into one hairball. A candidate joins a cluster only when:

    - it shares ``min_shared`` documents with the *seed* (not the growing union),
    - Jaccard vs the seed is at least ``min_jaccard``,
    - it shares a content token with the seed (coherent terms).

    Concepts that never qualify stay as singleton clusters. NN/g calls those
    singularities — the stitch prompt will omit count==1 clusters.
    """
    unused = list(concepts)
    clusters: list[Cluster] = []

    while unused:
        seed = unused.pop(0)
        seed_toks = content_tokens(seed.preferred)
        members = [seed]
        kept: list[Concept] = []
        for cand in unused:
            if len(members) >= max_members:
                kept.append(cand)
                continue
            shared = len(seed.docs & cand.docs)
            if shared < min_shared:
                kept.append(cand)
                continue
            if _jaccard(seed.docs, cand.docs) < min_jaccard:
                kept.append(cand)
                continue
            cand_toks = content_tokens(cand.preferred)
            if not (seed_toks & cand_toks):
                kept.append(cand)
                continue
            members.append(cand)
        unused = kept

        docs: set[str] = set()
        aliases: list[str] = []
        for m in members:
            docs.update(m.docs)
            aliases.extend(m.aliases)
        clusters.append(
            Cluster(
                label=seed.preferred,
                members=members,
                count=len(docs),
                aliases=list(dict.fromkeys(aliases)),
                docs=frozenset(docs),
            )
        )

    clusters.sort(key=lambda c: (-c.count, c.label))
    return clusters


def expand_aliases(tag_to_region: dict[str, str], clusters: list[Cluster]) -> int:
    """If any alias (or the cluster label) is mapped, map every sibling alias.

    Best practice: the model only lists representative labels. The harness
    owns SKOS altLabel expansion so we never ask Nemotron to enumerate 3515 tags.
    """
    added = 0
    for cluster in clusters:
        hits = [tag_to_region[a] for a in cluster.aliases if a in tag_to_region]
        if cluster.label in tag_to_region:
            hits.append(tag_to_region[cluster.label])
        if not hits:
            continue
        rid = hits[0]
        for alias in cluster.aliases:
            if alias not in tag_to_region:
                tag_to_region[alias] = rid
                added += 1
        if cluster.label not in tag_to_region:
            tag_to_region[cluster.label] = rid
            added += 1
    return added
