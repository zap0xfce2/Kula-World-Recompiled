# CLAUDE.md – Kula World Recompiled

Statischer Recomp von **Kula World (PAL, SCES-01000)** zu einer nativen Linux/Windows-Anwendung
auf Basis von [psxrecomp](https://github.com/RetroPortingToolKit/psxrecomp).
Vorlage für Projektstruktur, Mods und Launcher: [hercules-recompiled](https://github.com/obaidr1/hercules-recompiled).

## Zusammenarbeit
- Antworte immer auf Deutsch und duze den Nutzer.
- Der Nutzer ist Softwareentwickler, IT-Experte und DevOps Engineer. Erkläre keine Grundlagen.
- Code nicht ausführlich erklären, sondern nach Clean-Code-Prinzip kommentieren.
- Default-Plattform ist Linux. Editor-Anweisungen immer mit `vi`, nie `nano`.
- Git: Das Repo ist seit 2026-10-16 öffentlich. Die frühere Freigabe „ohne Rückfrage committen und pushen“ galt nur, solange es privat war; Commits und Pushes jetzt nur nach Rückfrage.
  - Weiterhin nur mit Freigabe: Force-Push, Historie umschreiben, Sichtbarkeit ändern, Issues/PRs in fremden Repos.
  - Vor jedem Commit `git status` prüfen und sicherstellen, dass keine Spieldaten und keine Secrets dabei sind.
- Tests laufen standardmäßig unter Linux (Xvfb + Debug-Server). Der Mac macht nur die Endabnahme und was unter Linux nicht geht (echte GPU-fps, Ton, Launcher, Fenster per Maus). Freigabe vom 2026-10-15.
- Ghidra und PSX-Plugins dürfen installiert und genutzt werden, wenn es hilft (Freigabe vom 2026-10-15).
- Spekuliere nicht über Hardware-Verhalten. Verifiziere gegen den Oracle-Emulator (Beetle) oder sag "unbekannt".

## Rechtliches – harte Regel
**Niemals Spieldaten committen**: kein BIOS, keine `.bin`/`.cue`, keine `SCES_010.00`,
keine extrahierten Assets und keine Disassembly mit Original-Bytes.
`disc/`, `bios/`, `generated/` (bis zur Release-Entscheidung) gehören in `.gitignore`.

## Stand (2026-10-15)
Voranalyse abgeschlossen, Repo nach New Project Layout aufgesetzt (Remote `github.com/zap0xfce2/kula-world-recompiled`, vorerst privat). **KUSEG-Smoke-Test bestanden**, Details und A/B-Tabelle in `NOTES.md`.
- Submodule: `psxrecomp` @ `0edce1d3`, `recomp-ui` @ `41c88ff` (Snapshot in `framework_pins.txt`)
  - `psxrecomp` kommt seit 2026-10-16 aus dem Fork `zap0xfce2/psxrecomp`, Branch `kula/ws-screen-x-sltu-band`: Upstream-Pin `f9c287f5` plus die `sltu`-Bandform für `screen_x_sites`.
  - Darauf aufbauend Branch `feat/ws-feedback-rect` (Framebuffer-Feedback in den Bändern, Pillen-Effekt, 2026-10-19). Upstream: PR RetroPortingToolKit/psxrecomp#692 (Branch `feat/ws-feedback-rect-upstream`, auf aktuellem `master`). Nach dem Merge wie bei #676 zurück auf Upstream pinnen.
  - Upstream: Issue RetroPortingToolKit/psxrecomp#675, PR #676 (auf aktuellem `master`). Nach dem Merge `.gitmodules` zurück auf Upstream stellen und neu pinnen.
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
3. ~~Recompiler bauen, BIOS und Spiel generieren, Runtime bauen~~ (erledigt, Befehle und Fallstricke unter Build-Gotchas)
4. ~~KUSEG-Smoke-Test: Boot → Titel → Level, A/B gegen psx-beetle~~ (erledigt)
   - Interaktiv verifiziert: Spielstart per Eingabe, Timer läuft, Kugel rollt (`analysis/play-native2/`).
5. Offene Punkte aus dem Smoke-Test:
   - ~~Ergebnis upstream melden~~ (erledigt 2026-10-15): RetroPortingToolKit/psxrecomp#671 (KUSEG) und #672 (6 Portabilitäts-Befunde). Quelle: `docs/upstream-report-kuseg.md`.
     - Zu #671 (2026-10-19): PR #695 trägt das Ergebnis in `docs/SEGMENT_AWARE_CODE.md` §7 ein. Neu gemessen auf Upstream `bce31aff` (Testbaum ohne Mods/Fork): 971 Funktionen, Kalt- gegen Warm-Cache (5 Shards: 4× `seg-kuseg`, 1× `seg-kseg1`) über 10.000 Frames in allen `frame_fingerprint`-Spalten identisch, `segment_native` 0 → 59.524, 0 Misses. Demo-Enden wie Beetle: 3603/9950 und 3017/6845. Gotchas: Upstream braucht das Untermodul `lib/retcomm-rbengine` (`git submodule update --init --recursive`), und mit aktiven Mods ohne Plugins startet die Runtime nicht (`mods/state.toml` abschalten). Captures schreibt `overlay_capture_dump`, nicht `kill -9`.
     - Zu #672 (2026-10-19): PR #693 (Punkte 1, 2, 5, 6: libucontext-Erkennung, `uint16_t`, `python3` zuerst, `../build-recompiler`) und PR #694 (Punkt 4: `generate --bios` schreibt den Emitter-Stempel). Punkt 3 (glibc-Toolchain-Download unter musl) ist upstream durch `2c92ac3f` erledigt: Linux/macOS nutzen native Tools, kein Download, keine PATH-Hooks. Nach dem Merge können die musl-Flags und `regen_bios.sh` aus der `Taskfile.yaml` bzw. den Build-Gotchas entfallen.
   - Auf dem Mac verifiziert: XA-Musik und SFX, Memory Card (`saves/card1.mcd`), LLE-Boot. Offen: Controller (kein Gamepad zur Hand).
   - Ending-FMV (`FINAL.STR`) läuft (Mac, 2026-10-19, Nutzer live gesehen). Weg: Levelauswahl W10/L15, nach dem Laden `fruitsCollectedBitmask` (0x800A51F0) = 0 (sonst Bonuslevel) und `levelEndReason` (0x800A591C) = 1 → „Well Done!“, X → FMV, danach Score-Tabelle. Während des FMV `present_native_43` = 1 (4:3 mit Balken). `cheated` blockiert es nicht. Ungeprüft: volle Länge (Skript drückte X, lief ca. 30 s) und FMV-Ton.
   - Speichern und Laden über die Memory Card bestätigt der Nutzer (2026-10-19).
   - ~~Performance auf echter GPU messen~~ (erledigt): Der Mac schafft 49,5 fps. Die 35 bis 44 fps unter Xvfb/llvmpipe kommen von der Umgebung.
   - OpenBIOS (MIT, vom Framework mitgeliefert und mitgelinkt) funktioniert, getestet am 2026-10-15:
     - Start: `--bios build-dev/bios/openbios.bin`
     - `smoke_boot.py`: `demo_gameplay_reached`, gleiche Demo (Welt 0, Level 4) und gleicher Timer-Endwert 3603 wie mit SCPH1001
     - Log: `bios_backend=LLE`, `bios_boot=HLE (shell skipped)`, `image=OPENBIOS`. Call-HLE ist auf OpenBIOS nicht verfügbar.
     - Mac: Ohne gespeicherte BIOS-Wahl nimmt der Launcher OpenBIOS. Demo wie unter Linux, 50,0 fps, XA und SFX ok.
     - Memory Card ok: Ein unter Retail angelegter Spielstand lässt sich unter OpenBIOS laden und neu speichern.
     - Ein Build nur mit OpenBIOS geht: `-DPSXRECOMP_BIOS_STEMS=OpenBIOS`, ohne SCPH1001-Quellen, Smoke ohne `--bios` ok (Mac).
     - Die Demo startet mit Retail-HLE und OpenBIOS bei gleichem Frame (~3100–3200). Mit Retail-LLE (echtes Intro) kommt sie ca. 10 s später. Linux erreicht den Frame wegen llvmpipe in Sekunden später.
     - Offen: interaktives Spielen und A/B gegen Beetle mit OpenBIOS. Damit kann ein Release ohne Sony-BIOS auskommen, die Disc braucht es weiterhin.
   - `vsyncCounter` (`0x800A2F64`) ist auf beiden Backends immer 0. Klären, ob die Adresse aus dem Decomp für PAL stimmt.
6. Seeds und Indirect Targets verfeinern. Auf dem Pfad Boot/Menü/Demo gibt es 0 Dispatch-Misses. 6 Decomp-Funktionen sind keine Einstiegspunkte (`zcalloc`, `StrCallback`, `_spu_2pitch`, `Libpad_Padportd_654`, `DebugSaveScreenshotToPc`, `zcallocUnused`); erst handeln, wenn `unknown_dispatch_log` sie meldet. Die Funktionsgrenzen kommen aus `function_addrs.txt` des dezgeg-Decomps (lokal, siehe Lizenzhinweis), Namen über `symbols.toml`. Vorlage für das Format: Hercules `decomp/config/indirect_targets.json`.
7. Mods (vor jedem Mod Brainstorming mit dem Nutzer, Vorschlag: mit der Levelauswahl anfangen):
   - Levelauswahl-Mod `kula.level-select` (in `main` seit 2026-10-15, Spec und Plan unter `docs/superpowers/`):
     - „Arcade“ öffnet START / WORLD 1–10 / LEVEL 1–15. Standardmäßig an.
     - Ein Start ≠ 1/1 setzt `cheated = 1` und macht aus der Highscore-Eingabe die reine Tabelle.
     - Linux und Mac (M1 Pro, OpenBIOS) verifiziert: Starts 1/1, 3/5, 7/3, 10/3, 10/12; Optik; Kreis/Dreieck zurück; Highscore-Sperre und Gegenprobe 1/1; Launcher an/aus; keine Artefakte in anderen Texten.
     - Offen: Speicherpunkte nach Start ≠ 1/1 im Spiel bestätigen (laut Decomp unterdrückt `cheated` sie). Ending-FMV über W10/L15 erreichbar (siehe Smoke-Test-Abschnitt oben).
     - Plugin `mods/src/kula_level_select.c` + reine Logik `mods/src/level_select_logic.c` (C-Test in `task test`).
     - Hooks über `game.toml [recompiler] mod_function_entry_funcs`, danach `task generate`.
     - Prüfen: `tools/check_level_select.py --world W --level L` gegen eine frisch gestartete Dev-Runtime.
     - Gotcha Flackern: START ruft den Original-`SinglePlayerMenu` auf, der `DrawWidgets` vor der Kreuz-Abfrage zeichnet. Ohne den dritten Hook (`DrawWidgets` 0x17AE8, überspringt nur während `g_calling_original`) blitzte für einen Frame das Einspieler-Panel auf (2026-10-19 behoben, Linux und Mac per Frame-Capture bei 1/1 und 3/5 verifiziert; Final-Variante ungeprüft, kein passender Spielstand).
     - Gotcha: `DrawTextCrappyFont` zeichnet eine Zeile nur bei `\n`. `<`/`>` sind in dieser Schrift Tasten-Symbole.
     - Optik: alles in der kleinen Schrift, hellblau getönt. START zentriert, WORLD/LEVEL rechtsbündig an gemeinsamer Kante, `-`, Zahl und `+` je in fester Spalte, die gewählte Zeile hell, leichter Schatten. Kreis und Dreieck gehen zurück (Kreis nur im Untermenü).
     - Gotcha Schatten: Die kleine Schrift blendet additiv (`fontSprites` 0x800AA47C, abr 1), eine dunkle Kopie bleibt unsichtbar. Der Mod schaltet für den Schatten-Durchgang die Glyph-Vorlagen kurz auf subtraktiv (abr 2) und stellt sie danach wieder her.
     - Verworfen: Glas-Ziffern (`DrawTextFancyFont`) plus Menü-Kugel, Schriftmix gefiel nicht. Ein Glas-Alphabet gibt es nicht, Menüwörter sind fertige Bilder, und das Glas-`+` ist in PAL ein anderes Zeichen.
   - Widescreen-Mod `kula.widescreen` (in `main` seit 2026-10-15, Spec und Plan unter `docs/superpowers/`):
     - Standardmäßig an. Startfenster 16:9, danach folgt die Ansicht dem Fenster von 4:3 bis maximal 2:1 (darüber Balken). Der Himmel ist nur für ca. 1,7x 4:3-Breite generiert.
     - Plugin `mods/src/kula_widescreen.c` (`psx_mod_set_fixed_display_aspect` + `..._adaptive_...(2, 1)`), dazu `game.toml [widescreen] gte_game_mode = true` (ohne das bleibt die Ausgabe 4:3). `[video] aspect_ratio` allein wirkt nicht mehr.
     - Rand-Culling: Das Spiel verwirft alles außerhalb 0…320 gegen `screenOffsetX` (0x800A2E80, `sltu` + `beq`). Die 54 `beq` stehen als `[widescreen.cull] branch_keep_sites` in der `game.toml` und springen bei Breitbild nicht. Dazu kommen 10 Ladestellen von `screenOffsetX` als `clip_edge_x_load_sites`, die bei Breitbild 320 + Rand liefern. Damit nehmen auch die „behalten“-Ketten (Ecken 1–3) das rechte Band an. Ohne sie fehlte nahe Geometrie unten rechts (Vorderkante, Mac-Befund).
       - Liste nur über `python3 -I tools/find_ws_cull_sites.py disc/SCES_010.00` erzeugen. Es landen nur Adressen im Repo, keine Bytes.
       - Danach `task generate`.
     - `DoSubdivide` bekommt die Grenze im Register `a3` vom Aufrufer, deshalb startet das Skript dort mit vorbelegtem Register.
     - Partikel (`ProcessAndRenderParticles`) haben nur „behalten“-Sprünge und bleiben unverändert. Rechts greift für sie die Ladestelle, links können sie verschwinden. Links (negative X) erfassen die Ladestellen nichts. Dort ist nur die letzte Ecke verbreitert, deshalb sind kleine Popper in den Ecken unten/oben links möglich.
     - Linker Rand (in `main` seit 2026-10-15): Objekte (Items, Schlüssel) sowie Himmel- und Bonus-Hintergrundkacheln haben vor den Polygon-Ketten einen Kugeltest `x + r < Breite + 2r` (vorzeichenlos) gegen eine aus der Breite abgeleitete Grenze (`add t8, t1, r`).
       - Rechts reicht die Ladestelle, links verwarf der Test alles bei x < −r. Repro: W1/L1, rechts antippen, zwei Felder vor, der Schlüssel verschwand bei x ≈ −12.
       - Das Suchskript erfasst abgeleitete Grenzen (`add rd, bound, x`) und findet so 3 weitere Sites: 0x540B4 Items, 0x55C30 Bonus-Hintergrund, 0x565E8 Himmel.
     - Offen, Himmelskeil nach Fenster-Aufziehen im Level: Lädt man bei 16:9 und zieht dann auf 2:1, bleibt oben rechts ein schwarzer Keil, bis sich die Kamera dreht.
       - Repro: Mac-Skript, W1/L1, 757 dunkle Pixel im Band x 420–479, y 0–127.
       - Ursache: `RenderNonSpecialBackground` erneuert die Himmelskacheln nur bei Kamerabewegung. Die Ladestelle lieferte beim letzten Erneuern 320 + 53, deshalb fehlen die Kacheln zwischen +53 und +80.
       - Lädt man direkt bei 2:1 oder dreht die Kamera einmal, ist der Keil weg. Die Bodenlücke links (Nutzer) hat vermutlich denselben Mechanismus.
     - Bodenlücke links (Mac-Live-Aufnahme, 2026-10-16, Branch `fix/widescreen-left-floor`): Am Hieroglyphen-Würfel links der Grube fehlt im linken Band die Vorderfläche bis Spiel-x ≈ 50 (bei 2:1). Rechts tritt das nicht auf, Fenstergröße und Ladezeitpunkt spielen keine Rolle.
       - Ursache: Die „behalten“-Ketten (Ecken 1–3, `sltu x, W` + `bne`) verwerfen negatives X vorzeichenlos. Rechts deckt das die Ladestelle ab, links fehlt eine untere Grenze.
       - Lösung: Alle `sltu`-X-Vergleiche (94) stehen als `screen_x_sites` in der `game.toml`. Sie brauchen die `sltu`-Bandform aus dem Fork (`psx_ws_cull_sltu_band`): Im Breitbild gilt `-4·Rand ≤ x < W`, bei 4:3 das Original. Es stehen nur Adressen im Repo.
       - Verworfen: `[[widescreen.cull.keep]] result = 1`, also „immer sichtbar“. Das behob die Lücke, ließ aber in `RenderLevelGeometryQuads` alle Quads außerhalb des Bildes durch, und das W10-Intro stand ca. 5 s (Pufferüberlauf, per Halbierung auf die 3 Level-Quad-Stellen eingegrenzt). Mit nur einem Rand Reichweite blieb die Lücke, weil große nahe Quads keine Ecke im Band haben.
       - Die vorzeichenbehafteten Vergleiche (Lens-Flares) laufen weiter über `branch_keep_sites`. Partikel (`slt` + `bne`) bleiben links unverändert.
       - Repro, deterministisch (direkt bei 2:1 laden, T0 = erster Frame mit `levelTimeLeft` < 4950, `press` 4 Frames): R@100, U@150, U@200, U@250, L@310, U@370+55·i (i = 0..7). Blick wie im Nutzerbild bei rel ≈ 400–410, Pfad bei ≈ 600–650.
       - Breitenvergleiche zeigen den Fehler nicht, weil er bei jeder Breite im negativen X liegt.
     - HUD in den Ecken: Das Plugin verankert pro VBlank die Pakete von `keySprites` (0x800ADBB4, links) und `fruitSprites` (0x800ADD74, rechts) per `psx_mod_anchor_hud_primitive`. `nw_hud_corners` scheidet aus, weil es auch Himmels-Sprites verschiebt.
       - Gotcha: Das API liest den GP0-Farbbefehl an `primitive + 4`. Bei Kulas zusammengeführtem TSprite (DR_TPAGE + SPRT, 28 Byte) ist deshalb TSprite + 8 zu übergeben, also das SPRT-Tag-Wort.
       - Prüfen: `{"cmd":"ws_tag_stats"}`, `hud.hit` muss steigen.
       - Die „FRUIT BONUS“-Buchstaben (`fruitBonusTextSprites` 0x800ADFA4) verankert dasselbe VBlank-Plugin rechts.
       - Funken beim Einsammeln: Schlüssel, Früchte, Sanduhr und FRUIT BONUS erzeugen Partikel in Bildschirmkoordinaten (`pos.vz < 0`) an festen 4:3-Positionen. Ohne Anker saßen sie um den Rand versetzt neben den Symbolen. Ein Hook um `ProcessAndRenderParticles` (0x12918) ruft das Original und verankert danach jeden dieser Partikel nach seiner Bildhälfte (Mitte = Sanduhr bleibt mittig). Die Pakete werden jeden Frame neu gebaut, deshalb Tagging direkt nach dem Original statt im VBlank.
       - Repro ohne Navigation: im Level `particles[0][0..1]` (0x800AB014, 184 Byte) per `write_ram` mit pos (22, 230, −1) bzw. (208, 233, −1) und `animData` = `PARTICLE_TYPE_PTRS[0]` (0x800A3D80) füllen, dann `numParticles[0]` (0x800A3DB0) = 2. Für FRUIT BONUS `fruitsCollectedBitmask` (0x800A51F0) = 0x1F.
     - Standbilder mit gefüllten Bändern (2026-10-19): Ladebildschirm, Highscore-Tabelle und Memory-Card-Menüs zeichnen den Tasten-Hintergrund `DrawPsxButtonBackground` (0x1D9B4). Vorher zeigten die Bänder alten VRAM-Inhalt.
       - Der Hintergrund ist ein scrollendes Feld aus 20×10 Kacheln zu 48 px (960×480). Das Spiel setzt die XY aller Kacheln, hängt aber nur die in `-48 … W+48` in die OT (`otag[env][0][1024 - (button + 1)]`).
       - Der Hook ruft das Original auf und hängt danach die Kacheln im Band selbst ein. Liegt eine Kachel jenseits des Bands, wird sie um eine Feldbreite (±960) versetzt. Nötig, wenn das Feld ganz zur Seite gescrollt ist. Reine Logik in `mods/src/widescreen_logic.c`, C-Test in `task test`.
       - Ein Flag (gesetzt im Hook, gelöscht bei `RenderBackground` 0x2AA7C, das nur die Hauptschleife ruft) hält die Screens per `psx_mod_set_world_scene_predicate` breit. Sonst fällt der GTE-Klassifikator nach ca. 45 Frames Laden auf 4:3.
       - Texte, Score-Graph-Panel und `LOADING!`-Logo bleiben mittig.
       - Dunkler Verlauf der Tabelle: ein POLY_G4 (`ScoreGraph.polys3[env][1]`), im Highscore-Modus fest auf x 0…320. Der Hook vor `DrawScoreGraph` (0x2224C) setzt die x-Werte jeden Frame auf −Rand … Breite + Rand (erkennbar an Ecke 2 bei x ≤ 0, unter dem Memory-Card-Graph liegt sie bei x + 8).
       - Würfel der Tabelle: `RotSMD_FT4` (0x621B0, PsyQ-Lib) verwirft eine Fläche, sobald keine Ecke mehr in 0 ≤ x < hclip liegt. Im Band fehlten deshalb einzelne Flächen. Der Hook verschiebt GTE-OFX um +Rand, vergrößert `hclip` (Stack-Argument, `sp + 0x14`) um 2 × Rand, ruft das Original und schiebt die geschriebenen Ecken um −Rand zurück.
       - `LoadSaveMenu` (0x43348) und `MemCardUi` (0x43F04) lesen die Karte vor dem ersten Frame. Ohne Hook fiel der Klassifikator in dieser Pause auf 4:3 (Linux: 41 Frames). Beide setzen jetzt beim Eintritt das Standbild-Flag.
       - Verworfen: 4:3 mit Balken über `gpu_ws_set_native_scene_predicate` (Branch `fix/widescreen-still-screens-43`, funktioniert, aber Balken statt Kulisse).
       - Prüfen: `present_native_43` muss 0 bleiben. Der Debug-Screenshot enthält bei breiter Darstellung die Bänder (16:9: 428×256), bei 4:3 nur 320×256 ohne Balken. Müll in den Bändern ist also per Screenshot prüfbar, Balken nur per X11-Capture (`xwd`).
     - Pillen-Effekt (Nachziehen, 2026-10-19, Spec/Plan `docs/superpowers/*/2026-10-19-widescreen-framebuffer-feedback*`):
       - `DrawLethargyEffects` (0x20B30) kopiert jeden Frame das vorherige Bild per zwei 15-bit-Sprites (`lethargyEffectSprite`, 0x800A3EE4) über die Szene. Im VRAM gibt es nur 320 Spalten, deshalb hatte vorher nur die Mitte den Effekt.
       - Framework-Erweiterung im Fork (Branch `feat/ws-feedback-rect`): `gpu_ws_tag_feedback_rect` / `psx_mod_tag_feedback_rect` markiert ein solches Sprite. `gpu.c` setzt es an den Rändern als Band-Rechtecke fort (`ws_feedback_rect.h`, C-Test in `task test`). Die neue Backend-Operation `wide_feedback_rect` (GL inklusive Render-Thread, Software, kein Vulkan) liest aus der breiten Fläche des Quell-Puffers.
       - Gotcha Bit 15: Halbtransparenz wirkt nur auf Texel mit Bit 15. Der Start-Blitz beim Einsammeln (`lethargyEffectPoly`, 0x800A3E94, fest 0…W+1) setzt es in der Mitte, danach erhält es sich über die Kopien. Der Mod zieht den Blitz in die Bänder, und die Band-Kopie behandelt jedes Texel als Bit 15 gesetzt. Sonst verdunkeln Band-Pixel ohne Bit 15 Frame für Frame zu Schwarz, besonders im Pausenmenü (vorher 2 von 3 Läufen).
       - Gotcha GL-Helligkeit (Mac-Befund): Die Mitte liest jeden Frame das auf 5 Bit gepackte VRAM (`PACK_FS`), die Band-Kopie die 8-Bit-Fläche. Ohne dieselbe Abrundung drifteten die Bänder über das Feedback 2–4 Graustufen heller, eine sichtbare Stufe an der 4:3-Kante. Der Band-Shader rundet jetzt wie `PACK_FS` ab und moduliert wie `TEX_FS` (`* 2 / 255`). Messung: mittleres Grau der Spalten links/rechts der Kante, Zeilen 0–199.
       - Software-Renderer: `put_textured` schreibt jetzt das Texel-Bit 15 in den Pixel (vorher verloren, kanonisches VRAM zeigt es: ca. 57 % STP live).
       - Debug: `{"cmd":"wide_full","base_x":0,"alpha":1}` zeigt Bit 15 der breiten Fläche (GL) als Weiß.
       - Repro: Levelauswahl W1/L10, links drehen, 2× vor, rechts drehen, 3× vor, rechts drehen, 2× vor, dann START. Software-Renderer per `--renderer software`.
     - `gpu_state.ws.configured/active = 0` ist bei native-wide normal (Felder des Squash-Pfads). Aussagekräftig sind `mode 2`, `x_margin` (16:9: 53, 2:1: 80), `game_mode`, `present_native_43`.
     - Das Suchskript braucht Python 3.10+ (`int | None`), auf dem Mac also `PYTHON=python3.12`.
     - Prüfen: Debug-Kommando `window_size` (`w`, `h`) ändert das Fenster wie ein Spieler, auch unter Xvfb.
   - 60 FPS: Timer läuft framebasiert mit 50 Hz, die Logik muss entkoppelt werden. Checkliste der Werte pro Frame: rocco `SPEC.md`.
     - Ein reiner NTSC-Patch reicht nicht: Die US-Fassung passt rund 130 Stellen an 60 Hz an (`VID_NTSC ? a : b` im Decomp, z. B. Roll-Beschleunigung 7→6, Drehung 14→16 Frames, Effekt-Timer, 240-Zeilen-Layout). Nur umgeschaltet liefe PAL 20 % zu schnell.
     - Framework-„Smooth motion“ (`[video] frame_generation`, `psxrecomp/docs/FRAME_GENERATION.md`) auf dem Mac getestet (2026-10-15, `PSX_RENDER_THREAD=1 PSX_FRAME_GEN=1`): **erzeugt bei Kula keine Zwischenbilder.**
       - `frame_gen` zählt kaum Flips (`noplan_why` „older list invalid“), obwohl Kula doppelt puffert (`display_x` 0/320 im Wechsel) und 50 Swaps/s laufen. Über 55 s kamen nur ca. 7 Aufrufe pro Sekunde im Flip-Pfad an (`gpu_gl_renderer.c` um Zeile 13110).
       - Nur beim Springen kommen Flips an, die alle verworfen werden („few inliers“).
       - Smoke und Levelauswahl laufen mit eingeschalteter Generierung sauber.
       - Im Launcher fehlen die Zeilen Render-Thread/Smooth motion, obwohl `renderer = "opengl"` (`launcher_model.c:1947`, Ursache offen).
       - Kandidat für ein Upstream-Issue (Flip-Erkennung). Kein Default.
     - **Entscheidung (2026-10-15): ruht, bis sich upstream bei der Frame-Generierung etwas tut.** Untersucht und verworfen bzw. zurückgestellt:
       - Upstream-Issue zur Flip-Erkennung: erst Ursache eingrenzen, braucht Freigabe des Nutzers.
       - NTSC-Weg mit den rund 130 angepassten Werten: großer Aufwand, eigenes Brainstorming.
       - Vor einem neuen Anlauf `frame_gen` auf aktuellem Framework erneut auf dem Mac messen (Demo, Rollen, Springen, Kanten-Kippen).
   - Wobble-Fix
   - HD-Texturen aus TGI/GGI
   - Eigener Ladebildschirm statt Piraterie-Hinweis (`HIRO\WARNING.TIM`, Idee 2026-10-15):
     - Der Hinweis ist der Ladebildschirm des Erststarts (`LoadWarningTim` → `LoadImage` 640x256), ohne feste Wartezeit.
     - Über HD-Texture-Packs geht es nicht, weil `vram-write-` nicht unterstützt wird. Machbar per Mod-Plugin oder Patch (`docs/MOD_PACKAGES.md`).
     - Die Grafik muss selbst erstellt sein.
     - Kürzer wird der Screen nur durch schnelleres Laden. Mac-Messung der eingebauten Mods (OpenBIOS, Zeit bis Menü / Warnscreen):
       - Baseline: 12,1 s / ca. 7 s, Frame 775
       - `psx.enhancement.cd-speed` 4x: 8,2 s / ca. 5 s, Frame 576, Musik und Memcard sauber.
         - **4x hängt aber einen Weltwechsel, der nicht bei Level 1 startet** (gemessen mit der Levelauswahl): Der Level wird nie initialisiert, Bild schwarz, Timer steht. Load Game an Speicherpunkten ist vermutlich auch betroffen, aber nicht geprüft. 1x und 2x laden korrekt (W3/L3, W3/L5, W9/L12). Default deshalb **2x**.
         - Offen: Ursache (CD-Timing in der Runtime?) nicht gefunden. 2x ist ein Workaround, kein Beweis. Kandidat für ein Upstream-Issue mit Repro über `tools/check_level_select.py`.
         - Per Override in `mods/preloaded/packages/psx.enhancement.cd-speed/1.0.0/manifest.toml` standardmäßig an (`default_enabled = true`, Multiplikator 2), im Launcher abschaltbar.
         - Linux: Menü bei Frame 512 statt 713, Demo identisch (Timer-Endwert 3603).
         - Mac (2026-10-15): Launcher zeigt den Mod ohne Zutun an, die Wahl bleibt gespeichert. Warnscreen ca. 5 s bei 4x, ca. 6 s bei 2x (ohne Mod ca. 7 s).
           10 min Spiel mit Weltwechsel, Memory Card und Smoke sauber, 0 FATAL.
         - Das Override ist eine Kopie des Framework-Manifests. Bei Framework-Updates abgleichen.
       - `psx.enhancement.fast-loading` (laut Manifest deprecated): spart nur Wall-Clock, keine Guest-Frames. Zusammen mit CD Speed skippt die XA-Musik.
       - CD Speed Instant: Start 8x langsamer, danach `DISPATCH FATAL: misaligned target 0x00810081`. Upstream führt divisor 4x/instant als „proven unsafe“ (`ENHANCEMENTS.md`, MMX6), deshalb nie verwenden.
   - Muster für Mods und Patches: `hercules-recompiled/port/mods`, `port/patches`
8. Repo-Pflege (Entscheidung des Nutzers):
   - ~~Branch `test/kuseg-boot-smoke` nach `main` mergen~~ (erledigt)
   - ~~`.serena/` committen oder ignorieren~~ (erledigt, gitignored)
   - ~~`Taskfile.yaml` anlegen~~ (erledigt, siehe Build-Gotchas)
   - Offen: `task generate` scheitert ohne `bios/SCPH1001.BIN` (Mac hat nur OpenBIOS). Das Sony-BIOS nur nutzen, wenn die Datei existiert, sonst nur OpenBIOS generieren. Branch-Vorschlag `fix/taskfile-openbios-generate`.
   - Offen, Kleinkram aus dem Review des Levelauswahl-Mods:
     - `g_calling_original` bleibt nach einem Watchdog-longjmp auf 1.
     - `tools/check_level_select.py`: doppelte Reads in den Fehlermeldungen, Docstrings fehlen.
     - C-Tests: zwei prüfen kombinierte Bedingungen, ein Test für `LS_ACT_MOVE` fehlt.
     - Kommentar zur Annahme hinter `LS_MAX_MISSED_VBLANKS` fehlt.
9. Veröffentlichung (Repo auf public stellen). Vorher:
   - ~~Repo öffentlich schalten~~ (erledigt 2026-10-16, https://github.com/zap0xfce2/Kula-World-Recompiled)
   - mit dezgeg klären, ob Symbolnamen und Variablenadressen aus dem Decomp öffentlich stehen dürfen und ob ein eigener PC-Port geplant ist: angefragt in dezgeg/kula-world-decomp#1 (2026-10-16), Antwort offen
   - Entscheidung zu `generated/` (aktuell gitignored)
   - ~~README auf Projektstand bringen~~ (erledigt 2026-10-16, mit Screenshots unter `docs/images/`, Roadmap und KI-Hinweis)
   - erneuter Check der ganzen Historie auf Spieldaten, Secrets und persönliche Pfade
10. Roadmap: nativer Port über das Decomp (siehe Strategie). Vorher bei dezgeg Lizenz und PC-Port-Pläne erfragen.

## macOS
Nativer Build auf dem Mac (Apple Silicon), Anleitung in `docs/BUILD_MACOS.md`. Auf dem Mac wird das private Remote geklont.
- Rolle des Macs: reine Teststation für alles, was unter Linux ohne Display/GPU nicht geht (echte fps, Audio, Launcher-UI, Sichtprüfungen).
  - Der Nutzer sitzt nur für Beobachtungen am Mac (Stoppuhr, Gehör, Eingaben). Alles Messbare automatisiert die Mac-Session über den Debug-Server.
- Testablauf mit der Mac-Session (Claude Code über Remote Control, Name per `ListAgents`):
  - Linux pusht einen Branch und schickt per `SendMessage` den Branch-Namen plus Testauftrag.
  - Der Mac holt den Branch (`git fetch && git checkout <branch>`), baut und testet. Er pusht nicht und committet nicht.
  - Das Ergebnis kommt als Cross-Session-Nachricht zurück, die Doku pflegt nur Linux.
  - Mac-Repo: `origin` per SSH, `.claude/settings.local.json` erlaubt lesende Git-Befehle plus fetch/checkout/switch/submodule update.
  - ccache ist auf dem Mac aktiv, Folgebuilds dauern Sekunden.
  - Mods ohne Launcher reproduzierbar schalten: `<build>/mods/state.toml` (`[[package]] id`, `[[feature]] package_id/id/enabled`, Optionen unter `[feature.values]`). `--no-launcher` übernimmt die Datei.
  - Der Mac hat kein Sony-BIOS mehr und läuft nur mit OpenBIOS.
  - Tests immer stumm: jeder Runtime-Start mit `SDL_AUDIO_DRIVER=dummy` (Freigabe vom 2026-10-19).
  - yabai vor Tests ohne Rückfrage stoppen (`yabai --stop-service`) und danach wieder starten (`yabai --start-service`), weil es `window_size` aushebelt (Freigabe vom 2026-10-19).
- 2026-10-15 auf M1 Pro verifiziert: Build in 2:35 min, Launcher, Boot bis Demo, 49,5 fps, XA und SFX ok. Memory Card unter Retail und OpenBIOS ok. Levelauswahl-Mod ok. Ending-FMV ok (2026-10-19). Offen: Controller.
- Gotchas:
  - Ein verwaister `CommandLineTools/usr/include/c++/v1` überdeckt die SDK-Header (`'string' file not found`).
  - `runtime.cmake` sucht `python` vor `python3`, deshalb `-DPSX_PYTHON=$(command -v python3.12)`.
  - Das Default-`python3` ist 3.9, also überall `python3.12`.
- Der Launcher schreibt bei jedem Start `[controller] multitap_analog` in `game.toml`. Der Wert ist deshalb fest eingetragen, damit kein Diff entsteht.
- Der Launcher schaltet BIOS-Call-HLE ein (`bios_backend=HLE`). Mit `--no-launcher` gilt der Default LLE. Für A/B gegen Beetle `PSX_BIOS_HLE=0` setzen.

## Build-Gotchas (Alpine/musl)
Bevorzugt über die `Taskfile.yaml` (go-task, `task --list`). `task generate` läuft auch ohne Sony-BIOS. Dann regeneriert es nur OpenBIOS (Mac). `task all` erledigt Emitter, Generate und Dev-Build. Die musl-Flags setzt sie automatisch. Weitere Tasks:
- `run`, `run:dev`, `beetle`: Starten, headless mit `RUNNER="xvfb-run -a"`.
- `smoke PORT=4380`, `test`, `lint`.
- Auf dem Mac `PYTHON=python3.12`.

Der Ablauf als rohe Befehle (Begründung der Flags unten):
```sh
./psxrecomp/tools/ci/build_emitters.sh
python3 psxrecomp/psxrecomp_cli.py generate --config game.toml --project-root . \
    --disc disc/SCES01000.CUE --bios bios/SCPH1001.BIN --no-toolchain-download
(cd psxrecomp && PSXRECOMP_BIOS_BUILD=../build-recompiler bash tools/regen_bios.sh --config bios/SCPH1001.toml)
cmake -S . -B build-dev -G Ninja -DCMAKE_BUILD_TYPE=Release -DPSX_DEBUG_TOOLS=ON \
    -DCMAKE_C_STANDARD_LIBRARIES=-lucontext -DCMAKE_CXX_STANDARD_LIBRARIES=-lucontext
cmake --build build-dev
```
- Systempakete: `sudo apk add cmake samurai pkgconf sdl3-dev mesa-dev linux-headers` (samurai liefert `ninja`). Zum Headless-Testen: `xvfb xvfb-run mesa-dri-gallium`.
- `psxrecomp_cli.py generate` **immer mit `--no-toolchain-download`**. Ohne das Flag passiert Folgendes:
  - Es lädt die glibc-Toolchain `cmake-clang-v1` nach `~/.local/share/retcomm`, die unter musl nicht läuft.
  - Es trägt PATH-Hooks in `~/.zshrc` und `~/.profile` ein.
  - Es schreibt `toolchain/.psxrecomp-bin`.
  - Das CLI durchsucht `~/.local/share/retcomm` immer. Der Ordner darf also nicht existieren (glibc-Reste wurden am 2026-10-15 gelöscht).
- Nach `generate --bios` fehlt `psxrecomp/generated/SCPH1001.emitter.sha` (CLI-Lücke), dann meldet CMake „BIOS … STALE“. Abhilfe: `regen_bios.sh` wie oben. Das Skript sucht nur `psxrecomp/recompiler/build*`. Die Ausgabe von `build_emitters.sh` liegt aber in `build-recompiler/`, deshalb `PSXRECOMP_BIOS_BUILD=../build-recompiler` setzen (relativ zu `psxrecomp/`). Hier lief es bisher nur wegen eines alten `recompiler/build`.
- musl hat keine `getcontext`/`makecontext`/`swapcontext`, die `psx_fiber.c` braucht. Abhilfe: `sudo apk add libucontext-dev` und bei jedem CMake-Configure `-DCMAKE_C_STANDARD_LIBRARIES=-lucontext -DCMAKE_CXX_STANDARD_LIBRARIES=-lucontext`.
- Release-Builds haben keinen Debug-Server. Für Tests deshalb `build-dev` mit `-DCMAKE_BUILD_TYPE=Release -DPSX_DEBUG_TOOLS=ON`. Start: `xvfb-run -a ./build-dev/Kula_World_Recompiled --no-launcher --bios bios/SCPH1001.BIN --disc disc/SCES01000.CUE --debug-port 4370`.
- Generate dauert ca. 2 min (569 Shards, 31 Mio. Zeilen C, ~950 MB). Der Runtime-Build dauert auf 8 Kernen ca. 23 min.
- Serena mit C (`clangd`): `sudo apk add clang-extra-tools`. Dazu `.claude/settings.local.json` mit `env.UV_PYTHON=/usr/bin/python3` (lokal, über `.git/info/exclude` ignoriert), danach `/mcp` reconnect. Unter uvs statischem musl-Python liefert `platform.libc_ver()` `('libc', '')`, Serena meldet dann „Unknown platform“. `compile_commands.json` im Root ist ein Symlink auf `build-dev/` (`-DCMAKE_EXPORT_COMPILE_COMMANDS=ON`).
- Oracle: `psxrecomp/beetle-psx` (im Submodule gitignored) auf `5759277b` plus `docs/beetle_*.patch`, siehe `psxrecomp/docs/beetle-linux.md`.

## Smoke-Test
- `tools/smoke_boot.py --port 4370|4380` liest `gameState`, `isDemoMode`, `levelTimeLeft` usw. (Adressen aus dem Decomp) und speichert Screenshots nach `analysis/smoke/`.
- Ohne Eingabe startet das Spiel nach 2000 Menü-Frames (40 s) den Demo-Modus. „Demo aktiv und Timer läuft runter“ beweist also BIOS → Titel → Menü → 3D-Level.
- Tests: `python3 -m unittest discover -s tests`.
- Bewährte Methodik für Eingabe-Repros (Mac-Erfahrung):
  - Eingaben erst ab T0 + ca. 60 Frames, früher ignoriert das Spiel sie.
  - `press` mit 4 Frames entspricht genau 90° bzw. 1 Feld, 18 Frames drehen zu weit.
  - Screenshot pro Frame per Polling auf `frame` (ca. 50/s).
  - Himmelslücken-Scanner: 60-px-Band am Rand, obere 128 Zeilen, Graustufe < 4 %.
  - Auf dem Mac geht nur der Debug-Server-Screenshot, `screencapture` hat keine Berechtigung. Das Mac-Startfenster ist 853x480 (`x_margin` 54).
  - Ein Tiling-WM (yabai) hebelt `window_size` aus, `x_margin` bleibt dann bei jeder Fenstergröße gleich. Für Tests yabai ausschalten.
  - Im Menü (640 px Breite) ist `x_margin` doppelt so groß wie im Level (16:9: 107, 2:1: 160).
- Lange Testsitzungen: `task freeze-timer` (`tools/freeze_timer.py`) hält den Level-Timer per `write_ram` voll (nur Dev-Build). `SDL_AUDIO_DRIVER=dummy` schaltet den Ton ab, das Spiel läuft normal weiter.
- `write_ram` schreibt ein Byte pro Anfrage.
- Vor jedem Lauf prüfen, dass kein alter Runtime-Prozess den Debug-Port hält (`pgrep -af Kula_World`). Verliert ein Prozess sein Xvfb, nimmt er weiter Verbindungen an, antwortet aber nicht mehr (Timeout bei `frame`), und reagiert nicht auf SIGTERM, dann `kill -9`.
- Debug-Protokoll: eine Anfrage pro TCP-Verbindung. Frame-Nummer: Runtime über `frame`, Beetle im `ping`.
- **`press`/`set_input` erwarten das Pad-Wort active-low** (`0xFFFF` = nichts gedrückt). Kreuz drücken heißt also `0xFFFF ^ 0x4000`. Bits: `PAD_*` im Decomp `include/common.h`.
- Spielstart per Eingabe: Kreuz → Untermenü (`curMenu` 3) → Kreuz → 1-Spieler-Arcade (Welt 0, Level 0). Spielerposition `playerCombinedPos` = `0x800A45D0` (8 Byte).

## Werkzeuge in dieser Umgebung
- Serena immer nutzen, wo es geht: Code lesen, navigieren und ändern über die Symbol-Werkzeuge (`find_symbol`, `get_symbols_overview`, `find_referencing_symbols`, `replace_symbol_body` usw.) statt `grep`/`sed`/Volltext-Lesen. Gilt auch für `psxrecomp/` (Wunsch des Nutzers vom 2026-10-19).
- Erste Anlaufstelle für Code-Verständnis ist das dezgeg-Decomp, nicht Ghidra.
- Ghidra ist optional (noch nicht installiert, kein JDK), nur für die 27 ASM-Funktionen oder zum Gegenprüfen.
  Dann mit `ghidra_psx_ldr` die EXE im KUSEG-Segment laden (Basis `0x00011000`) und Funktionsgrenzen per `psxrecomp-analyze --emit-ghidra` importieren.
- Oracle: psx-beetle aus psxrecomp (`docs/beetle-linux.md`), gleiches TCP-Debug-Protokoll wie die Runtime.
- psxrecomp-Regeln aus dessen `CLAUDE.md` beachten:
  - Kein HLE, keine Stubs
  - Generierten Code nie von Hand ändern
  - Kein printf-Debugging, stattdessen Debug-Server-Kommandos
