# CLAUDE.md – Kula World Recompiled

Statischer Recomp von **Kula World (PAL, SCES-01000)** zu einer nativen Linux/Windows-Anwendung
auf Basis von [psxrecomp](https://github.com/RetroPortingToolKit/psxrecomp).
Vorlage für Projektstruktur, Mods und Launcher: [hercules-recompiled](https://github.com/obaidr1/hercules-recompiled).

## Zusammenarbeit
- Antworte immer auf Deutsch und duze den Nutzer.
- Der Nutzer ist Softwareentwickler, IT-Experte und DevOps Engineer. Erkläre keine Grundlagen.
- Code nicht ausführlich erklären, sondern nach Clean-Code-Prinzip kommentieren.
- Default-Plattform ist Linux. Editor-Anweisungen immer mit `vi`, nie `nano`.
- Git-Freigabe (2026-10-15): Solange das Repo privat ist, darf ohne Rückfrage auf `origin` committet und gepusht werden.
  - Weiterhin nur mit Freigabe: Force-Push, Historie umschreiben, Sichtbarkeit ändern, Issues/PRs in fremden Repos.
  - Vor jedem Commit `git status` prüfen und sicherstellen, dass keine Spieldaten und keine Secrets dabei sind.
- Spekuliere nicht über Hardware-Verhalten. Verifiziere gegen den Oracle-Emulator (Beetle) oder sag "unbekannt".

## Rechtliches – harte Regel
**Niemals Spieldaten committen**: kein BIOS, keine `.bin`/`.cue`, keine `SCES_010.00`,
keine extrahierten Assets und keine Disassembly mit Original-Bytes.
`disc/`, `bios/`, `generated/` (bis zur Release-Entscheidung) gehören in `.gitignore`.

## Stand (2026-10-15)
Voranalyse abgeschlossen, Repo nach New Project Layout aufgesetzt (Remote `github.com/zap0xfce2/kula-world-recompiled`, vorerst privat). **KUSEG-Smoke-Test bestanden**, Details und A/B-Tabelle in `NOTES.md`.
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
3. ~~Recompiler bauen, BIOS und Spiel generieren, Runtime bauen~~ (erledigt, Befehle und Fallstricke unter Build-Gotchas)
4. ~~KUSEG-Smoke-Test: Boot → Titel → Level, A/B gegen psx-beetle~~ (erledigt)
   - Interaktiv verifiziert: Spielstart per Eingabe, Timer läuft, Kugel rollt (`analysis/play-native2/`).
5. Offene Punkte aus dem Smoke-Test:
   - ~~Ergebnis upstream melden~~ (erledigt 2026-10-15): RetroPortingToolKit/psxrecomp#671 (KUSEG) und #672 (6 Portabilitäts-Befunde). Quelle: `docs/upstream-report-kuseg.md`.
   - Auf dem Mac verifiziert: XA-Musik und SFX, Memory Card (`saves/card1.mcd`), LLE-Boot. Offen: Controller (kein Gamepad zur Hand) und Ending-FMV (per Levelauswahl Welt 10 erreichbar, noch nicht gezielt geprüft).
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
     - Offen: Speicherpunkte nach Start ≠ 1/1 im Spiel bestätigen (laut Decomp unterdrückt `cheated` sie), Ending-FMV über Welt 10.
     - Plugin `mods/src/kula_level_select.c` + reine Logik `mods/src/level_select_logic.c` (C-Test in `task test`).
     - Hooks über `game.toml [recompiler] mod_function_entry_funcs`, danach `task generate`.
     - Prüfen: `tools/check_level_select.py --world W --level L` gegen eine frisch gestartete Dev-Runtime.
     - Gotcha: `DrawTextCrappyFont` zeichnet eine Zeile nur bei `\n`. `<`/`>` sind in dieser Schrift Tasten-Symbole.
     - Optik: alles in der kleinen Schrift, hellblau getönt. START zentriert, WORLD/LEVEL rechtsbündig an gemeinsamer Kante, `-`, Zahl und `+` je in fester Spalte, die gewählte Zeile hell, leichter Schatten. Kreis und Dreieck gehen zurück (Kreis nur im Untermenü).
     - Gotcha Schatten: Die kleine Schrift blendet additiv (`fontSprites` 0x800AA47C, abr 1), eine dunkle Kopie bleibt unsichtbar. Der Mod schaltet für den Schatten-Durchgang die Glyph-Vorlagen kurz auf subtraktiv (abr 2) und stellt sie danach wieder her.
     - Verworfen: Glas-Ziffern (`DrawTextFancyFont`) plus Menü-Kugel, Schriftmix gefiel nicht. Ein Glas-Alphabet gibt es nicht, Menüwörter sind fertige Bilder, und das Glas-`+` ist in PAL ein anderes Zeichen.
   - Widescreen-Mod `kula.widescreen` (Branch `feat/widescreen-mod`, Spec und Plan unter `docs/superpowers/`):
     - Standardmäßig an. Startfenster 16:9, danach folgt die Ansicht dem Fenster von 4:3 bis maximal 2:1 (darüber Balken). Der Himmel ist nur für ca. 1,7x 4:3-Breite generiert.
     - Plugin `mods/src/kula_widescreen.c` (`psx_mod_set_fixed_display_aspect` + `..._adaptive_...(2, 1)`), dazu `game.toml [widescreen] gte_game_mode = true` (ohne das bleibt die Ausgabe 4:3). `[video] aspect_ratio` allein wirkt nicht mehr.
     - Rand-Culling: Das Spiel verwirft alles außerhalb 0…320 gegen `screenOffsetX` (0x800A2E80, `sltu` + `beq`). Die 54 `beq` stehen als `[widescreen.cull] branch_keep_sites` in der `game.toml` und springen bei Breitbild nicht.
       - Liste nur über `python3 -I tools/find_ws_cull_sites.py disc/SCES_010.00` erzeugen. Es landen nur Adressen im Repo, keine Bytes.
       - Danach `task generate`.
     - `DoSubdivide` bekommt die Grenze im Register `a3` vom Aufrufer, deshalb startet das Skript dort mit vorbelegtem Register.
     - Partikel (`ProcessAndRenderParticles`) haben nur „behalten“-Sprünge und bleiben unverändert. Sie können am breiten Rand verschwinden. In `RenderDispList`/`DrawLasers` ist nur die letzte Ecke verbreitert, kleine Popper in den Ecken oben/unten sind möglich.
     - Offen: HUD in die Ecken. `nw_hud_corners` verschiebt auch Himmels-Sprites und erzeugt dunkle Streifen.
     - `gpu_state.ws.configured/active = 0` ist bei native-wide normal (Felder des Squash-Pfads). Aussagekräftig sind `mode 2`, `x_margin` (16:9: 53, 2:1: 80), `game_mode`, `present_native_43`.
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
   - mit dezgeg klären, ob Symbolnamen und Variablenadressen aus dem Decomp (z. B. in `tools/smoke_boot.py`) öffentlich stehen dürfen
   - Entscheidung zu `generated/` (aktuell gitignored)
   - README auf Projektstand bringen
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
- 2026-10-15 auf M1 Pro verifiziert: Build in 2:35 min, Launcher, Boot bis Demo, 49,5 fps, XA und SFX ok. Memory Card unter Retail und OpenBIOS ok. Levelauswahl-Mod ok. Offen: Controller, Ending-FMV.
- Gotchas:
  - Ein verwaister `CommandLineTools/usr/include/c++/v1` überdeckt die SDK-Header (`'string' file not found`).
  - `runtime.cmake` sucht `python` vor `python3`, deshalb `-DPSX_PYTHON=$(command -v python3.12)`.
  - Das Default-`python3` ist 3.9, also überall `python3.12`.
- Der Launcher schreibt bei jedem Start `[controller] multitap_analog` in `game.toml`. Der Wert ist deshalb fest eingetragen, damit kein Diff entsteht.
- Der Launcher schaltet BIOS-Call-HLE ein (`bios_backend=HLE`). Mit `--no-launcher` gilt der Default LLE. Für A/B gegen Beetle `PSX_BIOS_HLE=0` setzen.

## Build-Gotchas (Alpine/musl)
Bevorzugt über die `Taskfile.yaml` (go-task, `task --list`). `task all` erledigt Emitter, Generate und Dev-Build. Die musl-Flags setzt sie automatisch. Weitere Tasks:
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
- Oracle: `psxrecomp/beetle-psx` (im Submodule gitignored) auf `5759277b` plus `docs/beetle_*.patch`, siehe `psxrecomp/docs/beetle-linux.md`.

## Smoke-Test
- `tools/smoke_boot.py --port 4370|4380` liest `gameState`, `isDemoMode`, `levelTimeLeft` usw. (Adressen aus dem Decomp) und speichert Screenshots nach `analysis/smoke/`.
- Ohne Eingabe startet das Spiel nach 2000 Menü-Frames (40 s) den Demo-Modus. „Demo aktiv und Timer läuft runter“ beweist also BIOS → Titel → Menü → 3D-Level.
- Tests: `python3 -m unittest discover -s tests`.
- Debug-Protokoll: eine Anfrage pro TCP-Verbindung. Frame-Nummer: Runtime über `frame`, Beetle im `ping`.
- **`press`/`set_input` erwarten das Pad-Wort active-low** (`0xFFFF` = nichts gedrückt). Kreuz drücken heißt also `0xFFFF ^ 0x4000`. Bits: `PAD_*` im Decomp `include/common.h`.
- Spielstart per Eingabe: Kreuz → Untermenü (`curMenu` 3) → Kreuz → 1-Spieler-Arcade (Welt 0, Level 0). Spielerposition `playerCombinedPos` = `0x800A45D0` (8 Byte).

## Werkzeuge in dieser Umgebung
- Erste Anlaufstelle für Code-Verständnis ist das dezgeg-Decomp, nicht Ghidra.
- Ghidra ist optional (noch nicht installiert, kein JDK), nur für die 27 ASM-Funktionen oder zum Gegenprüfen.
  Dann mit `ghidra_psx_ldr` die EXE im KUSEG-Segment laden (Basis `0x00011000`) und Funktionsgrenzen per `psxrecomp-analyze --emit-ghidra` importieren.
- Oracle: psx-beetle aus psxrecomp (`docs/beetle-linux.md`), gleiches TCP-Debug-Protokoll wie die Runtime.
- psxrecomp-Regeln aus dessen `CLAUDE.md` beachten:
  - Kein HLE, keine Stubs
  - Generierten Code nie von Hand ändern
  - Kein printf-Debugging, stattdessen Debug-Server-Kommandos
