# LinkedIn walkthrough (sample corpus)

4:5 H.264, ~35 seconds, captions on screen (mute-safe).

**Do not film `compare/gb10` or any live dump.** The public cut uses
`burling/tests/fixtures/organize-drama` only.

## Post these

| File | Use |
|---|---|
| `topic-map-walkthrough.mp4` | Native LinkedIn video |
| `poster.png` | Thumbnail if LinkedIn asks |
| `LINKEDIN-CAPTION.txt` | Paste as the post |

## Rebuild

```bash
python tools/build_linkedin_demo.py
pip install playwright imageio-ffmpeg
python -m playwright install chromium
python tools/record_linkedin.py
```

`--model` on the builder runs a real local `--walk` instead of the gold clerk.
Review the frames before posting: no Dallas ISD chrome, no live filenames.
