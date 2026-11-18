# Launcher-Farben pro Spiel (Kula World) – Design

Stand 2026-11-18. Roadmap-Punkt „Launcher colors per game (recomp-ui extension)“.

## Absicht
Der Launcher soll nach Kula aussehen: Sandstein und Himmel statt PlayStation-Blau.
Der Nutzer hat im Browser-Entwurf (`mockups/launcher-colors.html`, Branch `spike/launcher-colors-mockup`) Variante **B · Himmel** gewählt.
Nice to have, keine Abhängigkeit der Release-Strecke.

## Ziele
- Launcher und das Menü im Spiel (recomp-ui Runtime-UI) zeigen die Kula-Palette.
- Allgemeiner Mechanismus in recomp-ui: Ein Spiel überschreibt einzelne Farben seines Konsolen-Schemas. Nicht gesetzte Farben bleiben wie im Schema.
- Upstream-fähig nach dem Muster von recomp-ui#114 (Logo).

## Nicht-Ziele
- Kein neues Layout, keine neuen Schriften, keine Hintergrundgrafik, keine Scanlines.
- Keine Änderung an Abständen, Radien oder Schriftgrößen (`LauncherTheme`-Maße).
- Kein spielspezifisches Schema „kula“ in `launcher_theme.h`.

## Anti-Ziele
- Schlechtere Lesbarkeit als heute (Text auf Flächen, PLAY-Beschriftung, Fokusrahmen).
- Ein Fork, der dauerhaft von Upstream abweicht.

## Ansätze
1. **Farbdatei wie beim Logo (gewählt).** Option `THEME <pfad>` in `recomp_ui_add`, Ablage als `assets/theme_game.ini`, der Launcher legt die Werte über das Konsolen-Schema. psxrecomp reicht `LAUNCHER_THEME` durch wie `LAUNCHER_BRAND`.
2. Farben beim Bauen eincompilieren (CMake-Liste → Defines). Gleicher Effekt, aber recomp-ui pro Spiel neu kompiliert und für Upstream unschöner.
3. Eigenes Schema „kula“ nur im Fork. Am kleinsten, aber nicht upstream-fähig. Verworfen.

## Entscheidungen des Nutzers
- Variante B, Ansatz 1.

## Vorschläge von mir (korrigierbar)
- Das Menü im Spiel bekommt dieselben Farben.
- Dateiformat: INI, Abschnitt `[colors]`, eine Zeile je Token, Wert `#RRGGBB` oder `#RRGGBBAA`. Schlüssel heißen wie die Felder von `LauncherTheme` (`background`, `background2`, `panel`, `panel_hovered`, `control`, `control_hovered`, `border`, `accent`, `accent_dim`, `accent_text`, `accent2`, `text`, `text_muted`, `good`, `warn`, `focus_ring`). Unbekannte Schlüssel und kaputte Werte werden ignoriert (eine Zeile auf stderr), der Launcher startet immer.
- Kula-Werte aus dem Entwurf B:

| Token | Wert |
|---|---|
| background | `#081429` |
| background2 | `#123A73` |
| panel | `#0F2547` |
| panel_hovered | `#17345F` |
| control | `#143058` |
| control_hovered | `#1C3E6E` |
| border | `#25497D` |
| accent | `#ECC57D` |
| accent_dim | `#C8913F` |
| accent_text | `#1A120A` |
| accent2 | `#BFE6FF` |
| text | `#EEF6FF` |
| text_muted | `#9FB8D8` |
| good | `#7FE0A6` |
| focus_ring | `#F6C21B` |

  `warn` bleibt wie im PSX-Schema.
- Datei im Repo: `assets/launcher/theme.ini`, eingebunden über `LAUNCHER_THEME` in `psxrecomp_add_game_runtime` (wie `LAUNCHER_BRAND`).

## Wie es heute funktioniert
- `launcher_ng_capi.c`: `launcher_theme_by_name(game->theme)` baut das Schema, danach `launcher_backend_set_assets_directory(assets_dir)` und `launcher_backend_run(..., &theme)`.
- Runtime-UI (`recomp_runtime_ui.c`, `runtime_ui_imgui.cpp`): `launcher_theme_by_name(ui->config.theme)` an mehreren Stellen.
- Logo: `recomp_ui.cmake` kopiert `BRAND` per POST_BUILD nach `assets/img/brand_game.tga`; `launcher_imgui.cpp` lädt es über `asset()` vor dem Profil-Logo.
- INI-Hilfen gibt es schon (`launcher_ini.h`/`.inc`).
- `asset()` löst Pfade relativ zum Assets-Ordner auf; seit recomp-ui#171 auch, wenn der Host den Exe-Ordner übergibt.

## Was der Builder entscheidet
- Wo genau überlagert wird: eine Funktion `launcher_theme_apply_game_overrides(LauncherTheme*, const char* path)` neben `launcher_theme_by_name`, aufgerufen an allen Stellen, die das Schema bauen (Launcher und Runtime-UI). Wie die Runtime-UI an den Pfad kommt (Assets-Ordner im Config oder Exe-Ordner), klärt der Builder im Code.
- Ob `accent_dim` für den PLAY-Verlauf reicht oder ein weiterer Token nötig ist (Entwurf: reicht).
- Tests: C-Test für das Einlesen (gültig, Teilmenge, kaputter Wert, fehlende Datei), wie die vorhandenen `tests/*_test.c`.

## Ablauf
1. recomp-ui: Option `THEME`, Ablage, Einlesen, Anwendung in Launcher und Runtime-UI, Test, README-Zeile neben `BRAND`. Auf dem Fork-Branch über `b54c7eb` (enthält #171).
2. psxrecomp: `LAUNCHER_THEME` in `psxrecomp_add_game_runtime` durchreichen. Fork-Branch.
3. Kula: `assets/launcher/theme.ini`, `LAUNCHER_THEME` in `CMakeLists.txt`, Submodule auf die Fork-Branches.
4. Linux: Build, Datei liegt im Build-Ordner, Launcher startet (Farben unter Xvfb nicht beurteilbar, Rot/Blau vertauscht), Test grün. Mac: Sichtprüfung Launcher und Menü im Spiel durch den Nutzer.
5. Upstream-PRs für recomp-ui und psxrecomp nur nach Freigabe des Nutzers.

## Risiken
- Upstream nimmt die Option nicht oder anders an: Dann bleibt der Fork, bis es eine Upstream-Lösung gibt.
- Fokusrahmen in Gelb (`#F6C21B`) auf Sandstein-Akzent: im Entwurf gut lesbar, im echten Launcher am Mac prüfen.
