"""Tests for the background runner (temp dirs and file:// URLs only, no network)."""

import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from hd.hd_auto import (
    Failed,
    Progress,
    Steps,
    download,
    needs_build,
    run_phases,
    current_marker,
    single_instance,
    tool_version,
)
from hd.build_pack import TOOL_VERSION

WANT = {"tool": 7, "upscaler": "m60", "model_sha256": "ab" * 32}


def ignore(_fraction: float) -> None:
    pass


def fallback_steps(built: list[Path | None]) -> Steps:
    def no_model() -> Path:
        raise Failed("network", "offline")

    return Steps(
        python=lambda: Path("python3"),
        packages=lambda _py, _with_model: None,
        model=no_model,
        build=lambda _py, model: built.append(model),
    )


class AutoTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp)

    def write_marker(self, marker: dict) -> Path:
        pack = self.tmp / "SCES-01000"
        pack.mkdir()
        (pack / "hd-pack.json").write_text(json.dumps(marker))
        return pack

    def test_progress_fraction_counts_finished_phases(self) -> None:
        Progress(self.tmp / "p.json").set("model", 0.5)
        data = json.loads((self.tmp / "p.json").read_text())
        self.assertAlmostEqual(data["fraction"], round((0.3 + 1.5 + 0.2) / 100, 4))

    def test_download_rejects_checksum_mismatch(self) -> None:
        source = self.tmp / "source.bin"
        source.write_bytes(b"data")
        with self.assertRaises(Failed) as ctx:
            download(source.as_uri(), self.tmp / "dst.bin", "0" * 64, ignore)
        self.assertEqual(ctx.exception.code, "download")

    def test_download_keeps_verified_file(self) -> None:
        dst = self.tmp / "dst.bin"
        dst.write_bytes(b"data")
        digest = hashlib.sha256(b"data").hexdigest()
        missing = (self.tmp / "missing.bin").as_uri()
        self.assertEqual(download(missing, dst, digest, ignore), dst)

    def test_needs_build_when_marker_differs(self) -> None:
        pack = self.write_marker(dict(WANT, upscaler="lanczos"))
        self.assertTrue(needs_build(pack, WANT))

    def test_no_build_when_marker_matches(self) -> None:
        self.assertFalse(needs_build(self.write_marker(WANT), WANT))

    def test_needs_build_without_pack(self) -> None:
        self.assertTrue(needs_build(self.tmp / "missing", WANT))

    def test_second_instance_exits(self) -> None:
        first = single_instance(self.tmp)
        self.addCleanup(first.close)
        self.assertIsNone(single_instance(self.tmp))

    def test_tool_version_read_from_builder_source(self) -> None:
        self.assertEqual(tool_version(), TOOL_VERSION)

    def test_model_failure_falls_back_to_lanczos(self) -> None:
        built: list[Path | None] = []
        run_phases(True, fallback_steps(built))
        self.assertEqual(built, [None])

    def test_build_failure_with_model_retries_without(self) -> None:
        built: list[Path | None] = []

        def build(_py: Path, model: Path | None) -> None:
            built.append(model)
            if model:
                raise Failed("failed", "MPS op missing")

        steps = Steps(
            python=lambda: Path("python3"),
            packages=lambda _py, _with_model: None,
            model=lambda: Path("model.pth"),
            build=build,
        )
        run_phases(True, steps)
        self.assertEqual(built, [Path("model.pth"), None])

    def test_current_marker_names_the_model(self) -> None:
        self.assertEqual(current_marker(True)["upscaler"], "m60")

    def test_current_marker_without_model_is_lanczos(self) -> None:
        self.assertIsNone(current_marker(False)["model_sha256"])

    def test_model_failure_is_reported(self) -> None:
        self.assertEqual(run_phases(True, fallback_steps([])), "network")


if __name__ == "__main__":
    unittest.main()
