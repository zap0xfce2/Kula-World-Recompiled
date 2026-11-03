# HD texture offline build (part 2: model mix and background runner) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The builder from part 1 makes the user's chosen look (M60, M60R, H-M) with IllustrationJaNai. A stdlib-only runner sets up Python, packages and the model on the player's machine and builds the pack in the background with a `progress.json`. Without the model it builds the Lanczos pack.

**Architecture:**
- `tools/hd/model.py` wraps the model as an `Upscaler` (the callable type from part 1) and mixes it 60/40 with Lanczos.
  - Every class already takes an `Upscaler`: `upscale_file` (M60), `round_ui` (M60R: model inside, Lanczos at the edge), `build_sky` (H-M on the panorama).
  - So the mix plugs in without touching the steps.
- `tools/hd/hd_auto.py` is the runner, adapted from Hercules `port/hd/hd_auto.py`.
  - It has no download of a prebuilt pack (spec non-goal).
  - Phases: python, packages, model, build.

**Tech Stack:** Python 3.12, Pillow, xxhash, torch, spandrel 0.4.1, `unittest`, ruff, black, go-task.

**Spec:** `docs/superpowers/specs/2026-11-02-hd-texture-offline-build-design.md`. Part 1: `docs/superpowers/plans/2026-11-02-hd-texture-offline-build.md`.

## Decisions made while planning (my calls, measured 2026-11-03)

**Mipmaps get Lanczos, not the model.**
- Unique RGB images the model would have to run on (all worlds):

  | Kind | Images | Source pixels |
  |---|---|---|
  | Full tiles (P8 64x64) | 954 | 3.9 M |
  | Mipmaps (P4 32x32 and 16x16) | 22,814 | 14.6 M |
  | Sprites | 91 | 0.14 M |
  | Bonus sky | 1 | 0.03 M |
  | Sky panoramas (10 worlds) | 10 | about 2.8 M |

- The mipmaps exist once per fog palette.
- Fog palettes are not an affine map of the base palette, so they cannot be derived from one model run (per-channel fit: median error 6.8, p90 23.8 of 255).
- Mipmaps are only drawn far away, a few screen pixels per texel.
- Effect: the model work drops to about 6.9 M of 21.5 M pixels (about a third).
- Cost if wrong: distant cubes look softer than near ones. Fix: a one-line change in `upscaler_for`, then a rebuild.

**Sky stays a panorama.**
- The spec says H-M2 per band segment. Tool version 7 replaced that with one panorama, and the user approved it live on the Mac ("Nahtlos, gefällt mir").
- H-M is therefore the 60/40 mix on the panorama.

**Model inference once per source image.**
- ST and plain variants share their RGB, but sorted names put them far apart.
- So the model output is cached on disk under `<work>/model/<sha1 of size + RGB>.png`, which also survives a resume.

**This Linux box cannot run the model.**
- Alpine/musl has no torch wheels, and python-build-standalone ships glibc builds.
- Model code is unit-tested with fake models here. Real inference and the runner's model phase are verified on the Mac (MPS) and, for CPU time, on the Mac with `--device cpu`.
- The Lanczos path of the runner is verified here with `--python .venv-hd/bin/python`.

**Supported platforms for the portable Python:**
- `linux-x86_64` (gnu), `windows-x86_64`, `macos-aarch64`.
- Elsewhere the runner needs `--python` or fails with `error: "platform"`.

## Global Constraints

- **Hard rule:** No PNG, dump, model, wheel, Python tarball or disc file in git. The repo holds code, URLs, versions and SHA-256 values only.
- **Model:** `4x_IllustrationJaNai_V1_DAT2_190k.pth` from `https://github.com/the-database/MangaJaNai/releases/download/1.0.0/IllustrationJaNai_V1_ModelsOnly.zip`.
  - zip SHA-256 `6f5496f5ded597474290403de73d7a46c3f8ed328261db2e6ff830a415a6f60b`
  - member `IllustrationJaNai/4x_IllustrationJaNai_V1_DAT2_190k.pth`, SHA-256 `a82f3a2d8d1c676171b86a00048b7a624e3c62c87ec701012f106a171c309fbe` (values from Hercules; Task 4 confirms them on download)
  - Licence CC BY-NC-SA: downloaded only with `--with-model`, never shipped.
- **Mix:** `MODEL_WEIGHT = 0.6` (model) on the colours. Alpha stays nearest in the classes 0/143/255, exactly as in part 1.
- **Python:** CPython 3.12.14, python-build-standalone release `20260825`, `install_only_stripped`. Hercules pins for linux/windows:
  - `cpython-3.12.14%2B20260825-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz`, SHA-256 `7ce4a71285d913955a76053cc7605ea96da8ecada54dba9cf395245961816421`
  - `cpython-3.12.14%2B20260825-x86_64-pc-windows-msvc-install_only_stripped.tar.gz`, SHA-256 `8e6aad12ef6fc9685e67ce66253f8f72d6e8fa02cb7187e5850bd4db5ecd9e2a`
  - The macOS `aarch64-apple-darwin` digest is taken from that release's `SHA256SUMS` in Task 3.
- **Packages:**
  - Base set: `pillow`, `xxhash`.
  - Model set: base plus `torch==2.7.0`, `spandrel==0.4.1`, `numpy`. On Linux and Windows, torch comes from `https://download.pytorch.org/whl/cpu` (`+cpu`). On macOS it comes from PyPI (has MPS).
  - Installed with `pip install --require-hashes --only-binary=:all:` from lock files in `tools/hd/requirements/`.
- **CPU share:**
  - One core stays free: `OMP_NUM_THREADS = MKL_NUM_THREADS = max(1, cpu_count - 1)`, and `torch.set_num_threads` gets the same.
  - Process priority: nice 19, or below-normal on Windows.
- **progress.json** (what part 3 shows): `{"phase", "fraction", "eta", "state": "running"|"done"|"failed", "error", "updated"}`, written atomically.
- **Pack marker** `hd-pack.json`: `{"tool": TOOL_VERSION, "upscaler": "lanczos"|"m60", "model_sha256": <hex>|null}`.
- **User rules:** type hints, no bare `except`, functions of about 30 lines, ruff and black clean, one assert per test, no game data in tests.

## Review Focus

1. **The model download fails or the network is gone.** Expected: the runner still installs a Lanczos pack, sets `error: "network"` with `state: "done"`, and the next start with `--with-model` upgrades it. Test `test_model_failure_falls_back_to_lanczos` (Task 3).
2. **A download is corrupt or truncated.** Expected: the `.part` file is deleted and the run fails with `error: "download"`. A corrupt file never counts as present. Test `test_download_rejects_checksum_mismatch` (Task 3).
3. **The launcher quits mid-build.** Expected: the runner and its build child stop, and the next start resumes. Finished PNGs are kept by part 1. Test `test_second_instance_exits` (Task 3) pins the lock. Watching the parent PID is checked by hand in Task 4.
4. **An installed Lanczos pack while the model is now available, or an older tool version.** Expected: rebuild. An up-to-date pack is not rebuilt. Test `test_needs_build_when_marker_differs` (Task 3).
5. **Large images on CPU** (sky panorama 784x360 into DAT2). Expected: tiled inference with the same result as one pass on a pointwise model, and no out-of-memory error. Test `test_tiled_equals_whole_for_pointwise_model` (Task 1).

---

### Task 1: Model upscaler, mix and disk cache

**Files:**
- Create: `tools/hd/model.py`
- Test: `tests/test_hd_model.py`

**Interfaces:**
- Consumes: `Upscaler`, `SCALE`, `lanczos4` from `hd.upscale`.
- Produces:
  - `MODEL_WEIGHT = 0.6`
  - `mix(model: Upscaler, weight: float = MODEL_WEIGHT) -> Upscaler`: RGB result `Image.blend(lanczos4(img), model(img), weight)`.
  - `tiled(model: Upscaler, tile: int = TILE, overlap: int = OVERLAP) -> Upscaler`, with `TILE = 256` and `OVERLAP = 16`.
    - Images up to `tile` on both sides pass straight through.
    - Larger ones are cut into tiles with `overlap` source pixels of context on each side. Each tile is upscaled, and only its core is pasted back.
  - `disk_cached(model: Upscaler, directory: Path) -> Upscaler`: key `sha1(f"{w}x{h}".encode() + rgb_bytes)`. A hit reads the PNG, a miss writes it via a temp name plus `os.replace`.
  - `load_model(path: Path, device: str | None = None) -> Upscaler`.
    - Imports torch and spandrel inside the function, so the module imports without torch.
    - Device: `cuda` if available, else `mps`, else `cpu`, unless one is given.
    - Calls `torch.set_num_threads(max(1, os.cpu_count() - 1))`.
    - Runs `spandrel.ModelLoader(device).load_from_file(path)`, then `.eval()`.
    - Per image: RGB to float tensor `(1,3,H,W)` in [0,1], descriptor call under `torch.inference_mode()`, back to RGB uint8 with rounding.
  - `model_upscaler(path: Path, cache: Path, device: str | None = None) -> Upscaler` = `mix(disk_cached(tiled(load_model(path, device)), cache))`.

- [ ] **Step 1: Write the failing tests** in `tests/test_hd_model.py`, with synthetic images and fake models only:

```python
def nearest4(image): return image.convert("RGB").resize((image.width * 4, image.height * 4), Image.Resampling.NEAREST)
def white4(image): return Image.new("RGB", (image.width * 4, image.height * 4), (255, 255, 255))

def test_mix_weights_model_sixty_percent(self):
    black = Image.new("RGB", (4, 4), (0, 0, 0))
    self.assertEqual(mix(white4)(black).getpixel((8, 8)), (153, 153, 153))

def test_tiled_equals_whole_for_pointwise_model(self):
    image = Image.effect_noise((300, 40), 64).convert("RGB")
    self.assertEqual(tiled(nearest4, tile=64, overlap=8)(image).tobytes(), nearest4(image).tobytes())

def test_disk_cache_runs_model_once_per_image(self):
    calls = []
    def counting(image): calls.append(1); return nearest4(image)
    cached = disk_cached(counting, Path(self.tmp))
    cached(Image.new("RGBA", (2, 2), (9, 9, 9, 143))); cached(Image.new("RGBA", (2, 2), (9, 9, 9, 255)))
    self.assertEqual(len(calls), 1)  # same RGB, different alpha (ST and plain variant)

def test_module_imports_without_torch(self):
    self.assertNotIn("torch", sys.modules)
```

`self.tmp` comes from `tempfile.mkdtemp()` in `setUp`.

- [ ] **Step 2: Run** `.venv-hd/bin/python -m unittest tests.test_hd_model -v`. Expected: ImportError, because `hd.model` does not exist yet.
- [ ] **Step 3: Implement** `tools/hd/model.py` with the interfaces above.
- [ ] **Step 4: Run** the same command. Expected: 4 passed. Then run `task test` and `task lint`, both green.
- [ ] **Step 5: Commit** `feat(hd): add model upscaler with 60/40 Lanczos mix`.

### Task 2: Model in the builder (M60, M60R, H-M; mipmaps Lanczos)

**Files:**
- Modify: `tools/hd/build_pack.py` (`pair_job`, `world_sky`, `sky_jobs`, `collect_jobs`, `stage`, `main`)
- Modify: `tools/hd/requirements.txt` stays the base set; add `tools/hd/requirements-model.txt` (`torch`, `spandrel==0.4.1`, `numpy`) for dev on the Mac.
- Test: `tests/test_hd_build_pack.py`

**Interfaces:**
- Consumes: `model_upscaler` (Task 1), `Pairing` and `Upload.kind`/`depth` from `hd.assets`.
- Produces:
  - CLI `build_pack.py DISC WORK --install PACK [--progress FILE] [--model PTH] [--device DEV]`.
  - `upscaler_for(pair: Pairing, model: Upscaler) -> Upscaler`: `lanczos4` for `kind == "tile" and depth == 4` (mipmaps), else `model`.
  - Name `"m60"` with a model, `"lanczos"` without. The cache dir is `out-v<TOOL_VERSION>-<name>`, and the model disk cache is `<work>/model`.
  - `stage(out, staging, names, model_sha256: str | None)` writes the marker from the Global Constraints.
  - `TOOL_VERSION` stays 7, because the Lanczos output is unchanged and the new name separates the caches.

- [ ] **Step 1: Write the failing tests:**

```python
def test_mipmaps_use_lanczos(self):
    pair = Pairing(Upload(0, 0, 8, 32, 4, b"\0" * 512, "tile"), Clut(0, 0, b"\0" * 32))
    self.assertIs(upscaler_for(pair, fake_model), lanczos4)

def test_full_tiles_use_the_model(self):
    pair = Pairing(Upload(0, 0, 32, 64, 8, b"\0" * 4096, "tile"), Clut(0, 0, b"\0" * 512))
    self.assertIs(upscaler_for(pair, fake_model), fake_model)

def test_marker_records_model_hash(self):
    # stage() into a temp dir with one dummy PNG; read hd-pack.json
    self.assertEqual(marker["model_sha256"], "ab" * 32)
```

- [ ] **Step 2: Run** `.venv-hd/bin/python -m unittest tests.test_hd_build_pack -v`. Expected: the 3 new tests fail (ImportError or TypeError).
- [ ] **Step 3: Implement.**
  - `pair_job` takes the upscaler from `upscaler_for`.
  - `world_sky` and `sky_jobs` get the model upscaler. Keep `@lru_cache` keyed by `(tgi, upscale)`.
  - `main` adds `--model` and `--device`. It hashes the model file (`hashlib.sha256`, 1 MiB chunks) and passes the hash to `stage`.
- [ ] **Step 4: Run** `task test` and `task lint`, both green. Then run `task hd:build`. Expected: 48,867 files, cache `out-v7-lanczos` reused, so no file is re-rendered.
- [ ] **Step 5: Commit** `feat(hd): use the model mix in the builder, Lanczos for mipmaps`.

### Task 3: Runner with progress, locks and Lanczos fallback

**Files:**
- Create: `tools/hd/hd_auto.py` (stdlib only, no imports from `hd.*`, because it runs before Pillow exists)
- Create: `tools/hd/requirements/{base,model}-{linux-x86_64,windows-x86_64,macos-aarch64}.txt`, pinned with `--hash=sha256:` for every package including dependencies
- Create: `tools/hd/lock.py`
  - Regenerates the lock files with `pip download --only-binary=:all: --python-version 3.12 --platform <tag> [--index-url …]` into a temp dir, then writes `name==version --hash=sha256:<digest>` for each wheel.
  - Platform tags: `manylinux_2_28_x86_64`, `win_amd64`, `macosx_11_0_arm64`.
- Modify: `Taskfile.yaml`. Add `hd:lock` and `hd:auto` (`{{.PYTHON}} -I tools/hd/hd_auto.py --disc {{.DISC}} --pack build-dev/mods/texture-packs/SCES-01000 --data hd-auto {{.CLI_ARGS}}`), and add `hd-auto/` to `.gitignore`.
- Test: `tests/test_hd_auto.py`

**Interfaces:**
- Consumes: `build_pack.py` CLI (Task 2), the requirements files and the model constants (Global Constraints).
- Produces:
  - CLI `hd_auto.py --disc CUE --pack DIR --data DIR [--with-model] [--python PY] [--device DEV] [--parent-pid PID]`.
  - Phases, weighted as in Hercules (`python 0.3`, `packages 1.5`, `model 0.4`, `build 97.8`):
    - `python`: download and unpack the portable Python into `<data>/python`, unless `--python` is given.
    - `packages`: `pip install --require-hashes --only-binary=:all: -r <lock>`, with the model set only for `--with-model`. A stamp file holds the lock file's SHA-256, so a changed lock reinstalls.
    - `model`: only with `--with-model`. Download the zip, extract the one member and check both digests.
    - `build`: run `build_pack.py` in that Python, with `--model` if present and `--progress <data>/build.progress.json`. Mirror its fraction into `progress.json` with an ETA from the last 15 minutes (Hercules logic).
  - Fallback:
    - If the `packages` (model set) or `model` phase fails with `network` or `download`, log it, use the base set, build Lanczos and finish with `state: "done", error: <code>`.
    - Any other failure ends with `state: "failed"`.
  - `needs_build(pack: Path, want: dict) -> bool`: compares `hd-pack.json` with `{"tool", "upscaler", "model_sha256"}`. The runner skips the build when this is False.
    - It reads the tool version via `build_pack.py --print-tool-version`, which Step 3 adds as a one-line flag.
  - Lock `<data>/hd.lock` (`fcntl`/`msvcrt`): a second instance exits 0 without doing anything.
  - Own process group, SIGTERM stops the group, `--parent-pid` watcher, low priority, the CPU env from the Global Constraints, a 6 GB free-disk check before the first setup.
  - After `done`: delete `<data>/{downloads,python,work}`, but keep `<data>/model` and the log. A later run with the model then does not download it again.

- [ ] **Step 1: Write the failing tests** (no network, no subprocess):

```python
def test_progress_fraction_counts_finished_phases(self):
    # Progress(path).set("model", 0.5) with default phases
    self.assertAlmostEqual(read(path)["fraction"], round((0.3 + 1.5 + 0.2) / 100.0, 4))

def test_download_rejects_checksum_mismatch(self):
    # file:// URL to a temp file, wrong digest
    with self.assertRaises(Failed) as ctx: download(url, dst, "0" * 64, lambda f: None)
    self.assertEqual(ctx.exception.code, "download")

def test_download_keeps_verified_file(self): ...  # existing dst with right digest: no read of url (url points to a missing file)

def test_needs_build_when_marker_differs(self):
    # marker upscaler "lanczos", want "m60"
    self.assertTrue(needs_build(pack, want))

def test_no_build_when_marker_matches(self): ...

def test_second_instance_exits(self):
    first = single_instance(data); self.assertIsNone(single_instance(data))

def test_model_failure_falls_back_to_lanczos(self):
    # run_phases with fake phase functions: model phase raises Failed("network");
    # the build fake records whether it got a model path
    self.assertIsNone(built_with_model)
```

`run_phases(args, data, prog, steps)` takes the four phase callables, so the fallback is testable without I/O. `main` passes the real ones.
- [ ] **Step 2: Run** `.venv-hd/bin/python -m unittest tests.test_hd_auto -v`. Expected: ImportError.
- [ ] **Step 3: Implement** `hd_auto.py`.
  - Port from the Hercules file, minus its release-download part: `Progress`, `download`, `ssl_context`, `single_instance`, `tie_children`, `stop_all`, `watch_parent`, `lower_priority`, `phase_python`, `phase_build`.
  - Then add the macOS Python entry, the lock-file installs, the model phase, `needs_build` and `run_phases`.
  - Also add `--print-tool-version` to `build_pack.py`.
- [ ] **Step 4: Run** `task hd:lock`. Expected: 6 lock files, every line with `--hash=sha256:`, and torch lines with `+cpu` for linux and windows. Then `task test` and `task lint`, both green.
- [ ] **Step 5: Linux end-to-end, Lanczos:** `task hd:auto -- --python .venv-hd/bin/python`. Expected:
  - `progress.json` ends with `state: "done"`.
  - The pack marker says `lanczos`, and the file count is 48,867.
  - A second run returns at once (`needs_build` False).
- [ ] **Step 6: Commit** `feat(hd): add background runner with progress and Lanczos fallback`.

### Task 4: Acceptance on the Mac, docs

**Files:**
- Modify: `CLAUDE.md` (HD section: part 2 state, measured times, the mipmap decision)
- Modify: `docs/superpowers/specs/2026-11-02-hd-texture-offline-build-design.md` (note that the sky is a panorama, not per segment)

- [ ] **Step 1: Push** after the user approves, then send the Mac a test order via `SendMessage`:
  - `task hd:auto -- --with-model` from scratch, with a fresh `--data`. Log the time per phase, check that the model digests match, and check the device (`mps`).
  - CPU estimate: build the full tiles of W1 only with `--device cpu` and extrapolate.
  - Stop the launcher stand-in (`--parent-pid` of a `sleep` process, then kill it) mid-build: the runner and its children end, and a restart resumes.
  - Runtime with the pack, in W1, W2 and two more worlds: 50 fps, `scene_gpu`, `gl_evictions` after a route, `composition_builds` 0. Then the user's live verdict on the look, against the Lanczos pack. Watch for boxes at HUD and font, sky seams, spots around the sun, frayed UI edges, and soft distant cubes (the mipmap decision).
  - The usual Mac rules apply: `SDL_AUDIO_DRIVER=dummy`, stop yabai and restart it afterwards, no commits.
- [ ] **Step 2: Docs:** record the results in `CLAUDE.md` and the panorama note in the spec. If the user dislikes the soft distant cubes, change `upscaler_for` (Task 2) and measure again.
- [ ] **Step 3: Commit** `docs: note HD part 2 acceptance` (after user approval).
