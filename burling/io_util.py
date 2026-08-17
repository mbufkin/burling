"""Small I/O helpers. Atomic replace is the Windows-safe way to write JSON/Markdown."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

# The live tracker reads these files every second while the run writes them.
# On Windows that briefly locks the path and os.replace raises WinError 5.
_RETRY_DELAYS = (0.05, 0.15, 0.4, 1.0, 2.0)


def atomic_write(path: Path, content: str) -> None:
    """Write via temp file + os.replace so a crash never leaves a half-written ledger.

    Path.rename() on Windows fails with WinError 183 if the destination exists.
    os.replace() is the portable overwrite. Retry PermissionError so the
    status watcher cannot fail a document mid-run.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    last: Exception | None = None
    for delay in (0.0, *_RETRY_DELAYS):
        if delay:
            time.sleep(delay)
        try:
            os.replace(tmp, path)
            return
        except PermissionError as exc:
            last = exc
    if last:
        raise last


def atomic_write_json(path: Path, data: object) -> None:
    atomic_write(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def load_json(path: Path, default: object) -> object:
    """Read JSON. Retry Windows file locks; a half-replaced file is retried."""
    if not path.exists():
        return default
    last: Exception | None = None
    for delay in (0.0, *_RETRY_DELAYS):
        if delay:
            time.sleep(delay)
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except PermissionError as exc:
            last = exc
        except json.JSONDecodeError as exc:
            last = exc
    if last:
        raise last
    return default
