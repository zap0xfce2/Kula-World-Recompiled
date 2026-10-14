# Kula World (SCES-01000) – Voranalyse

## Disc
- Raw-Image MODE2/2352, 1 Datentrack, 255.123.792 Bytes
- MD5 `0f675dc230354f8c3b835bf34841bd20`, SHA1 `0bf9fb06b73a9b5353cdcc371e188934369068da` (gegen Redump prüfen)
- Boot: `SCES_010.00` (604 KB), `3.00` = 31 MB Null-Padding
- Pro Welt: `<WELT>.PAK` (Level, zlib), `<WELT>FI.PAK`, `<WELT>.TGI` (Theme-Grafik)
- `HIRO/`: zusätzlich `HIRO.GGI` (globale Grafik), `HIRO.SFX`, `COPYCAT.PAK`, `WARNING.TIM`
- `XA/`: `MUSIC_0..3.XA` (Form-2-Audio), `FINAL.STR` (Ending-FMV, MDEC)

## EXE
| Feld | Wert |
|---|---|
| Load / Text | `0x00011000`, `0x93000` Bytes (**KUSEG-gelinkt**, kein `0x8001xxxx`) |
| Entry | `0x00069F60` |
| GP | 0 (kein `$gp`-relatives Addressing) |
| Code | `0x00012344`–`0x00072AC0` (Rest: Daten/Strings) |
| Funktionen | 727 JAL-Ziele, ~814 mit Prolog-Heuristik |
| Indirekt | 202 `jalr`, 99 `jr reg` (Funktionszeiger, Jump-Tables) |
| PsyQ | libgpu `sys.c` 1998-01-12, libcd `bios.c` 1997-03-28 (~PsyQ 4.x) |
| Extern | zlib `inflate 1.0.4`, eigene Engine ("jens 2d-eng") |

## Overlays
**Keine.** Kein `Load`/`Exec`/`LoadExec`, alle `FlushCache`-Aufrufer sind PsyQ-Kernel-Patches,
kein MIPS-Code in TGI/GGI/SFX/PAK (auch entpackt). Rein statischer Recomp möglich.

## Ankerpunkte (PAL)
- Level-Timer-Init `0x000367D4`: Typ 666 → `startingTime * 50`, sonst 4950 (`0x1356`)
- `currentTime` = `0x000A52C8` (Roll Away: Code `0x35F5C`, Var `0xA573C`)

## Bekannte psxrecomp-Stolpersteine (aus chrisking1981/psxrecomp_kula_world)
1. crt0 legt `$sp` in den 4. RAM-Mirror (`0x807FFFF8`) – gefixt (memory.c)
2. GetID-Region hart auf SCEI – gefixt (PAL → SCEE)
3. CD-Controller-Version muss SCPH-1001-Wert `0x94 09 19 C0` liefern – gefixt
4. libcd CD-IRQ wurde nicht bedient → GetStat/Init-Endlosschleife – später gelöst,
   Branch `kula-world-linux-macos` erreicht spielbare 3D-Level
5. Upstream behält KUSEG inzwischen bei (kein Falten auf KSEG0) – mit Kula **noch nicht getestet**
   (psxrecomp `docs/SEGMENT_AWARE_CODE.md` §7)
