"""Tests for the HD pack build CLI helpers (temp dirs and synthetic bytes only)."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from PIL import Image

from hd.assets import Clut, Pairing, Upload
from hd.build_pack import (
    cache_dir,
    check_disc,
    check_raw_image,
    image_of,
    install,
    stage,
    upscaler_for,
    write_progress,
)
from hd.upscale import lanczos4

MODEL_HASH = "ab" * 32


def fake_model(image: Image.Image) -> Image.Image:
    return lanczos4(image)


def tile(depth: int, width_words: int, height: int) -> Pairing:
    words = bytes(width_words * height * 2)
    return Pairing(
        Upload(0, 0, width_words, height, depth, words, "tile"),
        Clut(0, 0, bytes(2 << depth)),
    )


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
        stage(out, self.tmp / "staging", ["keep"], None)
        names = [p.name for p in (self.tmp / "staging" / "replacements").iterdir()]
        self.assertEqual(names, ["keep.png"])

    def test_marker_records_model_hash(self) -> None:
        out = self.tmp / "out"
        out.mkdir()
        (out / "keep.png").write_text("x")
        stage(out, self.tmp / "staging", ["keep"], MODEL_HASH)
        marker = json.loads((self.tmp / "staging" / "hd-pack.json").read_text())
        self.assertEqual(marker["model_sha256"], MODEL_HASH)

    def test_mipmaps_use_lanczos(self) -> None:
        self.assertIs(upscaler_for(tile(4, 8, 32), fake_model), lanczos4)

    def test_full_tiles_use_the_model(self) -> None:
        self.assertIs(upscaler_for(tile(8, 32, 64), fake_model), fake_model)

    def test_cache_dir_changes_with_upscaler(self) -> None:
        self.assertNotEqual(cache_dir(self.tmp, "lanczos"), cache_dir(self.tmp, "m60"))

    def test_image_of_unquoted_cue(self) -> None:
        cue = self.tmp / "game.cue"
        cue.write_text("FILE game.bin BINARY\n  TRACK 01 MODE2/2352\n")
        self.assertEqual(image_of(cue), self.tmp / "game.bin")

    def test_image_of_plain_bin(self) -> None:
        self.assertEqual(image_of(self.tmp / "game.bin"), self.tmp / "game.bin")

    def test_rejects_2048_byte_iso(self) -> None:
        iso = self.tmp / "game.iso"
        iso.write_bytes(bytes(16 * 2048 + 1) + b"CD001" + bytes(4096))
        with self.assertRaises(SystemExit):
            check_raw_image(iso)

    def test_rejects_unknown_disc(self) -> None:
        with self.assertRaises(SystemExit):
            check_disc(b"\0" * 16)

    def test_progress_fraction(self) -> None:
        write_progress(self.tmp / "p.json", "upscale", 1, 4, "running")
        data = json.loads((self.tmp / "p.json").read_text())
        self.assertEqual(data["fraction"], 0.25)


if __name__ == "__main__":
    unittest.main()
