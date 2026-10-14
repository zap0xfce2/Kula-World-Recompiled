# CLAUDE.md – Kula World Recompiled

Statischer Recomp von **Kula World (PAL, SCES-01000)** zu einer nativen Linux/Windows-Anwendung
auf Basis von [psxrecomp](https://github.com/RetroPortingToolKit/psxrecomp).
Vorlage für Projektstruktur, Mods und Launcher: [hercules-recompiled](https://github.com/obaidr1/hercules-recompiled).

## Zusammenarbeit
- Antworte immer auf Deutsch und duze den Nutzer.
- Der Nutzer ist Softwareentwickler, IT-Experte und DevOps Engineer. Erkläre keine Grundlagen.
- Code nicht ausführlich erklären, sondern nach Clean-Code-Prinzip kommentieren.
- Default-Plattform ist Linux. Editor-Anweisungen immer mit `vi`, nie `nano`.
- Spekuliere nicht über Hardware-Verhalten. Verifiziere gegen den Oracle-Emulator (Beetle) oder sag "unbekannt".

## Rechtliches – harte Regel
**Niemals Spieldaten committen**: kein BIOS, keine `.bin`/`.cue`, keine `SCES_010.00`,
keine extrahierten Assets und keine Disassembly mit Original-Bytes.
`disc/`, `bios/`, `generated/` (bis zur Release-Entscheidung) gehören in `.gitignore`.

## Stand (2026-10-15)
Voranalyse abgeschlossen, Repo nach New Project Layout aufgesetzt (lokal, kein Remote). **KUSEG-Smoke-Test bestanden**, Details und A/B-Tabelle in `NOTES.md`.
- Submodule: `psxrecomp` @ `f9c287f5`, `recomp-ui` @ `41c88ff` (Snapshot in `framework_pins.txt`)
- Scaffold-Optionen: recomp-ui + Setup-Wizard an; Netplay, CI-Workflow, Boxart aus
- BIOS liegt als `bios/SCPH1001.BIN` vor (MD5 `924e392ed05558ffdb115408c263dccf`, verifiziert)
- 2026-10-15: Generate und Release-Build laufen (`build-release/Kula_World_Recompiled`). Der Boot unter Xvfb erreicht BIOS → Titel → Hauptmenü → **Demo-Modus in 3D** (X11-Screenshots in `analysis/smoke-native/`). Das ist der erste KUSEG-Lauf auf aktuellem Upstream-Codegen (`d67f0f93`).
  - Gemessen (`build-dev`, `tools/smoke_boot.py`): gleiche Demo-Abfolge und gleiche Endwerte wie psx-beetle, 0 Dispatch-Misses. Ergebnis noch nicht upstream gemeldet (Entwurf in `docs/upstream-report-kuseg.md`).
- **Abweichung von Upstream:** `generated/` ist bewusst gitignored (Upstream committet es), bis die Release-Entscheidung gefallen ist.
- `disc/kula-quest-jp/` enthält Kula Quest (Japan), nur als Referenz, nicht Teil des Builds.

### Disc
- Raw-Image MODE2/2352, 1 Datentrack, 255.123.792 Bytes
  - MD5 `0f675dc230354f8c3b835bf34841bd20`
  - SHA1 `0bf9fb06b73a9b5353cdcc371e188934369068da`
  - Noch nicht gegen Redump verifiziert
- Liegt als `disc/SCES01000.BIN` + `.CUE` vor. Die Cue-Datei wurde von Hand erstellt, das Original war eine falsch benannte `.iso`.
- `disc/SCES_010.00` ist die vom Scaffold extrahierte Boot-EXE (gitignored).
- Dateien:
  - Boot-EXE `SCES_010.00`
  - Pro Welt `<WELT>.PAK` (Level, zlib), `<WELT>FI.PAK` und `<WELT>.TGI`
  - `HIRO/` mit `HIRO.GGI`, `HIRO.SFX`, `COPYCAT.PAK`, `WARNING.TIM`
  - `XA/` mit `MUSIC_0..3.XA` (Form 2) und `FINAL.STR` (MDEC-FMV)
  - `3.00` = 31 MB Null-Padding
- Format-Doku: https://wiki.kula.quest/ (PAK, KUB, TGI, GGI, SFX, Level)

### EXE `SCES_010.00`
| Feld | Wert |
|---|---|
| Load / Text | `0x00011000`, `0x93000` Bytes – **KUSEG-gelinkt** |
| Entry | `0x00069F60` |
| GP | 0, kein `$gp`-relatives Addressing |
| Stack | Header `0x801FFFF0`, crt0 legt `$sp` aber in den 4. RAM-Mirror (`0x807FFFF8`) |
| Code | `0x00012344`–`0x00072AC0`, danach Daten und Strings |
| Funktionen | 727 JAL-Ziele (`seeds/ghidra_funcs.txt`), plus 88 Prolog-Kandidaten (`seeds/heuristic_candidates.txt`) |
| Indirekt | 202 `jalr`, 99 `jr reg` → Indirect Targets und Jump-Tables nötig |
| Libs | PsyQ ~4.x (libgpu `sys.c` 1998-01-12, libcd `bios.c` 1997-03-28), zlib `inflate 1.0.4` |
| GTE | ca. 135 Kommandos im Code (RTPT, RTPS, NCLIP, AVSZ3/4, MVMVA, DCPL) |

**Keine Overlays** (verifiziert):
- Kein `Load`, `Exec` oder `LoadExec` im Code.
- Die `FlushCache`-Aufrufer sind PsyQ-Kernel-Patches.
- In TGI, GGI, SFX und PAK (auch entpackt) steckt kein MIPS-Code.

Damit ist ein rein statischer Recomp möglich.

### Ankerpunkte (PAL)
- Level-Timer-Init `0x000367D4`: Property-Typ 666 → `startingTime * 50`, sonst `0x1356` (4950)
- Variable `currentTime` = `0x000A52C8`
- Zum Vergleich in Roll Away (SLUS_007.24): Code `0x35F5C`, Variable `0xA573C`. Die Community-Doku nutzt meist diese Version.

## Vorarbeit anderer (unbedingt lesen)
Fork **chrisking1981/psxrecomp_kula_world**, Branch `kula-world-linux-macos`
(Commit `6e711e0`, 2026-07-03). Er erreicht BIOS → Titel → Menü → spielbares 3D-Level unter Linux, Windows und macOS.
- `docs/kula-world-findings.md`: alle Bugs und Debug-Methodik
- `docs/WINDOWS_BUILD_KULA.md`, `docs/MACOS_BUILD_KULA.md`
- `games/kula/game.toml`: dort noch mit Faltung auf KSEG0 (`0x80011000`)

Dort gefixt und laut `docs/ecosystem-watch.md` nach upstream übernommen:
1. RAM-Mirror: `$sp` im 4. Mirror (`runtime/src/memory.c`)
2. GetID-Region war fest auf SCEI kodiert → aus `SYSTEM.CNF` abgeleitet (PAL = SCEE)
3. CD-Statusbits ADPBUSY/BUSYSTS
4. CD-Controller-Version für SCPH-1001 auf `0x94 0x09 0x19 0xC0`
5. libcd-CD-IRQ wurde nicht bedient. War in der Findings-Doku noch offen, laut späterem Commit gelöst.

**alexbeavs-ps1-ports/kula-world-recomp** (GPL-3.0, Releases bis v0.3.6 vom 2026-09-04, Recherche am 2026-10-14):
- Gleiche Disc (gleiche MD5) und gleiche KUSEG-`game.toml`. Laut `docs/FEASIBILITY.md` bis Gameplay gekommen (`bootstrap_verified`).
- Teil eines Portfolios mit 24 Titeln. Inhaltlich nur Scaffold plus Packaging/CI: Seeds nur aus dem Probe, keine Symbole, keine Mods.
- Pinnt den eigenen Fork `Alexbeav/psxrecomp@08ec704`. Merge-Base mit Upstream ist vom 2026-08-30, also **vor** dem KUSEG-Codegen `d67f0f93` (2026-09-29). Gegenüber Upstream 91 Commits voraus (u. a. PAL-VBlank-Timing, SPU-IRQ, Savestates) und 1482 zurück.
- Fazit: Bootstrap bringt er nichts mit, was wir übernehmen müssten. Mods und KUSEG auf aktuellem Upstream hat noch niemand gemacht.

**dezgeg/kula-world-decomp** (Matching-Decomp, **keine Lizenz**, seit 2024, 947 Commits, aktiv bis 2026-10-13):
- Zielt auf genau unsere EXE: `config/eu-SCES_010.00`, SHA256-Check `28c8f46d…` ist identisch mit `disc/SCES_010.00`.
- 939 benannte Funktionen (`function_addrs.txt`, nur 5 `FUN_`), 937 typisierte Variablen, 347 PsyQ-Lib-Symbole, Strings und Relocs. Format: splat/`name = 0x…; // type:…`.
- Nur noch 27 Funktionen in ASM, v. a. Render, GTE, Subdivide, Light-Effects, `WaitForVBlank`. Der Rest ist matchendes C (`src/*.c`, u. a. `cheats.c`, `level_update*.c`, `player_movement.c`, `vsync.c`).
- Portiert gerade nach US/JP (`VER_US`, `VID_NTSC`). `psyz` (PsyQ-Reimplementierung für PC) ist als Submodule eingebunden, wird im Makefile aber noch nicht genutzt.
- Nutzen für uns: vollständige Funktionsgrenzen für Seeds/Indirect Targets, Symbole für `symbols.toml`, lesbares C als Grundlage für die Mods (Timer, Kamera, Cheats). Ohne Lizenz die Dateien nur lokal als Referenz nutzen und vor dem Committen abgeleiteter Listen beim Maintainer nachfragen.

**Pixelsprout/rocco-engine** (UPL-1.0, Odin/Roc): Klon-Engine mit 3 Leveln und eigenen Assets, Code für uns unbrauchbar.
Nützlich ist `games/kula/SPEC.md`: Gameplay-Fakten aus dem Decomp (Commit `2ca79ff`) mit Zeilenverweisen.
Darin stehen Einheiten (512/Block, 4096/Umdrehung), pro Frame laufende Werte (Roll +7/Frame bis 40, Turn 16 Frames, Gravity +6 bis 80, Jump 27 Frames, Idle-Bob hängt an `levelTimeLeft`) und die Kamera (starr, H=160 → 73,7° vFOV bei 4:3).
Das ist die Checkliste für den 60-FPS-Mod (was an 50 Hz hängt) und die Basis für Widescreen.

**Daten- und Modding-Tools** (Disc-Formate, kein Code):
- `SaturnKai/Randomizer` (GPL-3.0, C#): mischt Level, Themes, SFX und Modelle auf Dateiebene.
- `KulaWorkshop/Quilt` (Nachfolger von PakTool) und `LevelEditor`.
- `RetroAtlas/KulaWorldMap` (GPL-2.0, sehr aktuell): Doku zu Level-Format, TGI, GGI und Bewegungsregeln, inkl. Cheat für beliebige Level (`docs/level-format.md`).

**Offener Punkt für uns:** Upstream faltet KUSEG nicht mehr auf KSEG0, die Code-Identität bleibt `0x0001xxxx`
(`docs/SEGMENT_AWARE_CODE.md` §3.2, §5.3, §7). Laut Upstream-Doku wurde das **mit Kula World nie getestet**.
Daher nutzt unsere `game.toml` bewusst die KUSEG-Adressen aus dem Header.

## Projektlayout
```
CLAUDE.md, NOTES.md        Kontext und Befunde
psxrecomp/, recomp-ui/     Submodule (Framework, Launcher-UI)
CMakeLists.txt, codegen_setup.{c,h}, symbols.toml, psx_symbols.h, game_options.toml
                           Scaffold aus setup_project.sh; psx_symbols.h via tools/sync_symbols.py
catalog_identity.json, disc_probe.json, .recomp.json  Disc-Identität (Digests, TOC-Fingerprint)
game.toml                  psxrecomp-Config (von probe_disc.py erzeugt, disc-Pfad relativ gesetzt)
seeds/ghidra_funcs.txt     Seeds für den Recompiler (Entry + JAL-Ziele)
seeds/heuristic_candidates.txt  JAL + "addiu sp,sp,-N nach jr ra", noch nicht verifiziert
tools/psxdisc.py           ISO9660-Reader/Extraktor für Raw-MODE2/2352-Images
tools/exe_probe.py         EXE-Header, Seeds, BIOS-Stubs, GTE-Statistik, Strings
tools/mips.py              Mini-R3000A-Disassembler: mips.py <exe> 0x11000 <start> <count>
tools/scan_data.py         Sucht MIPS-Code in Disc-Dateien (inkl. entpackter PAKs)
disc/, bios/               Nutzerdaten, nicht in git
```
Python-Tools, die Disc-Daten lesen, immer mit `python3 -I` starten.

## Strategie (entschieden 2026-10-14)
- **Jetzt: Recomp mit psxrecomp.** Das dezgeg-Decomp dient nur als Wissens- und Symbolquelle, es fließt kein Code daraus ein.
- **Roadmap: nativer Port aus dem dezgeg-Decomp über psyz.** Voraussetzungen:
  - dezgeg vergibt eine Lizenz oder stimmt zu
  - die 27 ASM-Funktionen liegen als C vor
  - psyz ist angebunden
  - vorher bei dezgeg nachfragen, ob ein eigener PC-Port geplant ist (Zusammenarbeit statt Doppelarbeit)

## Nächste Schritte
1. ~~Repo nach New Project Layout aufsetzen~~ (erledigt)
2. ~~`bios/SCPH1001.BIN` einbinden~~ (erledigt)
3. `cmake`/`ninja` installieren (`apk add`), Recompiler bauen, BIOS und Spiel generieren, Runtime bauen:
   ```sh
   ./psxrecomp/tools/ci/build_emitters.sh
   python3 psxrecomp/psxrecomp_cli.py generate --config game.toml --project-root . \
       --disc disc/SCES01000.CUE
   cmake -S . -B build-release -G Ninja -DCMAKE_BUILD_TYPE=Release
   cmake --build build-release --target psx-runtime
   ```
4. ~~KUSEG-Smoke-Test: Boot → Titel → Level, A/B gegen psx-beetle~~ (erledigt). Ergebnis upstream melden (Entwurf liegt bereit, Freigabe durch den Nutzer nötig).
   - Noch offen: ein Level mit echter Eingabe spielen; Ending-FMV, Memory Card und XA-Musik prüfen.
5. Seeds und Indirect Targets verfeinern. Auf dem Pfad Boot/Menü/Demo gibt es 0 Dispatch-Misses. 6 Decomp-Funktionen sind keine Einstiegspunkte (`zcalloc`, `StrCallback`, `_spu_2pitch`, `Libpad_Padportd_654`, `DebugSaveScreenshotToPc`, `zcallocUnused`); erst handeln, wenn `unknown_dispatch_log` sie meldet. Die Funktionsgrenzen kommen aus `function_addrs.txt` des dezgeg-Decomps (lokal, siehe Lizenzhinweis), Namen über `symbols.toml`. Vorlage für das Format: Hercules `decomp/config/indirect_targets.json`.
6. Ziele nach Lauffähigkeit:
   - Widescreen (GTE-Squash + `[widescreen]`). Kamera und Projektion stehen in rocco `SPEC.md`, Cull-Stellen im Decomp-C.
   - Wobble-Fix
   - 60 FPS: Timer läuft framebasiert mit 50 Hz, die Logik muss entkoppelt werden. Checkliste der Werte pro Frame: rocco `SPEC.md`.
   - Levelauswahl-Mod (Cheat aus KulaWorldMap `docs/level-format.md`, `cheats.c` im Decomp)
   - HD-Texturen aus TGI/GGI
   - Muster für Mods und Patches: `hercules-recompiled/port/mods`, `port/patches`
7. Roadmap: nativer Port über das Decomp (siehe Strategie)

## Build-Gotchas (Alpine/musl)
- Systempakete: `sudo apk add cmake samurai pkgconf sdl3-dev mesa-dev linux-headers` (samurai liefert `ninja`). Zum Headless-Testen: `xvfb xvfb-run mesa-dri-gallium`.
- `psxrecomp_cli.py generate` **immer mit `--no-toolchain-download`**. Ohne das Flag passiert Folgendes:
  - Es lädt die glibc-Toolchain `cmake-clang-v1` nach `~/.local/share/retcomm`, die unter musl nicht läuft.
  - Es trägt PATH-Hooks in `~/.zshrc` und `~/.profile` ein.
  - Es schreibt `toolchain/.psxrecomp-bin`.
  - Das CLI durchsucht `~/.local/share/retcomm` immer. Der Ordner darf also nicht existieren (aktuell umbenannt zu `retcomm.broken-glibc`).
- Nach `generate --bios` fehlt `psxrecomp/generated/SCPH1001.emitter.sha` (CLI-Lücke), dann meldet CMake „BIOS … STALE“. Abhilfe: `cd psxrecomp && bash tools/regen_bios.sh --config bios/SCPH1001.toml`.
- musl hat keine `getcontext`/`makecontext`/`swapcontext`, die `psx_fiber.c` braucht. Abhilfe: `sudo apk add libucontext-dev` und bei jedem CMake-Configure `-DCMAKE_C_STANDARD_LIBRARIES=-lucontext -DCMAKE_CXX_STANDARD_LIBRARIES=-lucontext`.
- Release-Builds haben keinen Debug-Server. Für Tests deshalb `build-dev` mit `-DCMAKE_BUILD_TYPE=Release -DPSX_DEBUG_TOOLS=ON`. Start: `xvfb-run -a ./build-dev/Kula_World_Recompiled --no-launcher --bios bios/SCPH1001.BIN --disc disc/SCES01000.CUE --debug-port 4370`.
- Generate dauert ca. 2 min (569 Shards, 31 Mio. Zeilen C, ~950 MB). Der Runtime-Build dauert auf 8 Kernen ca. 23 min.
- Oracle: `psxrecomp/beetle-psx` (im Submodule gitignored) auf `5759277b` plus `docs/beetle_*.patch`, siehe `psxrecomp/docs/beetle-linux.md`.

## Smoke-Test
- `tools/smoke_boot.py --port 4370|4380` liest `gameState`, `isDemoMode`, `levelTimeLeft` usw. (Adressen aus dem Decomp) und speichert Screenshots nach `analysis/smoke/`.
- Ohne Eingabe startet das Spiel nach 2000 Menü-Frames (40 s) den Demo-Modus. „Demo aktiv und Timer läuft runter“ beweist also BIOS → Titel → Menü → 3D-Level.
- Tests: `python3 -m unittest discover -s tests`.

## Werkzeuge in dieser Umgebung
- Erste Anlaufstelle für Code-Verständnis ist das dezgeg-Decomp, nicht Ghidra.
- Ghidra ist optional (noch nicht installiert, kein JDK), nur für die 27 ASM-Funktionen oder zum Gegenprüfen.
  Dann mit `ghidra_psx_ldr` die EXE im KUSEG-Segment laden (Basis `0x00011000`) und Funktionsgrenzen per `psxrecomp-analyze --emit-ghidra` importieren.
- Oracle: psx-beetle aus psxrecomp (`docs/beetle-linux.md`), gleiches TCP-Debug-Protokoll wie die Runtime.
- psxrecomp-Regeln aus dessen `CLAUDE.md` beachten:
  - Kein HLE, keine Stubs
  - Generierten Code nie von Hand ändern
  - Kein printf-Debugging, stattdessen Debug-Server-Kommandos
