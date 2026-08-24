"""Turn a stitch tree of hashed .txt names into a browse map you can read.

Why this exists
---------------
The gold inbox strips Usenet headers and hashes filenames so the model cannot
cheat from folder names. The raw regions.html therefore lists
``00451f0d5bb2.txt`` — useless for judging grouping.

This script does not re-stitch. It takes the finished ``regions.json`` and:

1. Places each file in **one** pile — the tightest home (smallest folder that
   is not Needs review). A stranger cannot browse three homes.
2. Names the file from the tagger **summary**, not the hash.
3. Writes a Finder folder tree and a one-page HTML map.

Best practice: keep gold labels as a muted purity hint, not as folder titles.
The product is a discovered browse tree.
"""

from __future__ import annotations

import json
import re
import shutil
from collections import defaultdict
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INBOX = ROOT / ".data" / "20newsgroups" / "inbox"
GOLD = ROOT / ".data" / "20newsgroups" / "gold.json"
HERE = Path(__file__).resolve().parent
DUMP = HERE / "v1-folders"
HTML = HERE / "v1-mapped.html"

# Channel / era piles. Still real stitch output — they just lose when a
# tighter topical pile exists (Hockey 4 beats Usenet 137).
CHANNEL_IDS = {
    "usenet-1993",
    "email-1990s",
    "email-archive",
    "usenet-archive",
    "newsgroup-discussion",
    "1990s-internet-culture",
    "needs-review",
}


def _title(summary: str, fallback: str) -> str:
    """First sentence of the summary, short enough for a Finder name."""
    text = re.sub(r"\s+", " ", (summary or "").strip())
    if not text:
        return fallback
    match = re.match(r"(.+?[.!?])(?:\s|$)", text)
    sentence = match.group(1) if match else text
    if len(sentence) > 88:
        sentence = sentence[:85].rsplit(" ", 1)[0] + "…"
    return sentence


def _safe_name(title: str, used: set[str]) -> str:
    """Filesystem-safe unique filename. Keep the title readable."""
    name = re.sub(r"[/\\:*?\"<>|]", "-", title).strip(" .") or "untitled"
    name = name[:120]
    candidate = f"{name}.txt"
    n = 2
    while candidate in used:
        candidate = f"{name} ({n}).txt"
        n += 1
    used.add(candidate)
    return candidate


def _primary(assignment: dict, sizes: dict[str, int]) -> str | None:
    """Tightest topical home. Channel piles only if nothing tighter exists."""
    ids = [rid for rid in assignment.get("region_ids") or [] if rid in sizes]
    if not ids:
        return None
    topical = [rid for rid in ids if rid not in CHANNEL_IDS]
    pool = topical or [rid for rid in ids if rid != "needs-review"] or ids
    return min(pool, key=lambda rid: (sizes[rid], rid))


def main() -> None:
    payload = json.loads((HERE / "v1-regions.json").read_text(encoding="utf-8"))
    gold = json.loads(GOLD.read_text(encoding="utf-8"))
    regions = [n for n in payload.get("regions") or [] if isinstance(n, dict)]
    labels = {n["id"]: n.get("label") or n["id"] for n in regions if n.get("id")}
    descs = {n["id"]: n.get("description") or "" for n in regions if n.get("id")}

    by_region: dict[str, list[dict]] = defaultdict(list)
    for a in payload.get("assignments") or []:
        for rid in a.get("region_ids") or []:
            by_region[rid].append(a)
    sizes = {rid: len(docs) for rid, docs in by_region.items()}

    # One file, one folder — the browse tree a stranger can walk.
    piles: dict[str, list[dict]] = defaultdict(list)
    for a in payload.get("assignments") or []:
        rid = _primary(a, sizes)
        if rid is None:
            rid = "unmapped"
            labels.setdefault("unmapped", "Unmapped")
            descs.setdefault("unmapped", "No stitch home.")
        rel = a.get("rel_path") or ""
        g = gold.get(rel) or {}
        gold_path = (g.get("paths") or ["?"])[0]
        piles[rid].append(
            {
                "rel": rel,
                "title": _title(a.get("summary") or "", rel),
                "summary": (a.get("summary") or "").strip(),
                "gold": gold_path.replace("/", " · "),
                "homes": len(a.get("region_ids") or []),
            }
        )

    if DUMP.exists():
        shutil.rmtree(DUMP)
    DUMP.mkdir(parents=True)

    html_piles = []
    for rid, docs in sorted(piles.items(), key=lambda kv: (-len(kv[1]), labels.get(kv[0], kv[0]))):
        label = labels.get(rid, rid)
        folder = DUMP / re.sub(r"[/\\:*?\"<>|]", "-", label)
        folder.mkdir(parents=True, exist_ok=True)
        used: set[str] = set()
        cards = []
        for doc in sorted(docs, key=lambda d: d["title"].lower()):
            src = INBOX / doc["rel"]
            body = src.read_text(encoding="utf-8", errors="replace") if src.is_file() else ""
            name = _safe_name(doc["title"], used)
            dest = folder / name
            dest.write_text(body, encoding="utf-8")
            cards.append({**doc, "file": name, "body": body})
        html_piles.append(
            {
                "id": rid,
                "label": label,
                "desc": descs.get(rid, ""),
                "channel": rid in CHANNEL_IDS,
                "docs": cards,
            }
        )

    _write_html(html_piles, len(payload.get("assignments") or []))
    print(f"folders → {DUMP}")
    print(f"html    → {HTML}")
    for pile in html_piles:
        kind = "channel" if pile["channel"] else "topic"
        print(f"  {len(pile['docs']):3}  {pile['label']}  ({kind})")


def _write_html(piles: list[dict], total: int) -> None:
    """One-page folder map: titles and summaries, not hash names."""
    nav = []
    panes = []
    for pile in piles:
        n = len(pile["docs"])
        kind = "channel" if pile["channel"] else "topic"
        nav.append(
            f'<button type="button" class="nav {kind}" data-pile="{escape(pile["id"])}">'
            f'<span>{escape(pile["label"])}</span><b>{n}</b></button>'
        )
        items = []
        for doc in pile["docs"]:
            items.append(
                "<article>"
                f"<h3>{escape(doc['title'])}</h3>"
                f"<p class='sum'>{escape(doc['summary'] or 'No summary.')}</p>"
                f"<p class='meta'>gold: {escape(doc['gold'])}"
                f" · also in {doc['homes'] - 1} other pile(s)</p>"
                f"<pre>{escape(doc['body'][:4000])}</pre>"
                "</article>"
            )
        panes.append(
            f'<section class="pile" id="pile-{escape(pile["id"])}" hidden>'
            f"<header><h2>{escape(pile['label'])}</h2>"
            f"<p>{escape(pile['desc'])} · {n} posts, each shown once here.</p></header>"
            f"{''.join(items)}</section>"
        )

    HTML.write_text(
        f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>20news stitch — mapped (v1)</title>
<style>
  :root {{
    --ink: #1c1917; --mute: #78716c; --line: #e7e5e4;
    --paper: #faf7f2; --card: #fff; --topic: #0f3d2e; --channel: #7c2d12;
  }}
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; height: 100%; }}
  body {{
    display: grid; grid-template-columns: 280px 1fr;
    font: 15px/1.45 ui-sans-serif, system-ui, sans-serif;
    color: var(--ink); background: var(--paper);
  }}
  nav {{
    border-right: 1px solid var(--line); padding: 20px 12px;
    overflow: auto; background: #fff;
  }}
  .lede {{ font-size: 12px; color: var(--mute); padding: 0 8px 16px; }}
  .lede b {{ color: var(--ink); }}
  button.nav {{
    display: flex; justify-content: space-between; gap: 8px;
    width: 100%; border: 0; background: transparent; text-align: left;
    padding: 8px; border-radius: 6px; cursor: pointer; font: inherit;
  }}
  button.nav:hover, button.nav.on {{ background: #f5f0e8; }}
  button.nav b {{ color: var(--mute); font-weight: 500; }}
  button.topic span {{ color: var(--topic); }}
  button.channel span {{ color: var(--channel); }}
  main {{ overflow: auto; padding: 28px 36px 64px; }}
  header h2 {{ margin: 0 0 4px; font-size: 1.6rem; }}
  header p {{ margin: 0 0 24px; color: var(--mute); }}
  article {{
    background: var(--card); border: 1px solid var(--line);
    border-radius: 8px; padding: 16px 18px; margin: 0 0 12px;
  }}
  article h3 {{ margin: 0 0 6px; font-size: 1.05rem; }}
  .sum {{ margin: 0 0 8px; }}
  .meta {{ margin: 0 0 10px; font-size: 12px; color: var(--mute); }}
  pre {{
    white-space: pre-wrap; font: 13px/1.4 ui-monospace, Menlo, monospace;
    color: #44403c; max-height: 9.5em; overflow: auto;
    background: #f6f3ee; padding: 10px; border-radius: 4px; margin: 0;
  }}
</style>
</head>
<body>
<nav>
  <p class="lede"><b>Original stitch, mapped.</b><br/>
  {total} posts · one home each (tightest pile).<br/>
  Green = topic. Rust = channel/year leftover.</p>
  {''.join(nav)}
</nav>
<main>
  {''.join(panes)}
</main>
<script>
  const buttons = [...document.querySelectorAll("button.nav")];
  const piles = [...document.querySelectorAll("section.pile")];
  function show(id) {{
    buttons.forEach((b) => b.classList.toggle("on", b.dataset.pile === id));
    piles.forEach((p) => {{ p.hidden = p.id !== "pile-" + id; }});
  }}
  buttons.forEach((b) => b.addEventListener("click", () => show(b.dataset.pile)));
  if (buttons[0]) show(buttons[0].dataset.pile);
</script>
</body>
</html>
""",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
