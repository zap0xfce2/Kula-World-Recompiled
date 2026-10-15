#!/usr/bin/env python3
"""Keep the level timer full while testing (dev build with debug server only).

Rewrites levelTimeLeft once per interval while a level is running, so long
manual or scripted test sessions do not end in a time-out.
Usage: freeze_timer.py [--port 4370] [--interval 1.0]
"""

import argparse
import struct
import time

from smoke_boot import WATCHED_S32, DebugConnection, connect_with_retry

FULL_TIMER = 4950  # the game's default level time (99 s at 50 Hz)
GAME_STATE_PLAYING = 1
CONNECT_TIMEOUT_S = 60.0


def write_s32(conn: DebugConnection, addr: int, value: int) -> None:
    # write_ram writes one byte per request; the guest is little endian
    for offset, byte in enumerate(struct.pack("<i", value)):
        conn.request(
            {"cmd": "write_ram", "addr": f"0x{addr + offset:08X}", "val": f"{byte:02x}"}
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=4370)
    parser.add_argument("--interval", type=float, default=1.0)
    args = parser.parse_args()
    conn = connect_with_retry(
        "127.0.0.1", args.port, time.monotonic() + CONNECT_TIMEOUT_S
    )
    while True:
        if conn.read_s32(WATCHED_S32["gameState"]) == GAME_STATE_PLAYING:
            write_s32(conn, WATCHED_S32["levelTimeLeft"], FULL_TIMER)
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
