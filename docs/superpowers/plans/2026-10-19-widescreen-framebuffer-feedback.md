# Widescreen Framebuffer-Feedback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Kulas Pillen-Effekt (Framebuffer-Feedback-Sprites) läuft im Breitbild über die volle Breite.

**Architecture:** Ein Titel taggt Feedback-Sprites (`gpu_ws_tag_feedback_rect`). `gpu.c` erzeugt für getaggte Sprites am Bildrand Band-Rechtecke und ruft eine neue optionale Backend-Operation `wide_feedback_rect`, die nur in die aktuelle breite Fläche zeichnet und aus der breiten Fläche des Quell-Puffers liest. GL und Software implementieren sie, der Kula-Mod taggt die zwei Effekt-Sprites.

**Tech Stack:** C (psxrecomp-Runtime im Fork `psxrecomp/`), OpenGL 3.3 Shader, Kula-Mod-Plugin.

**Spec:** `docs/superpowers/specs/2026-10-19-widescreen-framebuffer-feedback-design.md`

## Global Constraints

- Kanonisches VRAM und 4:3 bleiben bitgleich. Ohne Tag passiert nichts Neues.
- Akzeptierte Sprite-Befehle: 0x64–0x67. Texturseite 15-bit direkt (`depth == 2`).
- Backend-Operation ist optional (NULL = nicht unterstützt). Vulkan bekommt sie nicht.
- Semi-Modi: 0: B/2 + F/2, 1: B + F, 2: B − F, 3: B + F/4, opak = −1. Texel 0x0000 transparent. Modulation Texel × Farbe / 128, bei `raw` keine.
- Kein printf-Debugging, generierten Code nie von Hand ändern, Serena für Navigation und Edits.
- Fork-Änderungen auf neuem Fork-Branch `feat/ws-feedback-rect` von `feat/ws-screen-x-sltu-band`. Commits und Pushes nur nach Rückfrage beim Nutzer.

## Review Focus

- Sprite berührt keinen Rand (z. B. kleines Sprite mitten im Bild): keine Band-Rechtecke. Test in Task 1.
- Rand 0 (Fenster exakt 4:3) oder native-wide aus: keine Band-Rechtecke, kein Backend-Aufruf. Test in Task 1.
- Quelle liegt in keinem bekannten Framebuffer (normale 15-bit-Textur): Tag wirkungslos. Prüfung in Task 2 (Bedingung vor dem Aufruf), manuell im Level.
- Fenster-Aufziehen während des Effekts: Rand ändert sich pro Frame, Band-Rechtecke folgen. Prüfung in Task 5 (live `window_size`).
- Quell-Fläche existiert noch nicht (erster Frame nach Umschalten): Backend zeichnet nichts, kein Absturz. Guard in Task 3/4.

---

### Task 1: Span-Logik `ws_feedback_rect.h`

**Files:**
- Create: `psxrecomp/runtime/include/ws_feedback_rect.h`
- Create: `psxrecomp/runtime/tests/test_ws_feedback_rect.c`
- Modify: `psxrecomp/runtime/CMakeLists.txt` (neben `ws_repeat_rect_test`)

**Interfaces:**
- Produces:
  ```c
  typedef struct { int32_t dst_x, src_x, w; } WsFeedbackSpan;
  /* x/w: Sprite in VRAM-X; src_x0: VRAM-X der Quelle zu x; left/width: Zeichenbereich; margin: Bandbreite.
   * Schreibt 0..2 Spans (links zuerst), gibt Anzahl zurück. */
  static inline int ws_feedback_rect_spans(int32_t x, int32_t w, int32_t src_x0,
                                           int32_t left, int32_t width, int32_t margin,
                                           WsFeedbackSpan out[2]);
  ```

- [ ] **Step 1: Failing Tests schreiben** (ein Assert pro Test, Stil wie `test_ws_repeat_rect.c`), Werte: `left 320, width 320, margin 54`.
  - `left_edge_sprite_gets_left_band`: `x 320, w 256, src 0` → 1 Span `{266, -54, 54}`.
  - `right_edge_sprite_gets_right_band`: `x 576, w 64, src 256` → 1 Span `{640, 320, 54}`.
  - `full_width_sprite_gets_both_bands`: `x 320, w 320, src 0` → 2 Spans, `out[1] == {640, 320, 54}`.
  - `inner_sprite_gets_no_band`: `x 400, w 64, src 80` → 0.
  - `zero_margin_gets_no_band`: `x 320, w 320, src 0, margin 0` → 0.
  - `negative_width_rejected`: `w 0` → 0.
- [ ] **Step 2:** `cc -std=c11 -Ipsxrecomp/runtime/include psxrecomp/runtime/tests/test_ws_feedback_rect.c -o build-tests/test_ws_feedback_rect && build-tests/test_ws_feedback_rect` → Compile-Fehler (Header fehlt).
- [ ] **Step 3:** `ws_feedback_rect_spans` implementieren. Linkes Band nur bei `x <= left`, rechtes nur bei `x + w >= left + width`. `src_x` folgt linear: `src_x0 + (dst_x - x)`.
- [ ] **Step 4:** Test-Kommando aus Step 2 → alle Tests grün. `add_executable(ws_feedback_rect_test ...)` + `add_test` in `runtime/CMakeLists.txt` eintragen.
- [ ] **Step 5:** Im Kula-`Taskfile.yaml` (`test`-Task) den Fork-Test wie `widescreen_logic` mitbauen und ausführen.

### Task 2: Tag-API und Auslösen in `gpu.c`

**Files:**
- Modify: `psxrecomp/runtime/include/gpu.h` (neben `gpu_ws_tag_repeat_rect`)
- Modify: `psxrecomp/runtime/src/gpu.c` (`gpu_ws_tag_repeat_rect`, `ws_repeat_textured_rect_reveal`, Aufrufstelle im 0x64-Handler)
- Modify: `psxrecomp/runtime/include/gpu_render.h` (`GpuRenderBackend`, Fassade `gr_*`)
- Modify: `psxrecomp/runtime/include/mod_plugins.h`, `psxrecomp/runtime/src/mod_runtime.cpp`

**Interfaces:**
- Consumes: `ws_feedback_rect_spans` (Task 1).
- Produces:
  - `void gpu_ws_tag_feedback_rect(uint32_t prim);` und `void psx_mod_tag_feedback_rect(uint32_t primitive);`
  - Backend-Member am Ende von `GpuRenderBackend`: `void (*wide_feedback_rect)(int src_base, int src_x, int src_y, int dst_x, int dst_y, int w, int h, int r, int g, int b, int raw, int semi);`
  - Fassade `void gr_wide_feedback_rect(...)` (gleiche Parameter, no-op bei NULL).

- [ ] **Step 1:** Eigene Tag-Tabelle `ws_feedback_rect_tags` mit `WsRepeatRectTag`-Infrastruktur (Periode fest 1, nur als Marker). `gpu_ws_tag_feedback_rect` wie `gpu_ws_tag_repeat_rect`, aber Befehl 0x64–0x67 erlaubt, keine Periode.
- [ ] **Step 2:** `ws_feedback_rect_reveal(x, y, w, h, u, v)` direkt nach `ws_repeat_textured_rect_reveal` aufrufen. Bedingungen: Tag + Guard, `margin > 0`, Zeichenbereich = Display-Breite, `depth == 2`, `ws_is_fb_base` liefert die Basis, deren 1024er-Spalte `tpage_x + u` enthält. Danach je Span `gr_wide_feedback_rect(src_base, span.src_x, tpage_y + v, span.dst_x, y, span.w, h, mod_r, mod_g, mod_b, raw, semi)`. Modulation, `raw` und `semi` aus dem Zustand, den `setup_textured_draw` gesetzt hat.
- [ ] **Step 3:** Mod-Wrapper `psx_mod_tag_feedback_rect` in `mod_runtime.cpp` (wie die übrigen `psx_mod_tag_*`), Deklaration mit Einzeilen-Kommentar in `mod_plugins.h`.
- [ ] **Step 4:** Build (`task build:dev`) kompiliert. Ohne Backend-Implementierung ändert sich nichts: Smoke-Endwert 3603.

### Task 3: Software-Backend

**Files:**
- Modify: `psxrecomp/runtime/src/gpu_sw_renderer.c` (neben den `g_wide_*`-Funktionen, Eintrag im Backend-Struct)

**Interfaces:**
- Consumes: Backend-Signatur aus Task 2.
- Produces: `static void sw_wide_feedback_rect(...)` im SW-Backend.

- [ ] **Step 1:** Implementieren: Quelle = `wide_surface_for(src_base)` (bestehender Lookup, NULL → return), Ziel = `g_wide_cur` (NULL → return). Lokale X wie `wide_dx()`, Skalierung `s` wie beim Spiegeln. Pro Pixel: Texel lesen, 0x0000 überspringen, Modulation (außer `raw`), Mischung mit den vorhandenen Semi-Funktionen, Maskenbit wie beim normalen Spiegeln.
- [ ] **Step 2:** Dev-Build mit `renderer = "software"` (nur lokal in `build-dev/game.toml`, nicht committen), Repro aus Task 5 → Schleier über volle Breite im Debug-Screenshot.

### Task 4: GL-Backend

**Files:**
- Modify: `psxrecomp/runtime/src/gpu_gl_renderer.c` (Shader-Setup neben den übrigen Programmen, Funktion neben `wide_target_begin`, Backend-Struct)

**Interfaces:**
- Consumes: Backend-Signatur aus Task 2.
- Produces: `static void glb_wide_feedback_rect(...)` im GL-Backend.

- [ ] **Step 1:** Kleines Programm `s_fb_prog`: Vertex-Shader mit Ziel-Rechteck in breiten lokalen Koordinaten, Fragment-Shader liest `s_wide_tex[src]` mit normierten Koordinaten (Quelle in lokalen Koordinaten / (`g_wide_w`, `VRAM_H`)), `discard` bei Farbe = 0, Modulation `tex * col / 128` (außer `raw`).
- [ ] **Step 2:** `glb_wide_feedback_rect`: Quellfläche per Basis suchen (fehlt → return), `g_wide_cur` = 0 → return, vorher `hiw_flush_queue()`, Ziel-FBO binden wie `wide_target_begin`, Blend: Modus 0 `GL_FUNC_ADD` mit konstantem 0,5/0,5, 1 `ADD ONE/ONE`, 2 `GL_FUNC_REVERSE_SUBTRACT ONE/ONE`, 3 `ADD` mit Quelle × 0,25 (im Shader vorskaliert), opak ohne Blend. Danach Zustand wiederherstellen wie `wide_target_end`.
- [ ] **Step 3:** Repro aus Task 5 mit `renderer = "opengl"` → Schleier über volle Breite.

### Task 5: Kula-Mod, Prüfung, Doku

**Files:**
- Modify: `mods/src/kula_widescreen.c`, `game.toml`, `CLAUDE.md`

**Interfaces:**
- Consumes: `psx_mod_tag_feedback_rect` (Task 2).

- [ ] **Step 1:** Hook `FN_DRAW_LETHARGY = 0x00020b30u` (Original via `psx_mod_call_guest`, danach taggen, Muster wie `on_process_particles`). Tag für `VAR_LETHARGY_SPRITES = 0x800a3ee4u + (env * 2 + i) * TSPRITE_SIZE + SPRT_TAG_OFFSET`, `i` 0..1, nur wenn `VAR_LETHARGY_MODE = 0x800a52b8u` ≠ 0. `"0x00020b30"` in `mod_function_entry_funcs`, dann `task generate` + `task build:dev`.
- [ ] **Step 2:** Repro unter Xvfb: Levelauswahl W1/L10, Eingaben `L U U R U U U R U U` (je 4 Frames), Screenshot, START, Screenshot. Erwartet bei 16:9 (428 px) und 2:1 (480 px): keine senkrechten Kanten an 54/374 bzw. 80/400, Schleier über volle Breite. Vorher/Nachher vergleichen.
- [ ] **Step 3:** Regression: `task test`, Smoke (3603), `check_level_select.py` 1/1 und 3/5, Score-Tabelle und Ladebildschirm ohne Müll.
- [ ] **Step 4:** `CLAUDE.md` Widescreen-Abschnitt: Pillen-Effekt, Tag-API, Fork-Branch, Repro.
- [ ] **Step 5:** Nach Rückfrage beim Nutzer: Fork-Branch und Kula-Branch committen, pushen, `.gitmodules`/Submodul-Pin anpassen, Mac-Test schicken.
