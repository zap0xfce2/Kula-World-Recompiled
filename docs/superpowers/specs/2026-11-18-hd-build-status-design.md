# HD-Bau-Status in der Mod-Zeile – Design

Stand 2026-11-18. Roadmap-Punkt „HD textures: build progress in the launcher“.

## Absicht
Der Spieler sieht auf der Mods-Seite des Launchers unter „HD Textures“, wie weit das HD-Pack ist: im Bau, gestoppt, fertig, aktiv oder fehlgeschlagen. Eine eigene Fortschrittsanzeige im Launcher ist laut Nutzer unsinnig, weil dort nichts gebaut wird; die vorhandene Statuszeile des Mods reicht.

## Ziele
- Eine kurze Zeile in der Mod-Statuszeile (recomp-ui zeigt `RecompLauncherCModFeature.status` schon gedämpft an, bei `has_error` in Warnfarbe, plus Tooltip).
- Allgemeiner Mechanismus in psxrecomp: Ein Feature kann eine Statusdatei nennen, deren erste Zeile als Status erscheint. Upstream-fähig.

## Nicht-Ziele
- Keine Live-Anzeige im Spiel, kein Fortschrittsbalken, keine Änderung an recomp-ui.
- Keine Änderung am Bau selbst.

## Anti-Ziele
- Ein Status, der lügt (z. B. „ready“, obwohl ein neuer Bau läuft).
- Prüffehler des Mods werden von der Statusdatei verdeckt.

## Ansätze
1. **`status_file` pro Feature (gewählt).** Manifest-Schlüssel im `[[feature]]`, Pfad relativ zum Exe-Ordner. psxrecomp liest die erste Zeile beim Befüllen der Feature-Daten für den Launcher, nur wenn kein Prüffehler vorliegt.
2. psxrecomp liest `hd-auto/progress.json` direkt. Nur für Kula, nicht upstream-fähig.
3. Einblendung im Spiel. Kein Mod-API dafür, deutlich mehr Arbeit.

## Entscheidungen des Nutzers
- Status in der Mod-Zeile statt eigener Launcher-Anzeige, Ansatz 1.

## Vorschläge von mir (korrigierbar)
- Datei `hd-auto/status.txt` neben der Exe, UTF-8, eine Zeile, höchstens 255 Byte (Feldgröße 256). Fehlt die Datei: kein Status (wie heute).
- Wer schreibt:
  - Der Runner (`tools/hd/hd_auto.py`) bei jeder Änderung von `progress.json`, atomar (temporäre Datei + `os.replace`).
  - Das Plugin (`mods/src/kula_hd_textures.c`), wenn es beim ersten VBlank ein aktuelles Pack erkennt (`up_to_date`), und bei seinen eigenen Fehlern vor dem Runner-Start (`extract_failed`, `no_platform`, `download_failed`, `checksum_failed`, `unpack_failed`, `runner_failed`).
- Texte (englisch wie der Launcher):

| Lage | Text |
|---|---|
| Bau läuft | `HD pack: 41 % built, continues while you play` |
| Bau gestoppt (Spiel beendet) | `HD pack: 41 % built, continues when you play` |
| Bau fertig | `HD pack ready (AI model), active from the next start` bzw. `(Lanczos)` |
| Fertig, Modell aufgegeben | `HD pack ready (Lanczos, AI model failed: download), active from the next start` |
| Pack aktuell beim Start | `HD pack active (AI model)` bzw. `(Lanczos)` |
| Fehler Runner | `HD pack build failed (<error>), retries on the next start` |
| Fehler Plugin | `HD pack not built: <grund>` (z. B. `no portable Python for this platform`) |

  Upscaler aus `hd-pack.json` (`m60` → „AI model“, `lanczos` → „Lanczos“). Prozent ganzzahlig aus `fraction`.
- Der Status ist reine Information, `has_error` bleibt den Prüffehlern vorbehalten.
- Kula-Manifest `kula.hd-textures`: `status_file = "hd-auto/status.txt"` im `[[feature]]`.

## Wie es heute funktioniert
- psxrecomp `runtime/src/mod_runtime.cpp` um Zeile 1305: `out->status` nur aus `state().validation.diagnostics`, sonst leer.
- Manifest-Felder pro Feature: `runtime/include/mod_packages.h` (`struct` mit `vsync_off`), Parser `runtime/src/mod_packages.cpp` um Zeile 1926.
- Runner schreibt `hd-auto/progress.json` (`{"phase","fraction","eta","state","error","updated"}`), `state` ∈ running/done/failed/stopped.
- Plugin vergleicht `hd-pack.json` beim ersten VBlank und meldet nur Counter.
- Gotcha (bekannt): Bis der neue Runner schreibt, steht in `progress.json` noch das `done` des letzten Baus. Der Status ist davon nicht betroffen, weil das Plugin beim Start entweder `active` schreibt oder den Runner startet, der sofort `running` schreibt.

## Was der Builder entscheidet
- Ob ein neuer Manifest-Schlüssel ein höheres `format_version` braucht (Parser-Regeln in psxrecomp).
- Wie oft psxrecomp die Datei liest (bei jedem Befüllen ist vermutlich billig genug; sonst nach mtime cachen).
- Tests: psxrecomp-Test für Parser und Status-Füllung (Datei da, fehlt, Prüffehler hat Vorrang, zu lang), Python-Test für die Texte im Runner, C-Test für die Plugin-Texte über die vorhandene Logik-Datei `hd_textures_logic.c`.

## Ablauf
1. psxrecomp-Fork (Branch auf aktuellem `feat/launcher-theme`, damit `main` beides pinnt): Schlüssel, Lesen, Test, Doku in `docs/MOD_PACKAGES.md`.
2. Kula: Manifest, Runner, Plugin, Tests, `CLAUDE.md`.
3. Linux: Status in allen Lagen über die Launcher-Mods-Seite (X11-Capture) bzw. den Provider prüfen. Mac-Sichtprüfung nur nach Rückmeldung an den Nutzer.
4. Upstream-PR für psxrecomp nur nach Freigabe.
