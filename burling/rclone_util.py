"""Thin rclone wrapper. Shared Drive I/O for the one-file stream reviewer.

Best practice: treat rclone as a subprocess, never as a Python Drive SDK. One
file at a time, so a bad export cannot fill the disk. `--auto-confirm` is
required on this Windows build or rclone waits on a hidden prompt.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from burling.paths import PROJECT_DIR


def rclone_bin(cfg: dict) -> Path:
    raw = (cfg.get("rclone") or {}).get("bin") or str(
        PROJECT_DIR / "tools" / "rclone" / "rclone.exe"
    )
    path = Path(raw)
    if not path.is_absolute():
        path = PROJECT_DIR / path
    if not path.is_file():
        raise FileNotFoundError(f"rclone not found: {path}")
    return path


def remote_name(cfg: dict) -> str:
    name = (cfg.get("rclone") or {}).get("remote") or "disd:"
    return name if name.endswith(":") else name + ":"


def rclone_run(cfg: dict, args: list[str], *, timeout: int = 600) -> subprocess.CompletedProcess:
    """Run rclone with the flags this Windows Drive remote needs."""
    cmd = [
        str(rclone_bin(cfg)),
        *args,
        "--auto-confirm",
        "--drive-acknowledge-abuse",
    ]
    return subprocess.run(
        cmd,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def list_remote_files(cfg: dict) -> list[str]:
    """Relative paths on the Shared Drive, POSIX-style, files only."""
    remote = remote_name(cfg)
    proc = rclone_run(
        cfg,
        ["lsf", remote, "--recursive", "--files-only", "--fast-list"],
        timeout=300,
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"rclone lsf failed: {err[:500]}")
    out = []
    for line in (proc.stdout or "").splitlines():
        rel = line.strip().replace("\\", "/")
        if not rel or rel.endswith("/"):
            continue
        # Browser "Save as HTML" dumps a sidecar folder of .js/.css. Skip those.
        if any(part.endswith("_files") for part in rel.split("/")):
            continue
        out.append(rel)
    return out


def _first_file(folder: Path) -> Path | None:
    files = [p for p in folder.rglob("*") if p.is_file()]
    return files[0] if files else None


def copy_one(cfg: dict, rel: str, dest_dir: Path) -> Path:
    """Download one Drive file into dest_dir. Returns the local path.

    ``copyto`` plus ``--drive-export-formats`` treats the source as a folder and
    fails with ``directory not found``. Binary uploads use plain ``copyto``.
    Native Google Docs/Sheets fall back to ``rclone copy`` of the parent folder
    with export formats (same as the original corpus pull).
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(rel).suffix
    dest = dest_dir / f"scratch{suffix}"
    remote = remote_name(cfg) + rel.replace("\\", "/")
    proc = rclone_run(
        cfg,
        ["copyto", remote, str(dest), "--retries", "1"],
        timeout=600,
    )
    if dest.is_file() and dest.stat().st_size > 0:
        return dest
    landed = _first_file(dest_dir)
    if landed is not None:
        return landed

    payload = dest_dir / "payload"
    payload.mkdir(exist_ok=True)
    parent = str(Path(rel).parent).replace("\\", "/")
    src = remote_name(cfg) if parent in {"", "."} else remote_name(cfg) + parent
    proc2 = rclone_run(
        cfg,
        [
            "copy",
            src,
            str(payload),
            "--include",
            f"/{Path(rel).name}",
            "--max-depth",
            "1",
            "--drive-export-formats",
            "pdf,docx,xlsx,csv",
            "--retries",
            "1",
        ],
        timeout=600,
    )
    exported = _first_file(payload)
    if exported is not None:
        return exported
    err = ((proc.stderr or proc.stdout or "") + "\n" + (proc2.stderr or proc2.stdout or "")).strip()
    raise RuntimeError(f"rclone copy failed for {rel}: {err[:500]}")


def trash_one(cfg: dict, rel: str) -> None:
    """Move one Drive file to trash. Caller decides; this does not check student records."""
    remote = remote_name(cfg) + rel
    proc = rclone_run(
        cfg,
        ["deletefile", remote, "--drive-use-trash=true", "--retries", "1"],
        timeout=120,
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"rclone deletefile failed for {rel}: {err[:500]}")
