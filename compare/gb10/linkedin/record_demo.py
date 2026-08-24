"""Record a LinkedIn walkthrough of the topic-map sunburst.

Best practice: LinkedIn video is watched muted. Captions carry the story.
A drawn cursor stands in for the OS pointer, which Playwright does not film.
"""

from __future__ import annotations

import math
import shutil
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path("/Users/michaelbufkin/Desktop/burling-v2/compare/gb10")
HTML = ROOT / "topic-map.html"
OUT = ROOT / "linkedin"
FRAMES = OUT / "frames"
VIDEO_DIR = OUT / "raw-video"
FFMPEG = "/Users/michaelbufkin/Library/Python/3.9/lib/python/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1"

# 4:5 fills the LinkedIn feed. 16:9 leaves empty chrome on mobile.
W, H = 1080, 1350

# Injected chrome — DISD editorial, not dashboard slop.
INJECT_CSS = """
  html, body { overflow: hidden; }
  .page { width: calc(100% - 40px); padding: 28px 0 88px; }
  h1 { font-size: 40px !important; }
  .lede { max-width: 28rem; font-size: 15px !important; }
  .stats dd { font-size: 28px !important; }
  .stage { margin-top: 28px; padding-top: 18px; gap: 20px; grid-template-columns: minmax(0,1fr) 240px; }
  #sunburst { height: 520px !important; }
  .hint, footer { display: none !important; }
  .js-plotly-plot .hoverlayer { display: none !important; }

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
    margin: 0 0 20px;
    font: 400 52px/1.08 Newsreader, Georgia, serif;
    letter-spacing: -0.02em;
  }
  #demo-end h2 em { font-style: italic; color: #1a6fa8; }
  #demo-end p {
    margin: 0 0 36px;
    max-width: 18em;
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
  cap.innerHTML = '<span class="kicker">Dallas ISD CTE</span><span class="line"></span>';
  const end = document.createElement("div");
  end.id = "demo-end";
  end.innerHTML = '<p class="eye">Dallas ISD · CTE handoff</p><h2>The dump, <em>organized</em>.</h2><p>28 documents placed on a governed map. Ring size is count — not importance.</p><dl><div><dt>Documents</dt><dd>28</dd></div><div><dt>Programs</dt><dd>12</dd></div><div><dt>Needs review</dt><dd>1</dd></div></dl>';
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


def label_box(page, label: str):
    """Viewport center of a sunburst label. None if Plotly hid it."""
    return page.evaluate(
        """(label) => {
          const gd = document.getElementById("sunburst");
          const want = label.toLowerCase();
          const t = [...gd.querySelectorAll("text")].find((el) => {
            const s = (el.textContent || "").trim().toLowerCase();
            return s === want || s.startsWith(want);
          });
          if (!t) return null;
          const r = t.getBoundingClientRect();
          if (r.width < 4 || r.height < 4) return null;
          return { x: r.x + r.width / 2, y: r.y + r.height / 2 };
        }""",
        label,
    )


def move_cursor(page, x: float, y: float, steps: int = 18) -> None:
    """Ease the drawn cursor and the real mouse together."""
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


def click_label(page, label: str) -> bool:
    box = label_box(page, label)
    if not box:
        print("missing label:", label, file=sys.stderr)
        return False
    click_at(page, box["x"], box["y"])
    page.wait_for_timeout(700)
    return True


def click_facet(page, name: str) -> None:
    loc = page.locator(f'button.facet[data-facet="{name}"]')
    box = loc.bounding_box()
    if not box:
        loc.click()
        return
    click_at(page, box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.wait_for_timeout(800)


def shot(page, name: str) -> Path:
    path = FRAMES / f"{name}.png"
    page.screenshot(path=str(path), type="png", animations="disabled")
    print("frame", path.name)
    return path


def caption(page, kicker: str, line: str) -> None:
    page.evaluate("([k,l]) => window.__demo.caption(k,l)", [kicker, line])


def pin_brief(page, kind: str, needle: str) -> None:
    """Force the side brief so the video shows the handoff, not the idle card."""
    page.evaluate(
        """([kind, needle]) => {
          const n = needle.toLowerCase();
          const gd = document.getElementById("sunburst");
          if (gd && gd.removeAllListeners) gd.removeAllListeners("plotly_unhover");
          for (const fig of Object.values(FIGURES)) {
            for (const raw of fig.customdata) {
              let m = raw;
              if (typeof raw === "string") {
                try { m = JSON.parse(raw); } catch (e) { continue; }
              }
              const hay = [m.title, m.ring, m.term, (m.files || []).join(" ")]
                .join(" ")
                .toLowerCase();
              if (m.kind === kind && hay.includes(n)) {
                renderBrief(m);
                return m.title;
              }
            }
          }
        }""",
        [kind, needle],
    )


def wait_chart(page) -> None:
    page.wait_for_function(
        """() => typeof Plotly !== "undefined"
          && document.querySelectorAll("#sunburst g.slice").length > 3""",
        timeout=25000,
    )
    page.wait_for_timeout(800)


def record() -> Path:
    FRAMES.mkdir(parents=True, exist_ok=True)
    if VIDEO_DIR.exists():
        shutil.rmtree(VIDEO_DIR)
    VIDEO_DIR.mkdir(parents=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
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
        page.evaluate(
            """() => {
              const gd = document.getElementById("sunburst");
              if (gd && window.Plotly) Plotly.relayout(gd, { hovermode: false });
            }"""
        )
        page.evaluate("() => window.__demo.cursor(180, 260, false)")
        page.mouse.move(180, 260)

        # 0. Title card — first three seconds matter on LinkedIn
        page.evaluate("() => window.__demo.end(true)")
        caption(page, "Dallas ISD CTE", "Watch the map work.")
        page.wait_for_timeout(900)
        shot(page, "00-title")
        page.wait_for_timeout(1800)
        page.evaluate("() => window.__demo.end(false)")

        # 1. Hero — title, stats, and the ring in one frame
        caption(page, "Dallas ISD CTE", "28 documents. One governed map.")
        page.wait_for_timeout(1800)
        shot(page, "01-hero")
        page.wait_for_timeout(1200)

        caption(page, "Program", "Ring size is count — not importance.")
        page.wait_for_timeout(1400)
        shot(page, "02-programs")

        # 2. Open the largest program
        caption(page, "Drill in", "Click a program. The files open.")
        click_label(page, "showcase events")
        pin_brief(page, "term", "showcase")
        page.wait_for_timeout(700)
        shot(page, "03-showcase-files")
        page.wait_for_timeout(1800)

        # 3. Read a file slice
        caption(page, "Handoff", "Each slice carries the note the successor needs.")
        clicked = click_label(page, "Parking") or click_label(page, "Showcase Invite List")
        if not clicked:
            click_label(page, "Career Exploration")
        pin_brief(page, "doc", "parking.pptx")
        page.wait_for_timeout(600)
        shot(page, "04-file-brief")
        page.wait_for_timeout(2000)

        # 4. Back to the map
        caption(page, "Return", "Click the center. The map closes.")
        click_label(page, "showcase events") or click_label(page, "by program")
        pin_brief(page, "term", "showcase")
        page.wait_for_timeout(500)
        shot(page, "05-back")
        page.wait_for_timeout(1000)

        # 5. Same documents, different cut
        caption(page, "Facet", "Same documents. A different cut.")
        click_facet(page, "function")
        page.wait_for_timeout(600)
        shot(page, "06-function")
        page.wait_for_timeout(1400)

        click_label(page, "meeting deck") or click_label(page, "course overview")
        pin_brief(page, "term", "meeting deck")
        page.wait_for_timeout(600)
        shot(page, "07-function-files")
        page.wait_for_timeout(1800)

        click_facet(page, "audience")
        page.wait_for_timeout(500)
        shot(page, "08-audience")
        page.wait_for_timeout(1400)

        # 6. End card
        caption(page, "Burling", "Taxonomy first. Then the successor can see.")
        page.evaluate("() => window.__demo.end(true)")
        page.wait_for_timeout(800)
        shot(page, "09-endcard")
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
    mp4 = OUT / "topic-map-walkthrough.mp4"
    cmd = [
        FFMPEG,
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
    print("mp4", mp4, mp4.stat().st_size)
    return mp4


def main() -> None:
    raw = record()
    transcode(raw)


if __name__ == "__main__":
    main()
