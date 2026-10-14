#!/usr/bin/env python3
"""Boot smoke test: poll a running psx-runtime or psx-beetle over the debug protocol.

Without input the game idles in the main menu and starts demo gameplay after
2000 frames, so "isDemoMode == 1 with levelTimeLeft counting down" proves
BIOS -> title -> menu -> 3D level. Same wire protocol on both backends.
"""

import argparse
import json
import socket
import sys
import time
from dataclasses import dataclass
from pathlib import Path

# Variable addresses from dezgeg/kula-world-decomp config/eu-SCES_010.00 (KSEG0 view).
WATCHED_S32: dict[str, int] = {
    "gameState": 0x800A2EC0,
    "gameMode": 0x800A2E48,
    "curMenu": 0x800A3354,
    "isDemoMode": 0x800A566C,
    "curWorld": 0x800A2EA4,
    "curLevel": 0x800A2EA0,
    "levelTimeLeft": 0x800A52C8,
    "vsyncCounter": 0x800A2F64,
}
DEFAULT_PORT = 4370
SOCKET_TIMEOUT_S = 10.0
CONNECT_RETRY_S = 1.0


@dataclass
class Sample:
    elapsed_s: float
    frame: int
    values: dict[str, int]


class DebugConnection:
    """JSON request/response over TCP; the server answers one request per connection."""

    def __init__(self, host: str, port: int) -> None:
        self._address = (host, port)

    def request(self, payload: dict[str, object]) -> dict[str, object]:
        with socket.create_connection(self._address, timeout=SOCKET_TIMEOUT_S) as sock:
            sock.sendall((json.dumps(payload) + "\n").encode())
            data = b""
            while b"\n" not in data:
                chunk = sock.recv(1 << 20)
                if not chunk:
                    break
                data += chunk
        reply: dict[str, object] = json.loads(data.split(b"\n", 1)[0])
        if not reply.get("ok", False):
            raise RuntimeError(f"{payload['cmd']} failed: {reply}")
        return reply

    def read_s32(self, addr: int) -> int:
        reply = self.request({"cmd": "read_ram", "addr": f"0x{addr:08X}", "len": 4})
        return int.from_bytes(bytes.fromhex(str(reply["hex"])), "little", signed=True)


def connect_with_retry(host: str, port: int, deadline_s: float) -> DebugConnection:
    """The server only listens once the runtime is up; wait for it."""
    conn = DebugConnection(host, port)
    while True:
        try:
            conn.request({"cmd": "ping"})
            return conn
        except OSError:
            if time.monotonic() > deadline_s:
                raise
            time.sleep(CONNECT_RETRY_S)


def read_frame(conn: DebugConnection) -> int:
    """psx-beetle reports the frame in ping; psx-runtime only via the frame command."""
    pong = conn.request({"cmd": "ping"})
    if "frame" in pong:
        return int(str(pong["frame"]))
    return int(str(conn.request({"cmd": "frame"})["frame"]))


def take_sample(conn: DebugConnection, started: float) -> Sample:
    frame = read_frame(conn)
    values = {name: conn.read_s32(addr) for name, addr in WATCHED_S32.items()}
    return Sample(time.monotonic() - started, frame, values)


def save_screenshot(conn: DebugConnection, out_dir: Path, label: str) -> str:
    path = (out_dir / f"{label}.png").resolve()
    try:
        conn.request({"cmd": "screenshot", "path": str(path)})
    except RuntimeError as err:
        return f"screenshot failed: {err}"
    return str(path)


def reached_demo_gameplay(samples: list[Sample]) -> bool:
    """Level timer ticks down between consecutive samples of the same demo level."""
    for before, after in zip(samples, samples[1:]):
        same_demo = (
            before.values["isDemoMode"] == after.values["isDemoMode"] == 1
            and before.values["curWorld"] == after.values["curWorld"]
        )
        if same_demo and after.values["levelTimeLeft"] < before.values["levelTimeLeft"]:
            return True
    return False


def run(args: argparse.Namespace) -> int:
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    conn = connect_with_retry(args.host, args.port, started + args.connect_timeout)
    samples: list[Sample] = []
    while time.monotonic() - started < args.duration:
        sample = take_sample(conn, started)
        samples.append(sample)
        shot = save_screenshot(
            conn, out_dir, f"t{int(sample.elapsed_s):04d}_f{sample.frame}"
        )
        print(
            json.dumps(
                {
                    "t": round(sample.elapsed_s, 1),
                    "frame": sample.frame,
                    **sample.values,
                    "shot": shot,
                }
            )
        )
        sys.stdout.flush()
        time.sleep(args.interval)
    verdict = reached_demo_gameplay(samples)
    print(
        json.dumps(
            {
                "verdict": (
                    "demo_gameplay_reached" if verdict else "demo_gameplay_not_reached"
                )
            }
        )
    )
    return 0 if verdict else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT, help="4370 runtime, 4380 beetle"
    )
    parser.add_argument(
        "--duration", type=float, default=120.0, help="seconds to observe"
    )
    parser.add_argument(
        "--interval", type=float, default=10.0, help="seconds between samples"
    )
    parser.add_argument("--connect-timeout", type=float, default=60.0)
    parser.add_argument("--out", default="analysis/smoke", help="screenshot directory")
    return parser.parse_args()


if __name__ == "__main__":
    sys.exit(run(parse_args()))
