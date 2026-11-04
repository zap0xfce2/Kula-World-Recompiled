# HD texture offline build (part 1: disc to Lanczos pack) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A command-line tool builds a complete DuckStation-format HD pack for Kula World from the player's disc. It uses Lanczos only (the spec's fallback pack) and checks the result against runtime dumps.

**Architecture:** A Python package in `tools/hd/` with these steps:
- read the disc (TGI skybox, tileset, bonus TIM; GGI sprites)
- rebuild the exact runtime file names (`texupload-…`, full palette range)
- decode the textures like the runtime dumper
- classify them as sky, UI or other
- upscale each class 4x with its own edge handling
- install the pack atomically

The upscaler is a plain callable, so part 2 (model download plus the M60/H-M mix) plugs in without changing the steps.

**Tech Stack:** Python 3.10+, Pillow, xxhash (dev venv `.venv-hd`), `unittest`, ruff, black, go-task.

**Spec:** `docs/superpowers/specs/2026-11-02-hd-texture-offline-build-design.md`

**Scope split (my call):** The spec covers three independent parts, each with its own plan.
- **Part 1 (this plan):** disc to verified Lanczos pack.
- **Part 2:** portable Python, torch, model download with SHA-256, the M60/M60R/H-M mix, background runner with `progress.json`.
- **Part 3:** launcher opt-in, licence dialog, progress, recomp-ui PR.

Part 1 alone already yields the spec's fallback pack and the acceptance harness the other two need.

## Global Constraints

- **No game data in git:** No disc bytes, extracted files, PNGs, dumps or models in git. The repo may hold code, coordinates, hashes and UV tables only (`CLAUDE.md`, "Rechtliches"). Tests use synthetic data only.
- **Name format,** exactly as `duck_texture_format_name` writes it:
  - `texupload-%s%s-%016llX-%016llX-%ux%u-%u-%u-%ux%u-P%u-%u`
  - The fields are the `ST`-or-empty prefix, mode `P4`/`P8`, source hash, palette hash, source width (words) x height, offset x, offset y, width x height (texels), palette min and palette max.
- **Full palette range only:** `P0-15` for P4, `P0-255` for P8. The palette hash covers all 16 or 256 entries; `palette_hash`, `duckstation_texture_pack.cpp:130` shows the first-N quirk that makes reduced ranges collide.
- **Source hash:**
  - Unseeded XXH3-64 over the upload's 16-bit words, little-endian, row-major (`duck_texture_hash_words_le`).
  - The palette hash is the same over the palette words.
- **Offsets:** Every file covers the whole upload (`-0-0-<full width>x<full height>-`). The runtime clips a part to each draw (`duck_texture_pack_match_parts`).
- **Decode rules** (dumper, `duckstation_texture_pack.cpp:572-583`):
  - Channel: `((c5*255+15)//31)`.
  - Alpha: 0 if the 16-bit colour is 0; 143 if the file is ST and bit 15 is set; else 255.
- **Output:** Every image is exactly 4x the source width and height. Alpha only takes the values 0, 143 and 255.
- **Pack layout:** The pack root is `<build>/mods/texture-packs/SCES-01000/` with `replacements/` and a `config.yaml` containing `ReducePaletteRange: false`. Install is atomic: build into a temp dir next to the target, then swap.
- **Python:** type hints everywhere, no bare `except`, functions of about 30 lines at most, `ruff check` and `black` clean (user rules).
- **Python tools** that read disc data run with `python3 -I`, except the existing `check_level_select.py` and `smoke_boot.py`.

## Review Focus

1. **A texture drawn semi-transparent but shipped only as an ordinary file** loses its STP blending. Expected: the build writes an `ST` variant for every texture whose palette has a non-zero entry with bit 15. The test `test_st_variant_when_palette_has_stp_bit` lives in Task 3.
2. **A sky quad at a CLUT-zone or page boundary** reads neighbour texels. Expected: each quad is filtered from its own crop, and zone gaps are never sampled. The test `test_sky_quad_filter_does_not_read_outside_crop` lives in Task 5.
3. **Thin font strokes** break under the contour rounding. Expected: the radius drops until the region count is unchanged. The test `test_contour_radius_keeps_thin_stroke` lives in Task 6.
4. **An interrupted build** leaves a half-written pack. Expected: the old pack stays until the new one is complete. The test `test_install_keeps_old_pack_when_build_fails` lives in Task 8.
5. **A disc that is not SCES-01000** (other region or revision). Expected: the tool refuses with a clear message instead of producing a pack that never matches. The test `test_rejects_unknown_disc` lives in Task 8; it checks the size of `SCES_010.00` and its SHA-256 `28c8f46d…` from the decomp config.

---

### Task 0: Dev environment and task wiring

**Files:**
- Create: `tools/hd/__init__.py` (empty), `tools/hd/requirements.txt`
- Modify: `Taskfile.yaml` (new tasks `hd:venv`, `hd:build`, `hd:verify`; add `tools/hd` to `lint`), `.gitignore` (`/.venv-hd/`, `/hd-work/`)

- [ ] **Step 1:** Make `hd:venv` create `.venv-hd` with `{{.PYTHON}} -m venv` and install `tools/hd/requirements.txt`. Pin `Pillow` and `xxhash` to the exact versions pip resolves on this machine.
- [ ] **Step 2:** Run `task hd:venv`, then `.venv-hd/bin/python -c "import PIL, xxhash"`. Expected: no output, exit 0.
- [ ] **Step 3:** Run `task test PYTHON=.venv-hd/bin/python` and `task lint`. Expected: both pass as before.
- [ ] **Step 4:** Commit with `chore: add dev venv and tasks for the HD pack builder`.

### Task 1: Names and hashes

**Files:**
- Create: `tools/hd/names.py`
- Test: `tests/test_hd_names.py`

**Interfaces:**
- Produces:
  - `hash_words(words: bytes) -> int`: XXH3-64 over the raw little-endian bytes.
  - `@dataclass(frozen=True) class TextureKey: depth: int  # 4 or 8; semi: bool; source_hash: int; palette_hash: int; width_words: int; height: int`
  - `texel_width(key: TextureKey) -> int`
  - `format_name(key: TextureKey) -> str`: no `.png`, full rect, full range.
  - `parse_name(name: str) -> TextureKey | None`

- [ ] **Step 1: Write the failing tests**

```python
def test_format_name_matches_runtime_format(self):
    key = TextureKey(depth=8, semi=False, source_hash=0x39AD3C3DA790BFE9,
                     palette_hash=0x07918AAE3CF149C6, width_words=384, height=256)
    self.assertEqual(format_name(key),
        "texupload-P8-39AD3C3DA790BFE9-07918AAE3CF149C6-384x256-0-0-768x256-P0-255")

def test_format_name_st_p4(self):
    key = TextureKey(4, True, 1, 2, 8, 32)
    self.assertEqual(format_name(key),
        "texupload-STP4-0000000000000001-0000000000000002-8x32-0-0-32x32-P0-15")

def test_parse_name_round_trip(self):
    key = TextureKey(4, True, 1, 2, 8, 32)
    self.assertEqual(parse_name(format_name(key) + ".png"), key)

def test_parse_name_rejects_reduced_range(self):
    self.assertIsNone(parse_name("texupload-P8-0000000000000001-0000000000000002-4x4-0-0-8x4-P3-255.png"))

def test_hash_words_is_xxh3(self):
    self.assertEqual(hash_words(b""), 0x2D06800538D394C2)
```

- [ ] **Step 2:** Run `.venv-hd/bin/python -m unittest tests.test_hd_names -v`. Expected: FAIL with an `ImportError`.
- [ ] **Step 3:** Implement the interfaces in `tools/hd/names.py` with `xxhash.xxh3_64_intdigest`.
- [ ] **Step 4:** Run the tests again. Expected: PASS.
- [ ] **Step 5:** Commit with `feat(hd): texture names and hashes`.

### Task 2: Disc readers (GGI sprites, TGI skybox, bonus TIM)

**Files:**
- Create: `tools/hd/assets.py` (shared types), `tools/hd/ggi.py`, `tools/hd/tgi.py`
- Test: `tests/test_hd_ggi.py`, `tests/test_hd_tgi.py`

**Interfaces:**
- Produces (`assets.py`):
  - `@dataclass(frozen=True) class Upload: x: int; y: int; width_words: int; height: int; depth: int; words: bytes; kind: str  # "sky" | "sprite" | "tile" | "bonus_sky"`
  - `@dataclass(frozen=True) class Clut: x: int; y: int; colors: bytes  # 16 or 256 LE words`
  - `@dataclass(frozen=True) class Pairing: upload: Upload; clut: Clut`
  - `@dataclass(frozen=True) class SkyQuad: band: int; clut_y: int; atlas_x: int; atlas_y: int; stride: int`. `atlas_x = (page_x - 640) * 2 + texture_x`, and `atlas_y = texture_y` (16 rows).
- Produces (readers):
  - `ggi.read_sprites(data: bytes) -> list[Pairing]`. The sprite sheet starts at decoded `abs[5]` from the header's half-delta chain anchored at `0x34`.
    - Per sprite: `i16 bpp, stp`, then the CLUT block (`vramX, vramY, reuse, pad`, then 256 or 16 entries unless `reuse`; `reuse` means the previous sprite's CLUT), then the texture (`vramX, vramY, width texels, height`, then data), padded to 4 bytes.
    - The 16-bpp sprite is skipped.
  - `tgi.read_sky(data: bytes) -> tuple[Upload, list[Clut], list[SkyQuad]]`. The skybox offset is the sum of the header's section lengths at `+0x164 … +0x184` added to `0x190`.
    - Layout: 1152 quads of 14 bytes, then 24 CLUTs of 520 bytes, then texture X/Y/W/H and 384×256 words.
  - `tgi.read_bonus_sky(data: bytes) -> list[Pairing]`: standard TIM parsing.

- [ ] **Step 1: Write the failing tests.** Build the minimal files in the test from `struct.pack`.

```python
def test_read_sprites_reuses_previous_clut(self):
    pairs = read_sprites(ggi_with_two_p4_sprites(second_reuses=True))
    self.assertIs(pairs[1].clut, pairs[0].clut)

def test_read_sprites_skips_16bpp(self):
    self.assertEqual(len(read_sprites(ggi_with_16bpp_sprite())), 0)

def test_read_sky_atlas_x(self):
    _, _, quads = read_sky(tgi_with_sky(page_x=768, texture_x=5))
    self.assertEqual(quads[0].atlas_x, 261)

def test_read_sky_counts(self):
    upload, cluts, quads = read_sky(tgi_with_sky())
    self.assertEqual((upload.width_words, upload.height, len(cluts), len(quads)), (384, 256, 24, 1152))
```

- [ ] **Step 2:** Run `.venv-hd/bin/python -m unittest tests.test_hd_ggi tests.test_hd_tgi -v`. Expected: FAIL.
- [ ] **Step 3:** Implement the readers as specified.
- [ ] **Step 4:** Run the tests again. Expected: PASS.
- [ ] **Step 5: Real-disc check (local only, nothing committed).**
  - Extract `HIRO/HIRO.GGI` and one `<WORLD>.TGI` with `python3 -I tools/psxdisc.py disc/SCES01000.BIN hd-work/disc`.
  - Load them and print the counts. Expected: 1152 quads, 24 CLUTs, and the sky upload hash equal to the W1 dump name `39AD3C3DA790BFE9` (HIRO).
- [ ] **Step 6:** Commit with `feat(hd): read GGI sprites, TGI skybox and bonus TIM`.

### Task 3: Decode like the dumper, ST variants

**Files:**
- Create: `tools/hd/decode.py`
- Test: `tests/test_hd_decode.py`

**Interfaces:**
- Consumes: `Upload`, `Clut` (Task 2), `TextureKey` (Task 1).
- Produces:
  - `decode(upload: Upload, clut: Clut, semi: bool) -> PIL.Image.Image`: RGBA, `texel_width × height`.
  - `needs_st(clut: Clut) -> bool`: true if any entry is non-zero and has bit 15.
  - `keys_for(pair: Pairing) -> list[TextureKey]`: always the ordinary key, plus the ST key if `needs_st`.

- [ ] **Step 1: Write the failing tests**

```python
def test_decode_rounds_5bit(self):
    self.assertEqual(decode(p4_upload([1]), clut_with(1, 0x7FFF), False).getpixel((0, 0)), (255, 255, 255, 255))

def test_decode_zero_is_cutout(self):
    self.assertEqual(decode(p4_upload([0]), clut_with(0, 0x0000), False).getpixel((0, 0))[3], 0)

def test_decode_stp_alpha_143_only_in_st(self):
    self.assertEqual(decode(p4_upload([1]), clut_with(1, 0x8001), True).getpixel((0, 0))[3], 143)

def test_st_variant_when_palette_has_stp_bit(self):
    self.assertEqual([k.semi for k in keys_for(pair_with_clut(0x8001))], [False, True])
```

- [ ] **Step 2:** Run `.venv-hd/bin/python -m unittest tests.test_hd_decode -v`. Expected: FAIL.
- [ ] **Step 3:** Implement `decode`, `needs_st` and `keys_for`. Index order within a word: the low nibble or byte first, as `native_pixel` reads it.
- [ ] **Step 4:** Run the tests again. Expected: PASS.
- [ ] **Step 5:** Commit with `feat(hd): decode textures like the runtime dumper`.

### Task 4: Tileset textures and their palettes (format research with a fixed acceptance)

**Files:**
- Modify: `tools/hd/tgi.py`
- Create: `tools/hd/pairs.py` (fallback table loader), `tools/hd/pairs.json` (only if needed, hashes and coordinates only)
- Test: `tests/test_hd_tgi.py`

**Interfaces:**
- Produces:
  - `tgi.read_tiles(data: bytes) -> list[Pairing]`. The section starts after the skybox, with length at header `+0x18C`. Pairing rules:
    - the mipmap CLUT index (24 × 3 × 99 i16, `x = (v & 0x3F) << 4`, `y = v >> 6`)
    - plus the block tile CLUT indices at header `+0x12C`
  - `pairs.load(path: Path) -> set[tuple[int, int]]`: allowed `(source_hash, palette_hash)` pairs.
  - `pairs.apply(uploads: list[Upload], cluts: list[Clut], allowed: set[tuple[int, int]]) -> list[Pairing]`

- [ ] **Step 1:** Write tests for the parts the wiki fixes: the mipmap position decode `test_mipmap_clut_position`, the section offset `test_tiles_section_offset`, and `pairs.apply`, which keeps only the listed pairs.
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3: Work out the tileset layout from the disc** (local, `hd-work/`).
  - Hypothesis: the same CLUT and texture blocks as GGI sprites (`vramX, vramY, w, h`, data).
  - Acceptance: every `texupload` TexHash in a full-range W1 dump (`ReducePaletteRange: false`, Mac or Linux) of kind tile is produced by `read_tiles`.
- [ ] **Step 4: Pair palettes from the data.**
  - If the data cannot pair everything, generate `pairs.json` from full-range dumps of all worlds, with a dev-only `verify` mode from Task 9: hashes only, sorted, one pair per line.
  - Record in the file's header comment which worlds and levels it came from.
- [ ] **Step 5:** Run the tests again. Expected: PASS.
- [ ] **Step 6:** Commit with `feat(hd): read tileset textures and pair their palettes`. Before the commit, `git status` must show no PNGs or disc files.

### Task 5: Sky segmentation and per-quad filtering

**Files:**
- Create: `tools/hd/sky.py`
- Test: `tests/test_hd_sky.py`

**Interfaces:**
- Consumes: `SkyQuad`, `decode`.
- Produces:
  - `Upscaler = Callable[[Image.Image], Image.Image]`, a 4x colour upscaler. It lives in `tools/hd/upscale.py`, created here with `lanczos4(img) -> img`.
  - `segments(quads: list[SkyQuad]) -> list[tuple[int, int, int, int, int]]`: `(clut_y, x0, x1, y0, y1)` half-open, cut at a band change, a CLUT change and non-adjacent `atlas_x`, with `y1 = y0 + 15`.
  - `build_sky(atlas: Image.Image, quads: list[SkyQuad], clut_y: int, upscale: Upscaler) -> Image.Image`
    - Start with nearest 4x of the whole atlas in this palette.
    - Then paste each quad of `clut_y` as `upscale(atlas.crop(quad_box))` at 4x.
    - Alpha stays nearest.
    - Never use `resize(box=…)`; it reads outside the box (round-3 test bug).

- [ ] **Step 1: Write the failing tests**

```python
def test_segments_split_on_clut_change(self):
    self.assertEqual(len(segments([quad(0, 232, 0, 1), quad(0, 233, 1, 1)])), 2)

def test_sky_quad_filter_does_not_read_outside_crop(self):
    atlas = two_colour_atlas(left=(0, 0, 255), right=(255, 255, 255), split_x=16)
    out = build_sky(atlas, [quad(0, 232, 0, 16)], 232, lanczos4)
    self.assertEqual(out.getpixel((63, 8))[:3], (0, 0, 255))

def test_build_sky_keeps_size(self):
    self.assertEqual(build_sky(blank_atlas(), [], 232, lanczos4).size, (3072, 1024))
```

- [ ] **Step 2:** Run `.venv-hd/bin/python -m unittest tests.test_hd_sky -v`. Expected: FAIL.
- [ ] **Step 3:** Implement `segments`, `lanczos4` and `build_sky`.
- [ ] **Step 4:** Run the tests again. Expected: PASS.
- [ ] **Step 5:** Commit with `feat(hd): sky per-quad filtering from the TGI quad table`.

### Task 6: UI contour (M60R rule) and alpha classes

**Files:**
- Create: `tools/hd/contour.py`
- Test: `tests/test_hd_contour.py`

**Interfaces:**
- Produces:
  - `upscale_alpha_nearest(img: Image.Image) -> Image.Image`: alpha only, nearest 4x.
  - `region_count(mask: Image.Image) -> int`: 4-connected regions of alpha > 0.
  - `contour_mask(img: Image.Image, radius: float) -> Image.Image`: the 4x mask from Lanczos, Gaussian blur with `radius`, then a threshold at 128.
  - `round_ui(img: Image.Image, upscale: Upscaler) -> Image.Image`. The radius is the first of `(4, 2, 1.5)` whose `contour_mask` has the same `region_count` as the nearest mask, else no rounding.
    - Pixels inside the mask take the alpha class of the nearest visible source texel.
    - Colour is `upscale` inside and Lanczos-only within 4 px of the mask edge.
  - `check_classes(img: Image.Image) -> None`: raises `ValueError` if any alpha is not in {0, 143, 255}.

- [ ] **Step 1: Write the failing tests**

```python
def test_contour_radius_keeps_thin_stroke(self):
    self.assertEqual(region_count(round_ui(one_pixel_wide_letter_i(), lanczos4)), 2)

def test_round_ui_alpha_classes_only(self):
    check_classes(round_ui(blob_with_stp_texels(), lanczos4))

def test_check_classes_rejects_128(self):
    with self.assertRaises(ValueError):
        check_classes(Image.new("RGBA", (1, 1), (0, 0, 0, 128)))
```

- [ ] **Step 2:** Run `.venv-hd/bin/python -m unittest tests.test_hd_contour -v`. Expected: FAIL.
- [ ] **Step 3:** Implement the functions with Pillow (`ImageFilter.GaussianBlur`, a BFS for the regions).
- [ ] **Step 4:** Run the tests again. Expected: PASS.
- [ ] **Step 5:** Commit with `feat(hd): rounded UI contour with stable font regions`.

### Task 7: Classification and per-file upscale

**Files:**
- Create: `tools/hd/classify.py`
- Test: `tests/test_hd_classify.py`

**Interfaces:**
- Produces:
  - `classify(pair: Pairing, image: Image.Image) -> str`, returning `"sky"`, `"ui"` or `"other"`.
    - `sky`: `pair.upload.kind == "sky"`.
    - `ui`: `kind == "sprite"` and the image has alpha 0 or 143 (my call, replaces the spike's "seen in at least 9 worlds" heuristic, because GGI holds exactly the global sprites).
    - `other`: everything else.
  - `upscale_file(image: Image.Image, cls: str, upscale: Upscaler) -> Image.Image`
    - `other`: `upscale` colour plus alpha nearest.
    - `ui`: `round_ui`.
    - `sky`: handled by `build_sky`, so `upscale_file` raises `ValueError` here.

- [ ] **Step 1:** Write one test per class, plus `test_upscale_file_other_is_4x` and `test_upscale_file_rejects_sky`.
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement `classify` and `upscale_file`.
- [ ] **Step 4:** Run the tests again. Expected: PASS.
- [ ] **Step 5:** Commit with `feat(hd): classify textures and upscale per class`.

### Task 8: Build CLI, resume, atomic install, disc check

**Files:**
- Create: `tools/hd/build_pack.py`
- Test: `tests/test_hd_build_pack.py`

**Interfaces:**
- Consumes: everything above.
- Produces:
  - CLI `python3 -I tools/hd/build_pack.py DISC.cue WORK_DIR --install PACK_DIR [--progress FILE]`
  - `check_disc(exe: bytes) -> None`: raises `SystemExit` with a German message if the size or SHA-256 differs from `SCES_010.00`.
  - `write_progress(path: Path, step: str, done: int, total: int, state: str) -> None`: JSON `{"step","done","total","fraction","state"}` written via temp file and rename.
  - `install(staging: Path, target: Path) -> None`: rename the old pack to `<target>.old`, rename `staging` to `target`, delete `.old`. On failure the old pack is restored.
  - Marker `hd-pack.json` in the pack: `{"tool": "<git describe>", "upscaler": "lanczos"}`.
  - Resume: a file that already exists in `WORK_DIR/out` is skipped.

- [ ] **Step 1: Write the failing tests**

```python
def test_install_keeps_old_pack_when_build_fails(self):
    target = make_pack(self.tmp, "old")
    with self.assertRaises(OSError):
        install(self.tmp / "missing-staging", target)
    self.assertTrue((target / "old").exists())

def test_rejects_unknown_disc(self):
    with self.assertRaises(SystemExit):
        check_disc(b"\0" * 16)

def test_progress_fraction(self):
    write_progress(self.tmp / "p.json", "upscale", 1, 4, "running")
    self.assertEqual(json.loads((self.tmp / "p.json").read_text())["fraction"], 0.25)
```

- [ ] **Step 2:** Run `.venv-hd/bin/python -m unittest tests.test_hd_build_pack -v`. Expected: FAIL.
- [ ] **Step 3:** Implement the CLI as a sequence of the steps from Tasks 2–7. Write the PNGs to `WORK_DIR/out/<name>.png`, then `install`. Write `config.yaml` with `ReducePaletteRange: false`.
- [ ] **Step 4:** Run the tests again. Expected: PASS.
- [ ] **Step 5:** Run `task hd:build` against the local disc. Expected: a pack under `build-dev/mods/texture-packs/SCES-01000/` and a printed file count. Note the run time.
- [ ] **Step 6:** Commit with `feat(hd): build CLI with resume and atomic install`.

### Task 9: Verification against runtime dumps

**Files:**
- Create: `tools/hd/verify_pack.py`
- Test: `tests/test_hd_verify_pack.py`

**Interfaces:**
- Produces:
  - CLI `python3 -I tools/hd/verify_pack.py PACK_DIR DUMP_DIR [--pairs-out FILE]`
  - `coverage(pack: set[TextureKey], dumped: set[TextureKey]) -> tuple[set[TextureKey], set[TextureKey]]`, returning `(covered, missing)`. A dump key counts as covered when the same source hash, palette hash, size and `semi` exist in the pack. The offset and rect in the dump name are ignored, since the pack files are full uploads.
  - `--pairs-out` writes the missing `(source_hash, palette_hash)` pairs for Task 4's fallback.

- [ ] **Step 1:** Write the tests `test_coverage_ignores_dump_rect` and `test_coverage_reports_missing`. Write the dump names as reduced-free full-range strings in the test.
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement `coverage` and the CLI. Print covered and total counts, then the missing names.
- [ ] **Step 4:** Run the tests again. Expected: PASS.
- [ ] **Step 5: Real run.**
  - Dump W1/L1 with `ReducePaletteRange: false` (Linux, `state.toml` with `dump = "true"`, `config.yaml` in the pack root).
  - Run `verify_pack`. Expected: 100 % coverage, or every missing name explained. The four STP4 textures of the spike are explicitly accounted for.
- [ ] **Step 6:** Commit with `feat(hd): verify the offline pack against runtime dumps`.

### Task 10: Acceptance on Linux and Mac, docs

**Files:**
- Modify: `CLAUDE.md` (HD section: the builder, its tasks, the coverage result, gotchas)

- [ ] **Step 1 (Linux):** Run `task smoke` (3603, 0 misses), `task test PYTHON=.venv-hd/bin/python` and `task lint`. Expected: all pass.
- [ ] **Step 2 (Linux):** Load the pack and check W1/L1 with `hd_textures`. Expected: `applied_draws > 0`. A `present_shot` shows no sky lines.
- [ ] **Step 3 (Mac, via `SendMessage` to `kula-world-mac`):**
  - Push the branch first, after asking the user. Then the Mac builds the pack from its own disc.
  - It runs `verify_pack` per world (full-range dumps of all 15 levels, bonus, menus).
  - It measures 50 fps, `scene_gpu` and `gl_evictions` per world.
  - The user checks live: sky lines, sun spots, UI edges, font.
- [ ] **Step 4:** Update `CLAUDE.md`. Check `git status` (no PNGs, dumps or disc files), then commit with `docs: record HD offline builder status`.
