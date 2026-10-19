# Widescreen: Framebuffer-Feedback in den Bändern (Pillen-Effekt)

Stand 2026-10-19, abgenommen im Chat.

## Absicht

Die Pille in Kula World (z. B. W1/L10) schaltet einen Nachzieh-Effekt ein: Jeden Frame legt das Spiel das
vorherige Bild aus dem anderen Framebuffer halbtransparent über das neue (`DrawLethargyEffects`,
`lethargyEffectSprite[2][2]`). Im Breitbild-Modus deckt das nur die 320 px der Mitte ab, weil im
PS1-VRAM nur diese Spalten existieren und Texturen im Framework immer aus dem kanonischen VRAM lesen.
An der 4:3-Grenze entstehen harte Kanten, im Pausenmenü sieht man einen hellen Schleier nur in der Mitte.

Ziel: Der Effekt läuft über die volle Breite, die Bänder bekommen dasselbe Nachziehen wie die Mitte.

## Ziele

- Ein Spiel kann ein Sprite als „1:1-Kopie aus einem Framebuffer“ markieren.
- Im Breitbild zeichnet das Framework für ein markiertes Sprite, das den Bildrand berührt, zusätzliche
  Band-Rechtecke. Sie lesen aus der breiten Fläche des Quell-Puffers (vorheriges Bild inklusive Bänder).
- GL- und Software-Renderer unterstützen das.
- Kula markiert die beiden Effekt-Sprites, der Pillen-Effekt geht über die volle Breite.

## Nicht-Ziele

- Keine automatische Erkennung von Feedback-Sprites. Die Klassifikation macht der Titel per Tag, wie bei
  `gpu_ws_tag_repeat_rect`.
- Kein Vulkan-Backend (experimentell). Ohne Backend-Operation bleibt alles wie heute.
- Keine Änderung am kanonischen VRAM oder an 4:3. Bei 4:3 und bei nicht markierten Paketen ist das
  Verhalten bitgleich zu heute.
- Keine Polygone (nur Sprite-Befehle 0x64–0x67).

## Anti-Ziele

- Ein Fix, der die Mitte verändert oder bei 4:3 wirkt.
- Heuristiken, die andere Spiele unbemerkt treffen.

## Entscheidungen

1. **Tag-API im Framework** (`gpu.h`): `void gpu_ws_tag_feedback_rect(uint32_t prim);`
   - `prim` ist die P_TAG-Adresse des Sprite-Pakets, die Befehlswörter liegen ab `prim + 4`
     (Konvention wie `gpu_ws_tag_repeat_rect`).
   - Akzeptiert nur 0x64–0x67 (Sprite mit variabler Größe, opak oder halbtransparent, mit oder ohne
     Rohtextur). Packet-Guard wie bei `repeat_rect` (`ws_prepass_packet_guard`), Tag gilt für den
     laufenden Frame.
   - Inert, solange native-wide nicht konfiguriert ist.
   - Mod-Wrapper in `mod_plugins.h`/`mod_runtime.cpp`: `void psx_mod_tag_feedback_rect(uint32_t primitive);`
2. **Ausführung in `gpu.c`**: Nach dem normalen Zeichnen eines Sprites (dort, wo
   `ws_repeat_textured_rect_reveal` aufgerufen wird) prüft `ws_feedback_rect_reveal`:
   - Tag vorhanden und Wächter passt.
   - Aktuelle Texturseite ist 15-bit direkt (`depth == 2`).
   - Die Quelle `tpage_x + u` liegt in einem bekannten Framebuffer (`ws_is_fb_base`, Basis `src_base`).
   - Das Ziel ist die aktuelle breite Zielfläche (Zeichenbereich = Display-Breite, wie bei `repeat_rect`).
   - Berührt das Sprite den linken Rand des Zeichenbereichs, entsteht ein linkes Band-Rechteck von
     `left - margin` bis `left`. Berührt es den rechten Rand, ein rechtes von `right` bis `right + margin`.
     Höhe und Y wie das Sprite.
   - Quell-X des Band-Rechtecks folgt linear: `src_x = (tpage_x + u) + (band_x - x)`. Das kann außerhalb
     der 320 Spalten des Quell-Puffers liegen. Genau dort liegen dessen Bänder in seiner breiten Fläche.
   - Aufruf der neuen Backend-Operation mit Modulationsfarbe, Rohtextur-Flag und Semi-Modus des Sprites.
   - Die Span-Berechnung ist reine Logik in einem Header (`ws_feedback_rect.h`, analog
     `ws_repeat_rect.h`) mit C-Test.
3. **Neue Backend-Operation** (`GpuRenderBackend`, optional, NULL = nicht unterstützt):
   `void (*wide_feedback_rect)(int src_base, int src_x, int src_y, int dst_x, int dst_y, int w, int h, int r, int g, int b, int raw, int semi);`
   - Koordinaten sind VRAM-Koordinaten, X darf außerhalb des 1024er-VRAM liegen (Band).
   - Ziel ist nur die aktuelle breite Fläche (`g_wide_cur`), nie das kanonische VRAM.
   - Quelle ist die breite Fläche mit Basis `src_base`. Fehlt sie, passiert nichts.
   - Lokale X-Umrechnung für Quelle und Ziel wie beim Spiegeln: `local = vram_x - base + g_wide_off + view_shift`.
   - Pixelrechnung wie PS1-Sprite mit 15-bit-Textur: Texel × Farbe / 128 (bei `raw` ohne Modulation),
     dann Semi-Modus 0–3 (0: B/2 + F/2, 1: B + F, 2: B − F, 3: B + F/4) oder opak (`semi = -1`).
     Texel 0x0000 ist transparent.
   - **Software** (`gpu_sw_renderer.c`): direkt auf den 16-bit-Flächen mit den vorhandenen
     Misch-Funktionen, exakt. Maskenbit wie beim normalen Spiegeln.
   - **GL** (`gpu_gl_renderer.c`): eigener kleiner Shader, liest die Quellfläche (`s_wide_tex[src]`,
     normierte Koordinaten, unabhängig von `s_wide_as`), Modulation im Shader, Mischung per
     `glBlendEquation`/`glBlendFunc`. Vor dem Lesen die Mirror-Warteschlange leeren (`hiw_flush_queue`),
     weil die Quelle eine breite Fläche ist. Transparenz von 0x0000 über „Farbe = 0“ nachgebildet,
     bekannte Abweichung bei Modus 0 (für Kula ohne Wirkung, Modus 1).
4. **Kula-Mod** (`mods/src/kula_widescreen.c`): Hook nach `DrawLethargyEffects` (0x20B30, Aufruf des
   Originals, danach taggen). Getaggt werden `lethargyEffectSprite[env][0]` und `[env][1]`
   (0x800A3EE4, TSprite 28 Byte, SPRT-Tag bei +8), solange `lethargyMode` (0x800A52B8) ≠ 0.
   Neuer Eintrag in `game.toml mod_function_entry_funcs`.

## Prüfung

- C-Test für die Span-Logik (`ws_feedback_rect.h`): linker Rand, rechter Rand, beide, keiner, Quell-X-Fortsetzung,
  Rand 0.
- Repro (Nutzer): W1/L10 per Levelauswahl, links drehen, 2× vor, rechts drehen, 3× vor, rechts drehen, 2× vor →
  Pille. START friert den Effekt im Pausenmenü ein.
- Erwartet bei 16:9 und 2:1: Schleier und Nachziehen über die volle Breite, keine senkrechten Kanten bei
  x = 54/374 bzw. 80/400 (Debug-Screenshot enthält die Bänder).
- Software-Renderer (`renderer = "software"`) zeigt dasselbe Bild.
- Regression: `task test`, Smoke (Timer-Endwert 3603), Levelauswahl 1/1 und 3/5, `present_native_43` = 0 im Level.
- Mac: echte GPU und Sichtprüfung durch den Nutzer.

## Dem Umsetzer überlassen

- Genaue Shader-Gestaltung im GL-Pfad und ob die Band-Rechtecke in die Mirror-Warteschlange gehen oder sofort
  gezeichnet werden (Reihenfolge muss mit dem übrigen Spiegeln stimmen).
- Ob `gpu.c` den Rand per Zeichenbereich oder per Display-Basis bestimmt, solange es zu `repeat_rect` passt.

## Eigene Festlegungen (vom Nutzer nicht einzeln abgestimmt)

- Tag-basiert statt automatischer Erkennung.
- Nur Sprites, nur GL und Software.
- Umsetzung im psxrecomp-Fork (Branch auf `feat/ws-screen-x-sltu-band`), Upstream-PR entscheidet der Nutzer später.
