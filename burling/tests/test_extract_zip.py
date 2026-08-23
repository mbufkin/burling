"""Safe zip unpack + inventory. No model."""

from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from burling.extract import (
    extract_text,
    iter_source_files,
    safe_unpack_zip,
)


class SafeUnpackZipTests(unittest.TestCase):
    def test_unpacks_members_and_blocks_zip_slip(self) -> None:
        # Best practice: never write `../` members outside dest (zip slip).
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            zpath = root / "bundle.zip"
            with zipfile.ZipFile(zpath, "w") as zf:
                zf.writestr("inner/notes.md", "# CTE notes\nTrailer visit checklist.\n")
                zf.writestr("../escape.txt", "should not land outside dest")
            dest = root / "bundle.zip.unpacked"
            written = safe_unpack_zip(zpath, dest)
            self.assertTrue(any(p.name == "notes.md" for p in written))
            self.assertFalse((root / "escape.txt").exists())
            self.assertFalse(any("escape" in p.name for p in written))

    def test_iter_source_files_replaces_zip_with_members(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            intake = Path(tmp)
            zpath = intake / "handoff.zip"
            with zipfile.ZipFile(zpath, "w") as zf:
                zf.writestr("a.md", "enough text for a real extract here.\n")
                zf.writestr("b.txt", "second member also has enough text.\n")
            files = iter_source_files(intake)
            names = sorted(p.name for p in files)
            self.assertIn("a.md", names)
            self.assertIn("b.txt", names)
            self.assertNotIn("handoff.zip", names)

    def test_zip_itself_is_no_longer_unreadable(self) -> None:
        # After unpack, extract_text on a leftover zip still explains itself.
        with tempfile.TemporaryDirectory() as tmp:
            zpath = Path(tmp) / "empty.zip"
            with zipfile.ZipFile(zpath, "w"):
                pass
            with self.assertRaises(ValueError) as ctx:
                extract_text(zpath)
            self.assertIn("zip", str(ctx.exception).lower())


if __name__ == "__main__":
    unittest.main()
