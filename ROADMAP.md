# Roadmap

Numbers are stable IDs and are never reused.

Done:
1. [x] Disc and EXE analysis; the EXE runs from KUSEG, which upstream had never tested
2. [x] Recompilation boots BIOS → title → menu → 3D level, with 0 dispatch misses
3. [x] A/B against psx-beetle: identical attract demo and timer values
4. [x] macOS build verified (50 fps, audio, memory card, launcher)
5. [x] OpenBIOS: plays without a retail BIOS, including memory card saves
6. [x] Level Select mod
7. [x] Widescreen mod up to 2.4:1 (21:9), HUD in the corners, edge culling widened on both sides
8. [x] CD Speed default (2x)
9. [x] Upstream reports: KUSEG result and portability findings for musl/macOS
10. [x] Upstream PR: widescreen band form for register compares ([psxrecomp#676](https://github.com/RetroPortingToolKit/psxrecomp/pull/676))
11. [x] Widescreen: filled side bands on still screens, HUD sparkles in the corners, pill trail at full width
12. [x] Upstream PR: framebuffer-feedback sprites in the bands ([psxrecomp#692](https://github.com/RetroPortingToolKit/psxrecomp/pull/692))
13. [x] Upstream PRs for the musl/macOS findings ([#693](https://github.com/RetroPortingToolKit/psxrecomp/pull/693), [#694](https://github.com/RetroPortingToolKit/psxrecomp/pull/694))
14. [x] Ending FMV plays
15. [x] Wobble fix: PGXP on by default
16. [x] Launcher: only memory card 1, own box art, brand mark and app icon
17. [x] Widescreen: sky reaches the wide corners
18. [x] HD textures, built in the background from the player's disc (Linux and macOS verified)
19. [x] Detail Distance: sharp far cubes and full item models (Linux and macOS verified)
20. [x] Upstream PRs: a game can hide memory card slot 2 and use its own brand mark in the launcher ([recomp-ui#110](https://github.com/RetroPortingToolKit/recomp-ui/pull/110), [#114](https://github.com/RetroPortingToolKit/recomp-ui/pull/114))
21. [x] Framework update: psxrecomp and recomp-ui on current upstream `master`
22. [x] Controller test on macOS (Xbox One pad over Bluetooth)
23. [x] Launcher colors per game: sandstone and sky
25. [x] Upstream PRs: per-game launcher colors and the mod feature status line ([recomp-ui#173](https://github.com/RetroPortingToolKit/recomp-ui/pull/173), [psxrecomp#1001](https://github.com/RetroPortingToolKit/psxrecomp/pull/1001))
27. [x] HD textures: hourglass sand levels and the menu/level-end graphics stored compressed in the EXE
28. [x] HD textures: build status in the launcher mod row
29. [x] Upstream PR: launcher finds its assets when the host passes the exe dir ([recomp-ui#171](https://github.com/RetroPortingToolKit/recomp-ui/pull/171))
30. [x] Windows build (MinGW-w64 cross build, verified under Wine)
31. [x] Release zips: Linux x64 (glibc), Windows x64, macOS arm64 (`.app` with icon, player data in Application Support)

Next:
24. [ ] Help [#1](https://github.com/zap0xfce2/Kula-World-Rerolled/issues/1): on Manjaro (glibc) the launcher's Generate & Rebuild fails with "Toolchain ensure succeeded but bin/ is not usable for emitters"
26. [ ] HD textures: test the background build on Windows
32. [ ] Listing on RecompStore / RecompLauncher (needs a GitHub release; optional `recomplauncher.json`)
