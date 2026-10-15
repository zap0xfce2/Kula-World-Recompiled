#!/usr/bin/env python3
"""Drive the level-select submenu over the debug server and verify the start.

Run against a dev build that sits in the main menu (fresh process).
Usage: check_level_select.py --world 7 --level 3 [--port 4370]
"""

import argparse
import sys
import time
from pathlib import Path

from smoke_boot import WATCHED_S32, DebugConnection, connect_with_retry

PAD_UP, PAD_RIGHT, PAD_DOWN, PAD_CROSS = 0x0010, 0x0020, 0x0040, 0x4000
ALL_RELEASED = 0xFFFF
MENU_TIMER = 4950
CHEATED_ADDR = 0x800A4E0C
PRESS_FRAMES = 4
SETTLE_S = 0.6
LOAD_WAIT_S = 20.0
MENU_WAIT_S = 120.0


def press(conn: DebugConnection, buttons: int) -> None:
    """The wire format is active-low."""
    conn.request(
        {"cmd": "press", "buttons": ALL_RELEASED ^ buttons, "frames": PRESS_FRAMES}
    )
    time.sleep(SETTLE_S)


def press_times(conn: DebugConnection, buttons: int, count: int) -> None:
    for _ in range(count):
        press(conn, buttons)


def wait_for_menu(conn: DebugConnection) -> None:
    deadline = time.monotonic() + MENU_WAIT_S
    while conn.read_s32(WATCHED_S32["levelTimeLeft"]) != MENU_TIMER:
        if time.monotonic() > deadline:
            raise TimeoutError("main menu not reached")
        time.sleep(0.5)


def select_and_start(
    conn: DebugConnection, world: int, level: int, shots: Path
) -> None:
    press(conn, PAD_CROSS)  # main menu: 1 Player
    press(conn, PAD_CROSS)  # one-player menu: Arcade opens the submenu
    press(conn, PAD_DOWN)
    press_times(conn, PAD_RIGHT, world - 1)
    press(conn, PAD_DOWN)
    press_times(conn, PAD_RIGHT, level - 1)
    conn.request({"cmd": "screenshot", "path": str((shots / "submenu.png").resolve())})
    press(conn, PAD_UP)
    press(conn, PAD_UP)
    press(conn, PAD_CROSS)


def check_started(conn: DebugConnection, world: int, level: int) -> list[str]:
    time.sleep(LOAD_WAIT_S)
    expected = {
        "curWorld": world - 1,
        "curLevel": level - 1,
        "gameState": 1,
        "isDemoMode": 0,
    }
    failures = [
        f"{name}: expected {want}, got {conn.read_s32(WATCHED_S32[name])}"
        for name, want in expected.items()
        if conn.read_s32(WATCHED_S32[name]) != want
    ]
    want_cheated = 0 if (world, level) == (1, 1) else 1
    if conn.read_s32(CHEATED_ADDR) != want_cheated:
        failures.append(f"cheated: expected {want_cheated}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=4370)
    parser.add_argument("--world", type=int, default=7, choices=range(1, 11))
    parser.add_argument("--level", type=int, default=3, choices=range(1, 16))
    parser.add_argument("--out", default="analysis/level-select")
    args = parser.parse_args()
    shots = Path(args.out)
    shots.mkdir(parents=True, exist_ok=True)
    conn = connect_with_retry("127.0.0.1", args.port, time.monotonic() + 60)
    wait_for_menu(conn)
    select_and_start(conn, args.world, args.level, shots)
    failures = check_started(conn, args.world, args.level)
    conn.request({"cmd": "screenshot", "path": str((shots / "level.png").resolve())})
    print(conn.request({"cmd": "mod_counters"}))
    for failure in failures:
        print("FAIL", failure)
    print("level_select_ok" if not failures else "level_select_failed")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
