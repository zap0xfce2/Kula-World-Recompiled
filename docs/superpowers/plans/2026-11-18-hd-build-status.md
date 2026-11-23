# HD-Bau-Status in der Mod-Zeile Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Die Statuszeile des Mods „HD Textures“ im Launcher zeigt den Stand des HD-Packs aus `hd-auto/status.txt`.

**Architecture:** psxrecomp liest für Features mit `status_file` die erste Zeile dieser Datei (relativ zum Exe-Ordner) und setzt sie als `RecompLauncherCModFeature.status`, wenn das Feature an ist und kein Prüffehler vorliegt. Kula schreibt die Zeile: der Runner bei jedem Fortschritt, das Plugin beim Start (aktuell oder eigener Fehler).

**Tech Stack:** C++17 (psxrecomp runtime, toml11), Python 3.9+ Standardbibliothek (Runner), C11 (Plugin), unittest/C-Tests über `task test`.

**Spec:** `docs/superpowers/specs/2026-11-18-hd-build-status-design.md`

## Global Constraints

- Datei `hd-auto/status.txt` neben der Exe, UTF-8, eine Zeile, höchstens 255 Byte; fehlt sie: kein Status.
- `status_file` ist relativ, ohne `..` und ohne absoluten Pfad; sonst Manifest-Fehler.
- Prüffehler (`has_error`) haben Vorrang; der Status setzt nie `has_error`.
- Texte exakt (Prozent ganzzahlig, abgerundet):
  - `HD pack: {p} % built, continues while you play`
  - `HD pack: {p} % built, continues when you play`
  - `HD pack ready ({kind}), active from the next start`
  - `HD pack ready (Lanczos, AI model failed: {error}), active from the next start`
  - `HD pack active ({kind})`
  - `HD pack build failed ({error}), retries on the next start`
  - `HD pack not built: {reason}`
  - `{kind}` = `AI model` (Marker `m60`) oder `Lanczos` (`lanczos`).
- Plugin-Gründe: `extract_failed` → `could not read the disc`, `no_platform` → `no portable Python for this platform`, `download_failed` → `Python download failed`, `checksum_failed` → `Python download is damaged`, `unpack_failed` → `Python could not be unpacked`, `runner_failed` → `the build could not start`.
- psxrecomp-Änderung auf dem Fork-Branch `feat/launcher-theme` (Pin von `main`), Upstream-PR nur mit Freigabe.

## Review Focus

- Feature aus, Datei sagt „active“: Status darf nicht erscheinen → Test `status_hidden_when_feature_disabled` (Task 1, im Provider-Test oder als Bedingung in `feature_status_text`).
- Datei mit CRLF oder ohne Zeilenende: Zeile ohne `\r` → Test `status_strips_crlf`.
- Datei länger als 255 Byte: auf 255 Byte gekürzt, ohne halbe UTF-8-Zeichen → Test `status_truncates_on_utf8_boundary`.
- Fremdes Manifest mit `status_file = "../../etc/passwd"`: abgelehnt → Test `status_file_rejects_parent_paths`.
- Runner wird während eines neuen Baus beendet: Status zeigt `continues when you play`, nicht `ready` → Test `status_line_stopped` (Task 2).

---

### Task 1: psxrecomp `status_file`

**Files:**
- Modify: `psxrecomp/runtime/include/mod_packages.h` (Feld `std::string status_file;` neben `vsync_off`), `psxrecomp/runtime/src/mod_packages.cpp` (Parser neben `vsync`, um Zeile 1920; `kMaxFormatVersion` 13 → 14; neue Funktion), `psxrecomp/runtime/src/mod_runtime.cpp` (um Zeile 1305, nach der Diagnose-Schleife), `psxrecomp/docs/MOD_PACKAGES.md` (Schlüssel und format_version 14).
- Test: `psxrecomp/runtime/tests/test_mod_packages.cpp`

**Interfaces:**
- Produces:
  - Manifest: `[[feature]] status_file = "<relativ>"`, verlangt `format_version >= 14`.
  - `std::string mod_feature_status_text(const std::filesystem::path& exe_dir, const std::string& status_file);` in `mod_packages.h`/`.cpp`: erste Zeile, `\r` entfernt, auf 255 Byte an UTF-8-Grenze gekürzt, leer bei fehlender Datei.
  - Provider: wenn `feature->status_file` gesetzt, Feature an, kein Prüffehler → `out->status = mod_feature_status_text(manager.root().parent_path(), feature->status_file)`.

- [ ] **Step 1: Failing tests** in `test_mod_packages.cpp` (Stil wie der `vsync`-Test um Zeile 2470, je ein `check`):
  - `status_file_parsed`: Manifest `head("st.mod", 14)` + `status_file = "hd-auto/status.txt"` → `features[0].status_file == "hd-auto/status.txt"`.
  - `status_file_needs_format_14`: gleiches Manifest mit `head(..., 13)` → Scan-Fehler.
  - `status_file_rejects_parent_paths`: `"../x.txt"` und `"/etc/passwd"` → Scan-Fehler.
  - `status_reads_first_line`: Datei `"HD pack active (Lanczos)\nzweite\n"` → `"HD pack active (Lanczos)"`.
  - `status_strips_crlf`: `"abc\r\n"` → `"abc"`.
  - `status_missing_file_is_empty`: → `""`.
  - `status_truncates_on_utf8_boundary`: 254 × `a` + `"ä"` (2 Byte) → Länge 254.
- [ ] **Step 2: Bauen, Tests schlagen fehl**
  Run: `cmake -S psxrecomp/runtime -B /tmp/claude-1000/psx-rt-test -G Ninja && cmake --build /tmp/claude-1000/psx-rt-test --target mod_packages_test`
  Expected: Kompilierfehler (`status_file`, `mod_feature_status_text` fehlen).
- [ ] **Step 3: Implementieren** wie in Interfaces. Pfadprüfung über `std::filesystem::path`: `is_absolute()` oder ein Element `..` → `std::runtime_error("feature status_file must be a relative path inside the game folder")`.
- [ ] **Step 4: Tests grün**
  Run: `/tmp/claude-1000/psx-rt-test/mod_packages_test`
  Expected: Exit 0, keine `FAIL`-Zeile.
- [ ] **Step 5: Commit** im Submodul auf `feat/launcher-theme`: `git commit -m "feat(mods): show a feature status line from a file"`, pushen nach `fork`.

### Task 2: Runner schreibt die Zeile

**Files:**
- Modify: `tools/hd/hd_auto.py` (`Progress`, `build_if_needed`, `main`)
- Test: `tests/test_hd_auto.py`

**Interfaces:**
- Produces:
  - `def status_line(state: str, fraction: float, error: str | None, with_model: bool) -> str` (reine Funktion, Texte aus Global Constraints; `state` ∈ running/stopped/done/failed/active).
  - `Progress(path: Path, status: Path | None = None, with_model: bool = False)`: schreibt nach jedem `set` zusätzlich `status_line(...)` atomar nach `status` (`.tmp` + `replace`, `OSError` ignorieren wie bei `progress.json`).
  - `build_if_needed`: bei aktuellem Pack `prog.set("build", 1.0, state="active")` — `active` wird nur in die Statusdatei übersetzt; in `progress.json` steht `done`.

- [ ] **Step 1: Failing tests** (je ein Assert):
  - `test_status_line_running`: `status_line("running", 0.416, None, True)` == `"HD pack: 41 % built, continues while you play"`.
  - `test_status_line_stopped`: `("stopped", 0.416, None, True)` == `"HD pack: 41 % built, continues when you play"`.
  - `test_status_line_done_model`: `("done", 1.0, None, True)` == `"HD pack ready (AI model), active from the next start"`.
  - `test_status_line_done_model_fallback`: `("done", 1.0, "download", True)` == `"HD pack ready (Lanczos, AI model failed: download), active from the next start"`.
  - `test_status_line_done_lanczos`: `("done", 1.0, None, False)` == `"HD pack ready (Lanczos), active from the next start"`.
  - `test_status_line_failed`: `("failed", 0.2, "disk", False)` == `"HD pack build failed (disk), retries on the next start"`.
  - `test_status_line_active`: `("active", 1.0, None, True)` == `"HD pack active (AI model)"`.
  - `test_progress_writes_status_file`: `Progress(tmp/"progress.json", tmp/"status.txt", True).set("build", 0.5)` → Datei existiert und beginnt mit `"HD pack: "`.
- [ ] **Step 2: Tests schlagen fehl**
  Run: `.venv-hd/bin/python -m unittest tests.test_hd_auto -k status`
  Expected: ImportError `status_line`.
- [ ] **Step 3: Implementieren**; in `main`: `Progress(data / "progress.json", data / "status.txt", args.with_model)`.
- [ ] **Step 4: Tests grün**
  Run: `.venv-hd/bin/python -m unittest tests.test_hd_auto`
  Expected: OK.
- [ ] **Step 5: Commit** `git commit -m "feat(hd): write a one-line build status for the launcher"`

### Task 3: Plugin und Manifest

**Files:**
- Modify: `mods/src/hd_textures_logic.{h,c}` (neue reine Funktion), `mods/src/kula_hd_textures.c` (Schreiben bei `up_to_date` und bei jedem eigenen Fehler-Counter), `mods/preloaded/packages/kula.hd-textures/1.0.0/manifest.toml` (`format_version = 14`, `status_file = "hd-auto/status.txt"` im `[[feature]]`)
- Test: `tests/test_hd_textures_logic.c`

**Interfaces:**
- Consumes: `status_file` aus Task 1, Texte wie Task 2 (`HD pack active (...)`).
- Produces: `int hd_status_text(char* out, size_t out_size, const char* counter, int with_model);` → schreibt den Text für Counter-Namen ohne Präfix (`up_to_date`, `extract_failed`, …), Rückgabe 0 bei unbekanntem Counter.

- [ ] **Step 1: Failing tests** (je ein Assert): `up_to_date` mit Modell → `"HD pack active (AI model)"`; `up_to_date` ohne → `"HD pack active (Lanczos)"`; `no_platform` → `"HD pack not built: no portable Python for this platform"`; `runner_started` → Rückgabe 0.
- [ ] **Step 2: Fehlschlag prüfen**
  Run: `task test PYTHON=.venv-hd/bin/python`
  Expected: Kompilierfehler `hd_status_text`.
- [ ] **Step 3: Implementieren**; im Plugin eine Hilfsfunktion, die den Text nach `<basepath>/hd-auto/status.txt` schreibt (Ordner anlegen, Fehler ignorieren), an jeder Stelle, die einen der Counter aus Global Constraints setzt. Bei Fehlern im Worker-Thread schreibt der Thread selbst (Datei-I/O ist thread-sicher, nur die Counter nicht).
- [ ] **Step 4: Grün**
  Run: `task test PYTHON=.venv-hd/bin/python`
  Expected: alle Tests ok.
- [ ] **Step 5: Commit** inkl. Submodul-Pin und `CLAUDE.md` (HD-Teil 3: Statuszeile): `git commit -m "feat(hd): show the HD pack status in the launcher mod row"`

### Task 4: Prüfung und Abschluss

- [ ] **Step 1: Build** `cmake --build build-dev`, Expected: ok, Manifest im Build mit `status_file`.
- [ ] **Step 2: Linux-Prüfung über die Mods-Seite** (Xvfb, X11-Capture, HD-Mod an per `build-dev/mods/state.toml`):
  - `hd-auto/status.txt` von Hand mit `HD pack: 41 % built, continues when you play` → Zeile unter „HD Textures“ sichtbar.
  - Mod aus → keine Zeile.
  - Datei entfernt → keine Zeile.
  - Echter Lauf unter musl: Plugin schreibt `HD pack not built: no portable Python for this platform`.
- [ ] **Step 3: Smoke** `demo_gameplay_reached`, 0 Misses.
- [ ] **Step 4: Push** Branch `feat/hd-build-status`. Mac-Prüfung (echter Bau mit Fortschritt, fertig, aktiv) erst nach Rückfrage beim Nutzer.
