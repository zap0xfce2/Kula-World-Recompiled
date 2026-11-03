#!/usr/bin/env python3
"""Build the HD pack in the background from the player's disc (the launcher's job).

    python3 tools/hd/hd_auto.py --disc GAME.cue --pack mods/texture-packs/SCES-01000
                                --data hd-auto [--with-model] [--python PY]
                                [--device DEV] [--parent-pid PID]

Standard library only: it sets up what the build needs below --data, each piece
from its official source and checked against a fixed SHA-256:

  python    portable CPython 3.12 (astral-sh/python-build-standalone)
  packages  tools/hd/requirements/<base|model>-<platform>.txt (tools/hd/lock.py)
  model     IllustrationJaNai V1 DAT2, only with --with-model (the player's
            consent: its licence, CC BY-NC-SA, does not allow us to ship it)
  build     tools/hd/build_pack.py, installed atomically to --pack

Without the model (no consent, offline, download failed) it builds the Lanczos
pack; a later run with the model replaces it. --python names a Python that
already has the packages and skips the first two steps. Every step resumes.
--data/progress.json is what the launcher shows:
{"phase", "fraction", "eta", "state": running|done|failed, "error", "updated"}.
Adapted from Hercules Recompiled port/hd/hd_auto.py, without its pack download.
"""

# Bootstrap Pythons may be older than 3.10 (macOS ships 3.9): keep annotations lazy.
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import signal
import ssl
import subprocess
import sys
import tarfile
import threading
import time
import urllib.error
import urllib.request
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import IO

HERE = Path(__file__).resolve().parent
BUILDER = HERE / "build_pack.py"
LOCKS = HERE / "requirements"
WIN = os.name == "nt"

PBS = "https://github.com/astral-sh/python-build-standalone/releases/download/20260825/"
PYTHON_TARBALLS = {
    "linux-x86_64": (
        "cpython-3.12.14%2B20260825-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz",
        "7ce4a71285d913955a76053cc7605ea96da8ecada54dba9cf395245961816421",
    ),
    "windows-x86_64": (
        "cpython-3.12.14%2B20260825-x86_64-pc-windows-msvc-install_only_stripped.tar.gz",
        "8e6aad12ef6fc9685e67ce66253f8f72d6e8fa02cb7187e5850bd4db5ecd9e2a",
    ),
    "macos-aarch64": (
        "cpython-3.12.14%2B20260825-aarch64-apple-darwin-install_only_stripped.tar.gz",
        "8b0f1fa71eab7ca644e482c631807a1116fa848491051cd1c8d9429491de63a6",
    ),
}
MODEL_ZIP = (
    "https://github.com/the-database/MangaJaNai/releases/download/1.0.0/"
    "IllustrationJaNai_V1_ModelsOnly.zip",
    "6f5496f5ded597474290403de73d7a46c3f8ed328261db2e6ff830a415a6f60b",
)
MODEL_MEMBER = "4x_IllustrationJaNai_V1_DAT2_190k.pth"
MODEL_SHA256 = "a82f3a2d8d1c676171b86a00048b7a624e3c62c87ec701012f106a171c309fbe"

# share of the whole run; the build itself takes hours on a CPU
PHASES = [("python", 0.3), ("packages", 1.5), ("model", 0.4), ("build", 97.8)]
FALLBACK_CODES = {"network", "download"}  # model unavailable: build Lanczos instead
FREE_GB = {True: 6, False: 3}  # with/without model: python + packages, work, pack
TOOL_VERSION_LINE = re.compile(r"^TOOL_VERSION = (\d+)$", re.MULTILINE)
CHUNK = 1 << 20
ETA_WARMUP, ETA_WINDOW, ETA_MIN_SPAN = 180, 900, 120  # seconds
POLL_SECONDS = 3
PIP_RAMP_SECONDS = 600
NO_WINDOW = 0x08000000 if WIN else 0  # CREATE_NO_WINDOW
BELOW_NORMAL_PRIORITY = 0x4000
NICE_LOWEST = 19
CA_BUNDLES = (
    "/etc/ssl/certs/ca-certificates.crt",
    "/etc/pki/tls/certs/ca-bundle.crt",
    "/etc/ssl/ca-bundle.pem",
    "/etc/ssl/cert.pem",
)
SYNCHRONIZE = 0x00100000
WAIT_TIMEOUT = 0x102
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9


class Failed(Exception):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code


@dataclass
class Steps:
    python: Callable[[], Path]
    packages: Callable[[Path, bool], None]
    model: Callable[[], Path]
    build: Callable[[Path, Path | None], None]


class Progress:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.phase, self.part = "", 0.0

    def set(
        self,
        phase: str,
        part: float = 0.0,
        eta: int | None = None,
        state: str = "running",
        error: str | None = None,
    ) -> None:
        self.phase, self.part = phase, part
        names = [name for name, _ in PHASES]
        before = sum(w for _, w in PHASES[: names.index(phase)])
        total = sum(w for _, w in PHASES)
        fraction = (
            1.0
            if state == "done"
            else min(1.0, (before + dict(PHASES)[phase] * part) / total)
        )
        data = {
            "phase": phase,
            "fraction": round(fraction, 4),
            "eta": eta,
            "state": state,
            "error": error,
            "updated": int(time.time()),
        }
        tmp = self.path.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(data))
            tmp.replace(self.path)
        except OSError:  # Windows: the launcher has it open; the next write wins
            pass


def log(message: str) -> None:
    print(time.strftime("%H:%M:%S ") + message, flush=True)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ssl_context() -> ssl.SSLContext:
    """Bundled Pythons may not find the system CA store on their own."""
    context = ssl.create_default_context()
    if WIN or context.get_ca_certs():
        return context
    for bundle in CA_BUNDLES:
        if os.path.exists(bundle):
            context.load_verify_locations(bundle)
            break
    return context


def fetch(url: str, part: Path, report: Callable[[float], None]) -> None:
    request = urllib.request.Request(
        url, headers={"User-Agent": "kula-world-recompiled-hd"}
    )
    try:
        with urllib.request.urlopen(
            request, timeout=60, context=ssl_context()
        ) as response, open(part, "wb") as f:
            total, got = int(response.headers.get("Content-Length") or 0), 0
            while chunk := response.read(CHUNK):
                f.write(chunk)
                got += len(chunk)
                if total:
                    report(got / total)
    except OSError as error:
        raise Failed("network", f"{url}: {error}") from error


def download(url: str, dst: Path, digest: str, report: Callable[[float], None]) -> Path:
    """url to dst, checked; a verified file from an earlier run is kept."""
    if dst.exists() and sha256(dst) == digest:
        return dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    part = dst.with_name(dst.name + ".part")
    log(f"download {url}")
    fetch(url, part, report)
    if sha256(part) != digest:
        part.unlink()
        raise Failed("download", f"{url}: checksum mismatch")
    part.replace(dst)
    return dst


def platform_key() -> str:
    machine = platform.machine().lower()
    if sys.platform == "win32" and machine in ("amd64", "x86_64"):
        return "windows-x86_64"
    if sys.platform == "darwin" and machine == "arm64":
        return "macos-aarch64"
    if (
        sys.platform == "linux"
        and machine == "x86_64"
        and platform.libc_ver()[0] == "glibc"
    ):
        return "linux-x86_64"
    raise Failed(
        "platform", f"{sys.platform} {machine}: no portable Python, use --python"
    )


def tool_version() -> int:
    match = TOOL_VERSION_LINE.search(BUILDER.read_text(encoding="utf-8"))
    if not match:
        raise Failed("failed", "TOOL_VERSION not found in build_pack.py")
    return int(match[1])


def needs_build(pack: Path, want: dict) -> bool:
    try:
        return json.loads((pack / "hd-pack.json").read_text()) != want
    except (OSError, ValueError):
        return True


def setup_model(py: Path, steps: Steps) -> tuple[Path | None, str | None]:
    try:
        steps.packages(py, True)
        return steps.model(), None
    except Failed as failure:
        if failure.code not in FALLBACK_CODES:
            raise
        log(f"model unavailable ({failure}), building the Lanczos pack")
        return None, failure.code


def run_phases(with_model: bool, steps: Steps) -> str | None:
    """All phases; returns the error code when the model was given up for Lanczos."""
    py = steps.python()
    model, error = setup_model(py, steps) if with_model else (None, None)
    if model is None:
        steps.packages(py, False)
    try:
        steps.build(py, model)
    except Failed as failure:
        if model is None:
            raise
        # An unsupported op or too little memory must not cost the player the whole pack.
        log(f"build with the model failed ({failure}), building the Lanczos pack")
        steps.build(py, None)
        error = "model"
    return error


def phase_python(data: Path, prog: Progress) -> Path:
    root = data / "python"
    exe = root / ("python/python.exe" if WIN else "python/bin/python3")
    if (root / ".ok").exists() and exe.exists():
        return exe
    prog.set("python")
    name, digest = PYTHON_TARBALLS[platform_key()]
    target = data / "downloads" / name.replace("%2B", "+")
    tar = download(PBS + name, target, digest, lambda f: prog.set("python", 0.9 * f))
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True)
    with tarfile.open(tar) as archive:
        if hasattr(tarfile, "data_filter"):  # 3.12, or 3.9.17+ backports
            archive.extractall(root, filter="data")
        else:  # the tarball is hash-checked above
            archive.extractall(root)
    (root / ".ok").touch()
    return exe


def phase_packages(
    py: Path, with_model: bool, data: Path, prog: Progress, logf: IO[str]
) -> None:
    lock = LOCKS / f"{'model' if with_model else 'base'}-{platform_key()}.txt"
    stamp = data / "python" / f".packages-{lock.stem}"
    if stamp.exists() and stamp.read_text() == sha256(lock):
        return
    prog.set("packages")
    cmd = [
        py,
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "--no-input",
        "--no-cache-dir",
        "--progress-bar",
        "off",
        "--require-hashes",
        "--only-binary=:all:",
        "-r",
        lock,
    ]
    process = run(cmd, logf)
    started = time.time()
    while process.poll() is None:  # pip gives no byte count: a slow ramp
        prog.set("packages", min(0.95, (time.time() - started) / PIP_RAMP_SECONDS))
        time.sleep(POLL_SECONDS)
    if process.returncode:
        raise Failed("network", f"pip install ended with {process.returncode}")
    stamp.write_text(sha256(lock))


def phase_model(data: Path, prog: Progress) -> Path:
    out = data / "model" / MODEL_MEMBER
    if out.exists() and sha256(out) == MODEL_SHA256:
        return out
    prog.set("model")
    url, digest = MODEL_ZIP
    archive = download(
        url,
        data / "downloads" / url.rsplit("/", 1)[1],
        digest,
        lambda f: prog.set("model", f),
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(archive) as zf, zf.open(MODEL_MEMBER) as src, open(
            out, "wb"
        ) as f:
            shutil.copyfileobj(src, f)
    except (
        KeyError,
        zipfile.BadZipFile,
    ) as error:  # a re-packed zip must not cost the pack
        raise Failed("download", f"{MODEL_MEMBER}: {error}") from error
    if sha256(out) != MODEL_SHA256:
        out.unlink()
        raise Failed("download", f"{MODEL_MEMBER}: checksum mismatch")
    return out


def run(cmd: list, logf: IO[str], env: dict | None = None) -> subprocess.Popen:
    log("run " + " ".join(map(str, cmd)))
    return subprocess.Popen(
        [str(c) for c in cmd],
        stdout=logf,
        stderr=subprocess.STDOUT,
        creationflags=NO_WINDOW,
        env=env,
    )


def cpu_env() -> dict:
    """One core stays for the game; no thread pinning (the game shares the cores)."""
    threads = str(max(1, (os.cpu_count() or 2) - 1))
    return dict(
        os.environ,
        OMP_NUM_THREADS=threads,
        MKL_NUM_THREADS=threads,
        KMP_AFFINITY="disabled",
        PYTORCH_ENABLE_MPS_FALLBACK="1",  # ops MPS lacks run on the CPU instead of failing
        PYTHONUTF8="1",
    )


def current_marker(with_model: bool) -> dict[str, int | str | None]:
    """What hd-pack.json says for a pack of this tool; the model is pinned by its SHA-256."""
    return {
        "tool": tool_version(),
        "upscaler": "m60" if with_model else "lanczos",
        "model_sha256": MODEL_SHA256 if with_model else None,
    }


def eta(samples: list[tuple[float, float]], fraction: float) -> int | None:
    """Remaining seconds from the pace of the last minutes; a resumed run first skips done work."""
    if len(samples) < 2 or samples[-1][0] - samples[0][0] < ETA_MIN_SPAN:
        return None
    (t0, f0), (t1, f1) = samples[0], samples[-1]
    return int((1 - fraction) / ((f1 - f0) / (t1 - t0))) if f1 > f0 else None


def build_command(
    py: Path, model: Path | None, args: argparse.Namespace, data: Path
) -> list:
    cmd = [
        py,
        "-I",
        BUILDER,
        args.disc,
        data / "work",
        "--install",
        args.pack,
        "--progress",
        data / "build.progress.json",
    ]
    if model:
        cmd += ["--model", model] + (["--device", args.device] if args.device else [])
    return cmd


def phase_build(
    py: Path,
    model: Path | None,
    args: argparse.Namespace,
    data: Path,
    prog: Progress,
    logf: IO[str],
) -> None:
    if not needs_build(args.pack, current_marker(model is not None)):
        log("pack is up to date")
        return
    prog.set("build")
    watch = data / "build.progress.json"
    process = run(build_command(py, model, args, data), logf, cpu_env())
    started, samples = time.time(), []
    while process.poll() is None:
        try:
            fraction = float(json.loads(watch.read_text()).get("fraction") or 0)
        except (OSError, ValueError):
            fraction = None
        now = time.time()
        if fraction is not None:
            if now - started > ETA_WARMUP:
                samples = [s for s in samples if now - s[0] <= ETA_WINDOW] + [
                    (now, fraction)
                ]
            prog.set("build", fraction, eta(samples, fraction))
        time.sleep(POLL_SECONDS)
    if process.returncode:
        raise Failed("failed", f"build_pack ended with {process.returncode}")


def lower_priority() -> None:
    try:
        if WIN:
            import ctypes  # noqa: PLC0415 - Windows only

            kernel = ctypes.windll.kernel32
            kernel.SetPriorityClass(kernel.GetCurrentProcess(), BELOW_NORMAL_PRIORITY)
        else:
            os.nice(NICE_LOWEST)
    except (OSError, AttributeError):
        pass


def tie_children() -> None:
    """Children die with this process: own process group, or a kill-on-close job on Windows."""
    if not WIN:
        try:
            os.setpgrp()
        except OSError:
            pass
        return
    try:
        windows_kill_on_close_job()
    except (OSError, AttributeError):
        pass


def windows_kill_on_close_job() -> None:
    import ctypes  # noqa: PLC0415 - Windows only
    from ctypes import wintypes  # noqa: PLC0415

    class Basic(ctypes.Structure):
        _fields_ = [
            ("a", ctypes.c_int64),
            ("b", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD),
            ("c", ctypes.c_size_t),
            ("d", ctypes.c_size_t),
            ("e", wintypes.DWORD),
            ("f", ctypes.c_size_t),
            ("g", wintypes.DWORD),
            ("h", wintypes.DWORD),
        ]

    class Extended(ctypes.Structure):
        _fields_ = [
            ("Basic", Basic),
            ("Io", ctypes.c_uint64 * 6),
            ("p", ctypes.c_size_t),
            ("j", ctypes.c_size_t),
            ("pp", ctypes.c_size_t),
            ("pj", ctypes.c_size_t),
        ]

    kernel = ctypes.windll.kernel32
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    job = kernel.CreateJobObjectW(None, None)
    info = Extended()
    info.Basic.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    kernel.SetInformationJobObject(
        wintypes.HANDLE(job),
        JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
        ctypes.byref(info),
        ctypes.sizeof(info),
    )
    kernel.AssignProcessToJobObject(
        wintypes.HANDLE(job), wintypes.HANDLE(kernel.GetCurrentProcess())
    )
    tie_children.job = (
        job  # the job ends, and kills its children, when this handle closes
    )


def stop_all(*_: object) -> None:
    """The process group gets SIGTERM; on Windows exiting closes the job (tie_children)."""
    if not WIN:
        if threading.current_thread() is threading.main_thread():
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
        try:
            os.killpg(0, signal.SIGTERM)
        except OSError:
            pass
    os._exit(3)


def windows_process_alive(pid: int) -> bool:
    import ctypes  # noqa: PLC0415 - Windows only

    kernel = ctypes.windll.kernel32
    handle = kernel.OpenProcess(SYNCHRONIZE, False, pid)
    if not handle:
        return False
    result = kernel.WaitForSingleObject(handle, 0)
    kernel.CloseHandle(handle)
    return result == WAIT_TIMEOUT


def parent_alive(pid: int) -> bool:
    # On Windows os.kill(pid, 0) sends CTRL_C_EVENT instead of probing.
    if WIN:
        return windows_process_alive(pid)
    # not getppid(): SDL starts background processes through a double fork
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        pass
    return True


def stopper(prog: Progress, stop: Callable[[], None] = stop_all) -> Callable[..., None]:
    """Without the mark the launcher would read a dead build as still running."""

    def stopped(*_: object) -> None:
        prog.set(prog.phase or "python", prog.part, state="stopped")
        stop()

    return stopped


def watch_parent(pid: int, stop: Callable[[], None]) -> None:
    def loop() -> None:
        while parent_alive(pid):
            time.sleep(2)
        log("launcher gone, stopping")
        stop()

    threading.Thread(target=loop, daemon=True).start()


def single_instance(data: Path) -> IO[str] | None:
    handle = open(data / "hd.lock", "a+")
    try:
        if WIN:
            import msvcrt  # noqa: PLC0415 - Windows only

            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl  # noqa: PLC0415 - POSIX only

            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return None
    return handle


def detach(args: argparse.Namespace, prog: Progress) -> None:
    tie_children()
    stop = stopper(prog)
    if not WIN:
        signal.signal(signal.SIGTERM, stop)
    lower_priority()
    if args.parent_pid:
        watch_parent(args.parent_pid, stop)


def real_steps(
    args: argparse.Namespace, data: Path, prog: Progress, logf: IO[str]
) -> Steps:
    def packages(py: Path, with_model: bool) -> None:
        if not args.python:
            phase_packages(py, with_model, data, prog, logf)

    return Steps(
        python=lambda: args.python or phase_python(data, prog),
        packages=packages,
        model=lambda: phase_model(data, prog),
        build=lambda py, model: phase_build(py, model, args, data, prog, logf),
    )


def check_space(args: argparse.Namespace, data: Path) -> None:
    free = shutil.disk_usage(data).free / 2**30
    if free < FREE_GB[args.with_model]:
        raise Failed("disk", f"{free:.1f} GB free, {FREE_GB[args.with_model]} needed")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--disc", type=Path, required=True)
    parser.add_argument("--pack", type=Path, required=True, help="texture pack folder")
    parser.add_argument(
        "--data", type=Path, required=True, help="work folder (GBs while it runs)"
    )
    parser.add_argument(
        "--with-model",
        action="store_true",
        help="the player accepted the model licence",
    )
    parser.add_argument(
        "--python", type=Path, help="a Python that already has the packages"
    )
    parser.add_argument("--device", help="cpu, mps or cuda for the model")
    parser.add_argument("--parent-pid", type=int)
    return parser.parse_args()


def cleanup(data: Path) -> None:
    """The model stays, so a later run does not download it again."""
    for name in ("downloads", "python", "work"):
        shutil.rmtree(data / name, ignore_errors=True)


def build_if_needed(
    args: argparse.Namespace, data: Path, prog: Progress, logf: IO[str]
) -> str | None:
    """Checked before any setup: a launcher start with a current pack costs nothing."""
    if not args.disc.exists():
        raise Failed("disc", str(args.disc))
    if not needs_build(args.pack, current_marker(args.with_model)):
        log("pack is up to date")
        return None
    check_space(args, data)
    return run_phases(args.with_model, real_steps(args, data, prog, logf))


def main() -> int:
    args = parse_args()
    data = args.data.resolve()
    data.mkdir(parents=True, exist_ok=True)
    lock = single_instance(data)
    if lock is None:
        return 0  # already running
    logf = open(data / "hd-build.log", "a", buffering=1, encoding="utf-8")
    sys.stdout = sys.stderr = logf
    prog = Progress(data / "progress.json")
    detach(args, prog)
    log(f"HD build: disc {args.disc}, pack {args.pack}, model {args.with_model}")
    try:
        error = build_if_needed(args, data, prog, logf)
    except Failed as failure:
        log(f"failed: {failure}")
        prog.set(prog.phase or "python", prog.part, state="failed", error=failure.code)
        return 1
    except Exception as failure:  # noqa: BLE001 - reported to the launcher
        log(f"failed: {failure!r}")
        prog.set(prog.phase or "python", prog.part, state="failed", error="failed")
        return 1
    prog.set("build", 1.0, state="done", error=error)
    log("HD pack installed; removing the build files")
    cleanup(data)
    return 0


if __name__ == "__main__":
    sys.exit(main())
