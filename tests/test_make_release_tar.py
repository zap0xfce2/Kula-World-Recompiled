"""Tests for the reproducible release tarball."""

import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from make_release_tar import FIXED_MTIME, write_tar


def stage_with_files(root: Path) -> Path:
    stage = root / "stage"
    (stage / "bios").mkdir(parents=True)
    (stage / "bios" / "openbios.bin").write_bytes(b"bios")
    exe = stage / "Kula_World_Rerolled"
    exe.write_bytes(b"elf")
    exe.chmod(0o700)
    return stage


class MakeReleaseTarTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.stage = stage_with_files(self.root)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def build(self, name: str) -> Path:
        out = self.root / name
        write_tar(self.stage, out)
        return out

    def member(self, name: str) -> tarfile.TarInfo:
        with tarfile.open(self.build("a.tar.gz")) as tar:
            return tar.getmember(name)

    def test_two_builds_are_identical(self) -> None:
        self.assertEqual(
            self.build("a.tar.gz").read_bytes(), self.build("b.tar.gz").read_bytes()
        )

    def test_executable_keeps_exec_bit(self) -> None:
        self.assertEqual(self.member("Kula_World_Rerolled").mode, 0o755)

    def test_plain_file_is_0644(self) -> None:
        self.assertEqual(self.member("bios/openbios.bin").mode, 0o644)

    def test_mtime_is_fixed(self) -> None:
        self.assertEqual(self.member("bios/openbios.bin").mtime, FIXED_MTIME)

    def test_owner_is_root(self) -> None:
        self.assertEqual(self.member("bios/openbios.bin").uid, 0)


if __name__ == "__main__":
    unittest.main()
