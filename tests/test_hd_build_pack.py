"""Tests for the HD pack build CLI helpers (temp dirs and synthetic bytes only)."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from hd.build_pack import cache_dir, check_disc, install, stage, write_progress


def make_pack(root: Path, marker: str) -> Path:
    target = root / "SCES-01000"
    target.mkdir()
    (target / marker).write_text("x")
    return target


class BuildPackTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_install_keeps_old_pack_when_build_fails(self) -> None:
        target = make_pack(self.tmp, "old")
        with self.assertRaises(OSError):
            install(self.tmp / "missing-staging", target)
        self.assertTrue((target / "old").exists())

    def test_install_replaces_pack(self) -> None:
        target = make_pack(self.tmp, "old")
        staging = self.tmp / "staging"
        staging.mkdir()
        (staging / "new").write_text("x")
        install(staging, target)
        self.assertEqual(sorted(p.name for p in target.iterdir()), ["new"])

    def test_stage_copies_only_current_files(self) -> None:
        out = self.tmp / "out"
        out.mkdir()
        (out / "keep.png").write_text("x")
        (out / "stale.png").write_text("x")
        stage(out, self.tmp / "staging", ["keep"])
        names = [p.name for p in (self.tmp / "staging" / "replacements").iterdir()]
        self.assertEqual(names, ["keep.png"])

    def test_cache_dir_changes_with_upscaler(self) -> None:
        self.assertNotEqual(cache_dir(self.tmp, "lanczos"), cache_dir(self.tmp, "m60"))

    def test_rejects_unknown_disc(self) -> None:
        with self.assertRaises(SystemExit):
            check_disc(b"\0" * 16)

    def test_progress_fraction(self) -> None:
        write_progress(self.tmp / "p.json", "upscale", 1, 4, "running")
        data = json.loads((self.tmp / "p.json").read_text())
        self.assertEqual(data["fraction"], 0.25)


if __name__ == "__main__":
    unittest.main()
