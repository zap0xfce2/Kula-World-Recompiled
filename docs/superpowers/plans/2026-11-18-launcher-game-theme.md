# Launcher-Farben pro Spiel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ein Spiel liefert eine INI-Datei mit Farben, die Launcher und Menü im Spiel über das Konsolen-Schema legen; Kula nutzt das für die Palette „B · Himmel“.

**Architecture:** recomp-ui bekommt eine kleine Override-Einheit (Parser, Anwenden, prozessweiter Cache mit Lazy-Load aus `<Exe-Ordner>/assets/theme_game.ini`). Jede Stelle, die heute `launcher_theme_by_name` aufruft, ruft danach `launcher_theme_apply_game_overrides`. `recomp_ui_add(... THEME <ini>)` stagt die Datei wie `BRAND`; psxrecomp reicht `LAUNCHER_THEME` durch.

**Tech Stack:** C11 (recomp-ui `src/common`), CMake, SDL3 (`SDL_GetBasePath`, über `launcher_sdlcompat.h`), CTest.

**Spec:** `docs/superpowers/specs/2026-11-18-launcher-game-theme-design.md`

## Global Constraints

- INI-Abschnitt `[colors]`, ein Schlüssel je Token, Wert `#RRGGBB` oder `#RRGGBBAA` (Hex, Groß-/Kleinschreibung egal). Ohne Alpha gilt `FF`.
- Schlüssel = Feldnamen von `LauncherTheme`: `background`, `background2`, `panel`, `panel_hovered`, `control`, `control_hovered`, `border`, `accent`, `accent_dim`, `accent_text`, `accent2`, `text`, `text_muted`, `good`, `warn`, `focus_ring`.
- Unbekannte Schlüssel und kaputte Werte werden übersprungen, je eine Zeile auf stderr mit Präfix `recomp-ui: theme_game.ini:`. Fehlende Datei: still, keine Änderung. Der Launcher startet immer.
- Kommentare nur mit `;` am Zeilenanfang (Werte beginnen mit `#`). CRLF und Leerzeichen um `=` sind erlaubt.
- Gestagter Name: `assets/theme_game.ini` neben der Exe (`$<TARGET_FILE_DIR>/assets/`).
- Abstände, Radien, Schriften, Scanlines und `background_style` bleiben unberührt.
- recomp-ui-Arbeit auf Fork-Branch `feat/game-theme-overrides` ab `b54c7eb`; psxrecomp auf Fork-Branch `feat/launcher-theme` ab `da9be047`. Upstream-PRs nur nach Freigabe des Nutzers.
- Kula: Branch `feat/launcher-game-theme`. Spieldaten nie committen.

## Review Focus

- Datei mit CRLF-Zeilenenden (Windows-Editor): Werte müssen trotzdem greifen → Test `crlf_lines_apply`.
- Schlüssel außerhalb von `[colors]` (z. B. Tippfehler im Abschnitt): werden ignoriert, nicht angewendet → Test `keys_outside_colors_section_ignored`.
- Kurzform oder Müll (`#FFF`, `#GGGGGG`, `ECC57D` ohne `#`): übersprungen, übrige Zeilen gelten → Test `invalid_value_skipped_others_apply`.
- `--no-launcher`: Das Menü im Spiel bekommt die Farben trotzdem (Lazy-Load unabhängig vom Launcher) → Linux-Prüfung in Task 4.
- Datei fehlt (andere Spiele, ältere Builds): Schema unverändert → Test `missing_file_leaves_theme_unchanged`.

---

### Task 1: Override-Einheit in recomp-ui

**Files:**
- Create: `recomp-ui/src/common/launcher_theme_overrides.h`, `recomp-ui/src/common/launcher_theme_overrides.c`
- Test: `recomp-ui/tests/launcher_theme_overrides_test.c`
- Modify: `recomp-ui/CMakeLists.txt` (Test-Executable wie `recomp-ui-ips-patch-test`, ohne SDL: Lazy-Load-Pfad im Test nicht nutzen)

**Interfaces:**
- Produces:
  - `typedef struct { uint32_t set_mask; LngColor color[16]; } LauncherThemeOverrides;` Bit i = Token i in der Reihenfolge der Global Constraints.
  - `int launcher_theme_overrides_parse(const char* text, LauncherThemeOverrides* out);` → Anzahl gültiger Einträge.
  - `void launcher_theme_overrides_apply(const LauncherThemeOverrides* o, LauncherTheme* t);`
  - `int launcher_theme_load_game_overrides(const char* path);` füllt den Prozess-Cache (fehlende Datei = leerer Cache, Rückgabe 0), markiert ihn als geladen.
  - `void launcher_theme_apply_game_overrides(LauncherTheme* t);` lädt beim ersten Aufruf ohne vorheriges Load aus `SDL_GetBasePath()` + `assets/theme_game.ini`, wendet dann den Cache an.

- [ ] **Step 1: Failing tests schreiben** (je Test ein Assert)
  - `accent_hex_applies`: `"[colors]\naccent = #ECC57D\n"` → `t.accent` ≈ (0xEC/255, 0xC5/255, 0x7D/255, 1.0), Toleranz 1e-4.
  - `alpha_suffix_applies`: `panel = #0F2547F0` → `t.panel.a` ≈ 0xF0/255.
  - `unset_token_keeps_scheme`: nur `accent` gesetzt → `t.text` gleich `launcher_theme_psx().text`.
  - `crlf_lines_apply`: `"[colors]\r\naccent = #ecc57d\r\n"` → Rückgabe 1.
  - `keys_outside_colors_section_ignored`: `"[other]\naccent = #ECC57D\n"` → Rückgabe 0.
  - `invalid_value_skipped_others_apply`: `accent = #FFF`, `text = #GGGGGG`, `border = 25497D`, `panel = #0F2547` → Rückgabe 1.
  - `comment_line_ignored`: `"; note\n[colors]\naccent = #ECC57D\n"` → Rückgabe 1.
  - `missing_file_leaves_theme_unchanged`: `launcher_theme_load_game_overrides("/nonexistent/theme_game.ini")` → 0, danach `apply` lässt `accent` wie PSX.
  - `load_file_applies`: Temp-Datei mit `accent = #ECC57D` → nach Load + `launcher_theme_apply_game_overrides` ist `t.accent.r` ≈ 0xEC/255.

- [ ] **Step 2: Tests laufen lassen, schlagen fehl**
  Run: `cmake -S recomp-ui -B /tmp/rui-test -DRECOMP_UI_BUILD_TESTS=ON && cmake --build /tmp/rui-test --target recomp-ui-launcher-theme-overrides-test` (Testschalter-Name aus `recomp-ui/CMakeLists.txt` übernehmen)
  Expected: Build-Fehler, Header fehlt.

- [ ] **Step 3: Implementieren**
  Zeilenweiser Parser über den Text (Abschnitt merken, `;`-Zeilen und Leerzeilen überspringen, `\r` abschneiden, Schlüssel per Tabelle `{name, offsetof(LauncherTheme, field)}`). Datei lesen mit `fopen`/`fread` (keine neue Abhängigkeit). SDL nur im Lazy-Load, über `launcher_sdlcompat.h`.

- [ ] **Step 4: Tests grün**
  Run: `ctest --test-dir /tmp/rui-test -R theme-overrides --output-on-failure`
  Expected: alle bestanden.

- [ ] **Step 5: Commit** (im Submodul, Fork-Branch `feat/game-theme-overrides`)
  `git commit -m "feat: let a game override launcher theme colors from an INI file"`

### Task 2: Anwenden in Launcher und Runtime-UI, Staging per `THEME`

**Files:**
- Modify: `recomp-ui/src/common/launcher_ng_capi.c:225`, `recomp-ui/src/common/recomp_runtime_ui.c:724,769`, `recomp-ui/src/common/backends/imgui/runtime_ui_imgui.cpp:325,329` (nach jedem `launcher_theme_by_name` → `launcher_theme_apply_game_overrides(&theme)`; in Zeile 325 den Temporärwert vorher in eine Variable ziehen)
- Modify: `recomp-ui/recomp_ui.cmake` (Argument `THEME` in `cmake_parse_arguments` Zeile 149, POST_BUILD-Kopie nach `$<TARGET_FILE_DIR:${TGT}>/assets/theme_game.ini` wie `RUI_BRAND` Zeile 389; `launcher_theme_overrides.c` in die Quellliste neben `launcher_ng_capi.c` Zeile 220; Kopfkommentar Zeile 10 ergänzen)
- Modify: `recomp-ui/README.md:696` (Zeile `THEME <path>` unter `BRAND`)

**Interfaces:**
- Consumes: `launcher_theme_apply_game_overrides(LauncherTheme*)` aus Task 1.
- Produces: `recomp_ui_add(<tgt> ... THEME <ini>)`.

- [ ] **Step 1: Ändern wie oben**
- [ ] **Step 2: Bestehende recomp-ui-Tests grün**
  Run: `cmake --build /tmp/rui-test && ctest --test-dir /tmp/rui-test --output-on-failure`
  Expected: keine neuen Fehler gegenüber `b54c7eb`.
- [ ] **Step 3: Commit**
  `git commit -m "feat: apply game theme overrides in the launcher and runtime UI"`, Branch pushen nach `fork`.

### Task 3: psxrecomp reicht `LAUNCHER_THEME` durch

**Files:**
- Modify: `psxrecomp/runtime/runtime.cmake:1570` (`LAUNCHER_THEME` neben `LAUNCHER_BRAND`), `:2482` (`THEME "${PSXRT_LAUNCHER_THEME}"` an `_psx_recomp_ui_args` wie `BRAND`), dazu die Doku-Stelle, die `LAUNCHER_BRAND` beschreibt (`grep -rn LAUNCHER_BRAND psxrecomp/docs`).

**Interfaces:**
- Consumes: `recomp_ui_add(... THEME <ini>)` aus Task 2.
- Produces: `psxrecomp_add_game_runtime(... LAUNCHER_THEME <ini>)`.

- [ ] **Step 1: Ändern**
- [ ] **Step 2: Commit** auf Fork-Branch `feat/launcher-theme` ab `da9be047`, `git commit -m "feat: pass a game launcher theme to recomp-ui"`, pushen nach `fork`.

### Task 4: Kula bindet die Palette ein

**Files:**
- Create: `assets/launcher/theme.ini` (Abschnitt `[colors]`, Werte exakt aus der Tabelle im Spec; Kopfkommentar mit `;`: eigene Palette nach Launcher-Entwurf B, keine Spiel-Assets)
- Modify: `CMakeLists.txt:61` (`LAUNCHER_THEME "${CMAKE_CURRENT_SOURCE_DIR}/assets/launcher/theme.ini"` unter `LAUNCHER_BRAND`)
- Modify: `.gitmodules` (psxrecomp auf `https://github.com/zap0xfce2/psxrecomp.git`, Branch `feat/launcher-theme`; recomp-ui Branch `feat/game-theme-overrides`), Submodule-Pins.
- Modify: `CLAUDE.md` (Abschnitt Launcher-Art: Mechanismus, Pfade, Fork-Pins, Rückweg nach Upstream-Merge), `README.md` (Submodul-Hinweis).

- [ ] **Step 1: Ändern, `cmake -S . -B build-dev && cmake --build build-dev`**
  Expected: Build ok, `build-dev/assets/theme_game.ini` existiert und ist gleich `assets/launcher/theme.ini` (`cmp`).
- [ ] **Step 2: Linux-Prüfung**
  - `task test PYTHON=.venv-hd/bin/python` grün.
  - Launcher unter Xvfb starten (`xvfb-run -a ./build-dev/Kula_World_Recompiled`), X11-Capture: Hintergrund ist nicht mehr PSX-Blau (`#0A0C14`); gegen `#081429` prüfen, bei vertauschtem Rot/Blau (llvmpipe-Gotcha, gilt sicher für Bilder) gegen `#291408`. stderr ohne `theme_game.ini:`-Zeilen.
  - `--no-launcher` mit Debug-Port, Menü im Spiel öffnen (`PSX_INTERNAL_RESOLUTION=native PSX_DYNRES=0 SDL_AUDIO_DRIVER=dummy`), Screenshot, Panel-Farbe gegen `#0F2547` (oder vertauscht `#47250F`).
  - Smoke `demo_gameplay_reached`, 0 Misses.
- [ ] **Step 3: Commit + Push** `git commit -m "feat: Kula World launcher colors (sandstone and sky)"`
- [ ] **Step 4: Mac-Abnahme** per `SendMessage` an `kula-world-mac`: Branch holen, Submodule aktualisieren, bauen, Launcher und Menü im Spiel zeigen. Prüfen: Farben wie Entwurf B, Lesbarkeit von Text, PLAY-Beschriftung, gelber Fokusrahmen per Pad. Ergebnis in `CLAUDE.md`.
- [ ] **Step 5: Nach Abnahme** Merge nach `main`, Roadmap-Punkt abhaken. Upstream-PRs (recomp-ui, psxrecomp) erst nach Freigabe des Nutzers.
