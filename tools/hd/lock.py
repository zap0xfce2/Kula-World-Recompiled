#!/usr/bin/env python3
"""Pin the runner's packages with SHA-256 per platform: tools/hd/requirements/<set>-<platform>.txt.

    python3 tools/hd/lock.py

Needs uv (dev only): unlike pip, it evaluates dependency markers for the target
platform, not for the machine it runs on."""

import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "requirements"
PYTHON_VERSION = "3.12"
TORCH_CPU_INDEX = (
    "https://download.pytorch.org/whl/cpu"  # holds the +cpu wheels uv pins
)
BASE = ["pillow==13.0.0", "xxhash==4.0.2"]
MODEL = BASE + ["spandrel==0.4.1", "numpy", "torch==2.7.0"]
# Lock file platform: uv target. The CPU backend gives torch+cpu on Linux and Windows, PyPI torch (MPS) on macOS.
PLATFORMS = {
    "linux-x86_64": "x86_64-manylinux_2_28",
    "windows-x86_64": "x86_64-pc-windows-msvc",
    "macos-aarch64": "aarch64-apple-darwin",
}


def compile_lock(packages: list[str], target: str, out: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        wanted = Path(tmp) / "in.txt"
        wanted.write_text("\n".join(packages) + "\n")
        cmd = ["uv", "pip", "compile", "-q", str(wanted), "-o", str(out)]
        cmd += ["--python-version", PYTHON_VERSION, "--python-platform", target]
        cmd += ["--torch-backend", "cpu", "--generate-hashes", "--emit-index-url"]
        cmd += ["--no-header", "--no-annotate"]
        subprocess.run(cmd, check=True)
    text = out.read_text()
    if "+cpu" in text:  # pip drops an extra index that comes before --index-url
        index, rest = text.split("\n", 1)
        out.write_text(f"{index}\n--extra-index-url {TORCH_CPU_INDEX}\n{rest}")


def main() -> None:
    OUT.mkdir(exist_ok=True)
    for platform, target in PLATFORMS.items():
        for name, packages in (("base", BASE), ("model", MODEL)):
            compile_lock(packages, target, OUT / f"{name}-{platform}.txt")
            print(f"{name}-{platform}.txt")


if __name__ == "__main__":
    main()
