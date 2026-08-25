#!/usr/bin/env python3
"""Record a mute-safe LinkedIn walkthrough of the sample topic map.

Best practice: film docs/linkedin/topic-map.html, never compare/gb10.
LinkedIn video is watched muted, so captions on screen carry the story.
A drawn cursor stands in for the OS pointer, which Playwright does not film.

  python tools/build_linkedin_demo.py
  pip install playwright imageio-ffmpeg
  python -m playwright install chromium
  python tools/record_linkedin.py
"""

from __future__ import annotations

import math
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
HTML = PROJECT / "docs" / "linkedin" / "topic-map.html"
OUT = PROJECT / "docs" / "linkedin"
FRAMES = OUT / "frames"
VIDEO_DIR = OUT / "raw-video"

# 4:5 fills the LinkedIn feed. 16:9 leaves empty chrome on mobile.
W, H = 1080, 1350

INJECT_CSS = """
  html, body { overflow: hidden; }
  .page { width: calc(100% - 40px); padding: 28px 0 88px; }
  h1 { font-size: 40px !important; }
  .lede { max-width: 28rem; font-size: 15px !important; }
  .stats dd { font-size: 28px !important; }
  .stage { margin-top: 28px; padding-top: 18px; gap: 20px; grid-template-columns: minmax(0,1fr) 240px; }
  #sunburst { height: 520px !important; }
  .hint, footer { display: none !important; }

  #demo-cursor {
    position: fixed;
    z-index: 80;
    width: 22px;
    height: 22px;
    margin: -6px 0 0 -6px;
    border: 2px solid #f3ead8;
    background: #1a6fa8;
    pointer-events: none;
    transform: translate(-120px, -120px);
    box-shadow: 0 0 0 6px rgba(26, 111, 168, 0.28);
    transition: transform 40ms linear, width 80ms, height 80ms;
  }
  #demo-cursor.down { width: 14px; height: 14px; background: #f3ead8; }
  #demo-caption {
    position: fixed;
    left: 28px;
    right: 28px;
    bottom: 0;
    z-index: 70;
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding: 12px 4px 18px;
    border-top: 1px solid #1a4460;
    background: #07263d;
    pointer-events: none;
  }
  #demo-caption .kicker {
    font: 600 11px/1 "Source Sans 3", sans-serif;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: #1a6fa8;
  }
  #demo-caption .line {
    font: 400 24px/1.25 Newsreader, Georgia, serif;
    color: #f3ead8;
  }
  #demo-end {
    position: fixed;
    inset: 0;
    z-index: 90;
    display: none;
    flex-direction: column;
    justify-content: center;
    padding: 72px 56px;
    background: #07263d;
    color: #f3ead8;
  }
  #demo-end.on { display: flex; }
  #demo-end .eye {
    margin: 0 0 24px;
    font: 600 12px/1 "Source Sans 3", sans-serif;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: #8a8070;
  }
  #demo-end h2 {
    margin: 0 0 24px;
    font: 400 52px/1.08 Newsreader, Georgia, serif;
    letter-spacing: -0.02em;
  }
  #demo-end h2 em { font-style: italic; color: #1a6fa8; }
  #demo-end p {
    margin: 0 0 36px;
    max-width: 20em;
    font: 400 18px/1.5 "Source Sans 3", sans-serif;
    color: #c4b8a0;
  }
  #demo-end dl {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0;
    margin: 0;
    padding: 0;
    border-top: 1px solid #1a4460;
  }
  #demo-end div { padding: 16px 16px 0 0; }
  #demo-end dt {
    font: 600 10px/1 "Source Sans 3", sans-serif;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: #8a8070;
  }
  #demo-end dd {
    margin: 8px 0 0;
    font: 400 32px/1 Newsreader, Georgia, serif;
  }
"""

INJECT_JS = """
(() => {
  if (document.getElementById("demo-cursor")) return;
  const cur = document.createElement("div");
  cur.id = "demo-cursor";
  const cap = document.createElement("div");
  cap.id = "demo-caption";
  cap.innerHTML = '<span class="kicker">Burling</span><span class="line"></span>';
  const end = document.createElement("div");
  end.id = "demo-end";
  end.innerHTML = '<p class="eye">Burling · v2</p><h2>Drawers with <em>names</em>.</h2><p>Sub-categories come from an approved plan per series. The model picks from the menu - it does not invent. Off-plan files stay at the series level.</p><dl><div><dt>Files</dt><dd>68</dd></div><div><dt>Drawers</dt><dd>40</dd></div><div><dt>Invented</dt><dd>0</dd></div></dl>';
  document.body.append(cur, cap, end);
  window.__demo = {
    cursor(x, y, down) {
      cur.style.transform = "translate(" + x + "px," + y + "px)";
      cur.classList.toggle("down", !!down);
    },
    caption(kicker, line) {
      cap.querySelector(".kicker").textContent = kicker;
      cap.querySelector(".line").textContent = line;
    },
    end(on) { end.classList.toggle("on", !!on); },
  };
})();
"""


def ffmpeg_bin() -> str:
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        found = shutil.which("ffmpeg")
        if found:
            return found
    raise SystemExit("Need ffmpeg or pip install imageio-ffmpeg")


def slice_point(page, label: str):
    """Mid-arc of an SVG slice. Bounding-box center often misses the path."""
    return page.evaluate(
        """(label) => {
          const want = String(label || "").toLowerCase();
          const slice = [...document.querySelectorAll("#sunburst .slice")].find((el) => {
            const a = (el.getAttribute("data-label") || "").toLowerCase();
            return a === want || a.startsWith(want);
          });
          if (!slice || !slice.getTotalLength) return null;
          const len = slice.getTotalLength();
          const p = slice.getPointAtLength(len * 0.35);
          const svg = slice.ownerSVGElement;
          const pt = svg.createSVGPoint();
          pt.x = p.x; pt.y = p.y;
          const ctm = slice.getScreenCTM();
          if (!ctm) return null;
          const sp = pt.matrixTransform(ctm);
          return { x: sp.x, y: sp.y, id: slice.getAttribute("data-id") };
        }""",
        label,
    )


def hub_point(page):
    return page.evaluate(
        """() => {
          const c = document.querySelector("#sunburst .hub circle");
          if (!c) return null;
          const r = c.getBoundingClientRect();
          return { x: r.x + r.width / 2, y: r.y + r.height / 2 };
        }"""
    )


def move_cursor(page, x: float, y: float, steps: int = 18) -> None:
    start = page.evaluate(
        """() => {
          const el = document.getElementById("demo-cursor");
          const t = el.style.transform || "translate(0px, 0px)";
          const m = t.match(/translate\\(([\\-0-9.]+)px,\\s*([\\-0-9.]+)px\\)/);
          return m ? { x: +m[1], y: +m[2] } : { x: 80, y: 80 };
        }"""
    )
    for i in range(1, steps + 1):
        p = 0.5 - 0.5 * math.cos(math.pi * i / steps)
        cx = start["x"] + (x - start["x"]) * p
        cy = start["y"] + (y - start["y"]) * p
        page.evaluate("([x,y]) => window.__demo.cursor(x,y,false)", [cx, cy])
        page.mouse.move(cx, cy)
        page.wait_for_timeout(16)


def click_at(page, x: float, y: float) -> None:
    move_cursor(page, x, y)
    page.evaluate("([x,y]) => window.__demo.cursor(x,y,true)", [x, y])
    page.mouse.click(x, y)
    page.wait_for_timeout(120)
    page.evaluate("([x,y]) => window.__demo.cursor(x,y,false)", [x, y])


def dispatch_slice(page, label: str) -> bool:
    """Click the SVG path itself. Mouse coords miss thin arcs."""
    return bool(
        page.evaluate(
            """(label) => {
              const want = String(label || "").toLowerCase();
              const slice = [...document.querySelectorAll("#sunburst .slice")].find((el) => {
                const a = (el.getAttribute("data-label") || "").toLowerCase();
                return a === want || a.startsWith(want);
              });
              if (!slice) return false;
              slice.dispatchEvent(new MouseEvent("click", { bubbles: true }));
              return true;
            }""",
            label,
        )
    )


def click_label(page, label: str) -> bool:
    box = slice_point(page, label)
    if box:
        move_cursor(page, box["x"], box["y"])
        page.evaluate("([x,y]) => window.__demo.cursor(x,y,true)", [box["x"], box["y"]])
    ok = dispatch_slice(page, label)
    if box:
        page.wait_for_timeout(120)
        page.evaluate(
            "([x,y]) => window.__demo.cursor(x,y,false)", [box["x"], box["y"]]
        )
    if not ok:
        print("missing slice:", label, file=sys.stderr)
        return False
    page.wait_for_timeout(700)
    return True


def click_hub(page) -> None:
    box = hub_point(page)
    if box:
        move_cursor(page, box["x"], box["y"])
        page.evaluate("([x,y]) => window.__demo.cursor(x,y,true)", [box["x"], box["y"]])
    page.evaluate(
        """() => {
          const hub = document.querySelector("#sunburst .hub");
          if (hub) hub.dispatchEvent(new MouseEvent("click", { bubbles: true }));
        }"""
    )
    if box:
        page.wait_for_timeout(120)
        page.evaluate(
            "([x,y]) => window.__demo.cursor(x,y,false)", [box["x"], box["y"]]
        )
    page.wait_for_timeout(700)


def shot(page, name: str) -> Path:
    path = FRAMES / f"{name}.png"
    page.screenshot(path=str(path), type="png", animations="disabled")
    print("frame", path.name)
    return path


def caption(page, kicker: str, line: str) -> None:
    page.evaluate("([k,l]) => window.__demo.caption(k,l)", [kicker, line])


def wait_chart(page) -> None:
    page.wait_for_function(
        """() => document.querySelectorAll("#sunburst .slice").length > 3""",
        timeout=25000,
    )
    page.wait_for_timeout(800)


def record() -> Path:
    if not HTML.is_file():
        raise SystemExit(f"missing {HTML} — run tools/build_linkedin_demo.py first")
    leak = HTML.read_text(encoding="utf-8")
    if "Dallas ISD" in leak:
        raise SystemExit("sample map still branded Dallas ISD — rebuild the demo")
    FRAMES.mkdir(parents=True, exist_ok=True)
    if VIDEO_DIR.exists():
        shutil.rmtree(VIDEO_DIR)
    VIDEO_DIR.mkdir(parents=True)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": W, "height": H},
            device_scale_factor=1,
            record_video_dir=str(VIDEO_DIR),
            record_video_size={"width": W, "height": H},
        )
        page = context.new_page()
        page.goto(HTML.as_uri(), wait_until="domcontentloaded")
        wait_chart(page)
        page.add_style_tag(content=INJECT_CSS)
        page.evaluate(INJECT_JS)
        page.evaluate("() => window.__demo.cursor(180, 260, false)")
        page.mouse.move(180, 260)

        page.evaluate("() => window.__demo.end(true)")
        caption(page, "Burling", "Every drawer, on the plan.")
        page.wait_for_timeout(900)
        shot(page, "00-title")
        page.wait_for_timeout(1900)
        page.evaluate("() => window.__demo.end(false)")

        caption(page, "Sub-categories", "Series are only half the map. Open one.")
        clicked = click_label(page, "finance")
        if not clicked:
            click_label(page, "operations")
        page.wait_for_timeout(800)
        shot(page, "01-finance-drawers")
        page.wait_for_timeout(1700)

        caption(page, "Five drawers", "Budget. Invoices. Payroll. Reimbursements. Vendors.")
        page.wait_for_timeout(1600)
        shot(page, "02-finance-five")

        caption(page, "Drill again", "Click a drawer. The files open inside it.")
        click_label(page, "invoices")
        page.wait_for_timeout(700)
        shot(page, "03-invoices-files")
        page.wait_for_timeout(1800)

        caption(page, "Return", "Click the center. Back a level.")
        click_hub(page)
        page.wait_for_timeout(500)
        shot(page, "04-back-hub")
        page.wait_for_timeout(900)

        caption(page, "The plan", "Drawer names come from an approved plan - not guesswork.")
        click_label(page, "personnel")
        page.wait_for_timeout(800)
        shot(page, "05-personnel-plan")
        page.wait_for_timeout(1700)

        caption(page, "Same discipline", "Security: incidents, tickets, policies, credentials.")
        click_hub(page)
        page.wait_for_timeout(350)
        click_label(page, "security")
        page.wait_for_timeout(800)
        shot(page, "06-security")
        page.wait_for_timeout(1700)

        caption(page, "Burling", "A successor inherits drawers that all have names.")
        page.evaluate("() => window.__demo.end(true)")
        page.wait_for_timeout(800)
        shot(page, "07-endcard")
        page.wait_for_timeout(2200)

        video = page.video
        context.close()
        raw = Path(video.path()) if video else None
        browser.close()

    if not raw or not raw.exists():
        raw = next(VIDEO_DIR.glob("*.webm"))
    print("raw video", raw)
    return Path(raw)


def transcode(raw: Path) -> Path:
    mp4 = OUT / "subcategory-walkthrough.mp4"
    poster = FRAMES / "01-hero.png"
    cmd = [
        ffmpeg_bin(),
        "-y",
        "-i",
        str(raw),
        "-f",
        "lavfi",
        "-i",
        "anullsrc=channel_layout=stereo:sample_rate=48000",
        "-shortest",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-profile:v",
        "high",
        "-crf",
        "18",
        "-movflags",
        "+faststart",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        str(mp4),
    ]
    subprocess.run(cmd, check=True)
    if poster.is_file():
        shutil.copyfile(poster, OUT / "poster.png")
    print("mp4", mp4, mp4.stat().st_size)
    return mp4


def main() -> None:
    raw = record()
    transcode(raw)


if __name__ == "__main__":
    main()
