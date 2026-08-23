"""Fetch a public gold folder tree. Texts stay under .data/ (gitignored).

Two corpora, same layout:

  .data/<name>/gold/     pre-sorted folders (the answer key)
  .data/<name>/inbox/    flattened copies (what Burling sees)
  .data/<name>/gold.json doc_id → gold paths
  .data/<name>/README.md citation + license

  python -m burling.fetch_gold --corpus 20newsgroups
  python -m burling.fetch_gold --corpus multieurlex
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import tarfile
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / ".data"

# Jason Rennie's by-date split — the usual 20 Newsgroups eval cut.
# Homepage: https://qwone.com/~jason/20Newsgroups/
# sklearn's mirror (Figshare) is what actually downloads; qwone often times out.
NEWS20_URLS = (
    "https://ndownloader.figshare.com/files/5975967",
    "https://qwone.com/~jason/20Newsgroups/20news-bydate.tar.gz",
    "https://people.csail.mit.edu/jrennie/20Newsgroups/20news-bydate.tar.gz",
)
NEWS20_SHA256 = "8f1b2514ca22a5ade8fbb9cfa5727df95fa587f4c87b786e15c759fa66d95610"

# First token of the newsgroup is the topic (comp, rec, sci, talk, …).
NEWS20_ROOTS = {
    "alt": "Belief",
    "comp": "Computing",
    "misc": "Marketplace",
    "rec": "Recreation",
    "sci": "Science",
    "soc": "Society",
    "talk": "Debate",
}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _tar_ok(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 1_000_000 and _sha256(path) == NEWS20_SHA256


def _slug(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s or "topic"


def _write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def fetch_20newsgroups(*, per_leaf: int = 20, seed: int = 20260820) -> Path:
    """Download the by-date TEST split and keep `per_leaf` docs per newsgroup."""
    out = DATA / "20newsgroups"
    raw_tar = DATA / "cache" / "20news-bydate.tar.gz"
    raw_tar.parent.mkdir(parents=True, exist_ok=True)
    if not _tar_ok(raw_tar):
        last_err: Exception | None = None
        for url in NEWS20_URLS:
            print(f"downloading {url}", flush=True)
            try:
                urllib.request.urlretrieve(url, raw_tar)
                if _tar_ok(raw_tar):
                    last_err = None
                    break
                last_err = ValueError(f"bad checksum from {url}")
            except OSError as exc:
                last_err = exc
        if last_err:
            raise last_err

    extract = DATA / "cache" / "20news-bydate"
    test_dir = extract / "20news-bydate-test"
    if not test_dir.is_dir():
        print(f"extracting {raw_tar}", flush=True)
        with tarfile.open(raw_tar, "r:gz") as tf:
            tf.extractall(extract)

    rng = random.Random(seed)
    by_leaf: dict[str, list[Path]] = defaultdict(list)
    for path in sorted(test_dir.rglob("*")):
        if not path.is_file():
            continue
        leaf = path.parent.name  # e.g. rec.sport.hockey
        by_leaf[leaf].append(path)

    gold_root = out / "gold"
    if gold_root.exists():
        # Rebuild so a second run is deterministic.
        import shutil

        shutil.rmtree(out, ignore_errors=True)
    gold_root.mkdir(parents=True)

    gold_by_rel: dict[str, list[str]] = {}
    kept = 0
    for leaf, files in sorted(by_leaf.items()):
        root_key = leaf.split(".", 1)[0]
        topic = NEWS20_ROOTS.get(root_key, root_key)
        sub = leaf.split(".", 1)[1] if "." in leaf else leaf
        topic_slug, sub_slug = _slug(topic), _slug(sub)
        chosen = list(files)
        rng.shuffle(chosen)
        chosen = chosen[:per_leaf]
        for src in chosen:
            rel = Path(topic_slug) / sub_slug / f"{src.name}.txt"
            dest = gold_root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            text = src.read_bytes()
            # Best-effort: drop Usenet headers so poster emails are less tempting.
            try:
                body = text.decode("latin-1")
                if "\n\n" in body:
                    body = body.split("\n\n", 1)[1]
                dest.write_text(body, encoding="utf-8")
            except OSError:
                dest.write_bytes(text)
            gold_by_rel[str(rel)] = [f"{topic_slug}/{sub_slug}"]
            kept += 1

    inbox_meta: dict[str, dict] = {}
    inbox = out / "inbox"
    inbox.mkdir(parents=True)
    for rel, paths in gold_by_rel.items():
        digest = hashlib.sha1(rel.encode()).hexdigest()[:12]
        (inbox / f"{digest}.txt").write_bytes((gold_root / rel).read_bytes())
        inbox_meta[f"{digest}.txt"] = {"gold_rel": rel, "paths": paths}

    _write_json(out / "gold.json", inbox_meta)
    (out / "README.md").write_text(
        "\n".join(
            [
                "# 20 Newsgroups (by-date test, sampled)",
                "",
                f"- Files: **{kept}** ({per_leaf} per newsgroup, seed {seed})",
                "- Gold tree: topic (comp/rec/sci/…) → subtopic (the newsgroup leaf)",
                "- Inbox names are hashes — the model must not see folder names",
                "- Source: [Jason Rennie / 20 Newsgroups](https://qwone.com/~jason/20Newsgroups/)",
                "- Split: `20news-bydate-test` (the usual eval cut)",
                "- This is a **public folder tree** we can run tonight.",
                "- It is **not** the locked Layer 2 gold (that is MultiEURLEX / EUROVOC).",
                "- Headers stripped when a blank line exists (Usenet From/email).",
                "",
                "Cite: Lang, K. NewsWeeder (the collection commonly used via",
                "Joachims / Rennie’s by-date redistribution).",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"20newsgroups: {kept} files → {out}", flush=True)
    return out


def fetch_multieurlex(*, per_l1: int = 25, seed: int = 20260820) -> Path:
    """English MultiEURLEX test split, stratified by EUROVOC level-1.

    Hugging Face still pulls the full ~2.8GB tarball once, then keeps English.
    """
    try:
        from datasets import load_dataset
    except ImportError as exc:
        raise SystemExit(
            "pip install datasets   # then re-run --corpus multieurlex"
        ) from exc

    out = DATA / "multieurlex-en"
    print("loading coastalcph/multi_eurlex en / test (first run downloads ~2.8GB)", flush=True)
    ds = load_dataset("coastalcph/multi_eurlex", "en", split="test")
    classlabel = ds.features["labels"].feature

    rng = random.Random(seed)
    by_l1: dict[str, list] = defaultdict(list)
    for row in ds:
        labels = row.get("labels") or []
        if not labels:
            continue
        # First L1 id is the primary gold parent for stratification.
        l1 = classlabel.int2str(int(labels[0]))
        by_l1[l1].append(row)

    gold_root = out / "gold"
    if out.exists():
        import shutil

        shutil.rmtree(out)
    gold_root.mkdir(parents=True)

    inbox_meta: dict[str, dict] = {}
    inbox = out / "inbox"
    inbox.mkdir()
    kept = 0
    for l1, rows in sorted(by_l1.items()):
        rng.shuffle(rows)
        topic = _slug(str(l1))
        for row in rows[:per_l1]:
            celex = str(row["celex_id"])
            paths = []
            for lab in row["labels"]:
                desc = classlabel.int2str(int(lab))
                paths.append(_slug(str(desc)))
            # L1-only folders until we join the L2 descriptor map.
            rel = Path(topic) / f"{celex}.txt"
            dest = gold_root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(str(row["text"] or ""), encoding="utf-8")
            digest = hashlib.sha1(celex.encode()).hexdigest()[:12]
            (inbox / f"{digest}.txt").write_text(str(row["text"] or ""), encoding="utf-8")
            inbox_meta[f"{digest}.txt"] = {
                "celex_id": celex,
                "gold_rel": str(rel),
                "paths": paths,
            }
            kept += 1

    _write_json(out / "gold.json", inbox_meta)
    (out / "README.md").write_text(
        "\n".join(
            [
                "# MultiEURLEX English (test, stratified L1 sample)",
                "",
                f"- Files: **{kept}** (~{per_l1} per EUROVOC level-1, seed {seed})",
                "- Source: `coastalcph/multi_eurlex` config `en` split `test`",
                "- Paper: Chalkidis, Fergadiotis, Androutsopoulos, EMNLP 2021",
                "- https://arxiv.org/abs/2109.00904",
                "- License: CC-BY-4.0 (EUR-Lex reuse; acknowledge + mark changes)",
                "- © European Union, 1998–2021",
                "- Do not use `nlpaueb/multi_eurlex` (2022 5-language cut)",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"multieurlex: {kept} files → {out}", flush=True)
    return out


def main() -> None:
    p = argparse.ArgumentParser(description="Fetch a public gold inbox (gitignored).")
    p.add_argument(
        "--corpus",
        choices=("20newsgroups", "multieurlex"),
        default="20newsgroups",
    )
    p.add_argument("--per-leaf", type=int, default=20)
    p.add_argument("--per-l1", type=int, default=25)
    args = p.parse_args()
    DATA.mkdir(parents=True, exist_ok=True)
    if args.corpus == "20newsgroups":
        fetch_20newsgroups(per_leaf=args.per_leaf)
    else:
        fetch_multieurlex(per_l1=args.per_l1)


if __name__ == "__main__":
    main()
