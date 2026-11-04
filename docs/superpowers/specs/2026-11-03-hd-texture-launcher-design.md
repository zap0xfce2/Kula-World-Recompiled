# HD texture pack, part 3: opt-in and background start – design

Status: approved by the user on 2026-11-03 (plugin route). Plan: `docs/superpowers/plans/2026-11-03-hd-texture-launcher.md`.
Deviations made while building it: the builder takes the folder as its existing disc
argument (no separate `--source`); the runner and the plugin share `tools/hd/python.lock`;
the runner lives at `tools/hd/` beside the executable; the plugin does not check `hd.lock`
(a second runner exits on its own).
Builds on `2026-11-02-hd-texture-offline-build-design.md` (parts 1 and 2 done).

## Goal
The player turns HD on in the launcher, the pack builds in the background from their own
disc, and the game uses it from the next start. No terminal, no prebuilt pack.

## Decided by the user (2026-11-03)
- **Two stages:** one switch turns HD on. Downloading the AI model needs its own,
  separate consent (licence CC BY-NC-SA 4.0, download size shown). Without it the
  builder makes the Lanczos pack (small download).
- **Python is fetched by our own code**, not shipped with the release and not taken from the
  system.
- **Upstream PRs only after asking.**

## Finding: where the start can live
- recomp-ui has no background job, no HTTP client and no process start for tools. The
  existing HD switch is NES-only (Mesen `hires.txt`).
- psxrecomp's trusted media preparers (`prepare = "provider.id"`, MOD_PACKAGES.md
  "Shared source media") run on PLAY and **block the launch** until they finish, and
  must ship their workers instead of downloading them. A 10-minute model build does not
  fit there.
- What a title plugin can already do, without framework changes:
  - **Read the options** the player set in the launcher: `psx_mod_option_value`, types
    boolean, choice and integer. The launcher renders and saves them by itself.
  - **Read files of the mounted disc:** `psx_mod_read_disc_file`, from emulation-thread
    callbacks. The builder needs only `SCES_010.00`, `HIRO/HIRO.GGI` and the `*.TGI` files.
  - **Switch on the framework's `psx.enhancement.hd-textures`:** `[[requirement]]`
    across packages, without writing to `state.toml`.
  - **Check the downloaded Python:** SHA-256 through `psx_sha256.h`.

## Recommended route (my call, needs approval): a Kula mod package, no upstream change
- New package `kula.hd-textures`, feature "HD textures", `default_enabled = false`, so the
  player has to opt in.
  - Boolean option "AI model": its label names the licence and about 1.5 GB of download.
    Default off.
  - `[[requirement]]` on `psx.enhancement.hd-textures/hd-textures`, so the pack loads
    without a second switch.
- Plugin `mods/src/kula_hd_textures.c`. On the first vblank of an offline session, and once
  per process:
  1. **Quit early** if the pack marker already matches what the options ask for, or if the
     runner reports a running build (`hd.lock` held).
  2. **Extract the source files** with `psx_mod_read_disc_file` into `<data>/source/`, with
     the same paths as on the disc. These are local files of the player and never in git.
     The plugin has no disc path, which is why it extracts.
  3. **Get Python if missing:** download it with the OS's own `curl`, check its SHA-256,
     unpack it with `tar`. Windows 10 1803 and later ships both, as do macOS and Linux.
     The target is `<data>/python` with `.ok`, so `hd_auto.py` skips its own Python phase.
  4. **Start `hd_auto.py`** detached with `--parent-pid <own pid>`, `--source <data>/source`
     and `--with-model` if the option is on.
- Changes to the builder and runner: `build_pack.py` also takes the extracted folder instead
  of a CUE (`disc_files` gets a second source), and `hd_auto.py` passes `--source` through.
- Where things live:
  - Runner files: `hd/` beside the executable. CMake copies them, like the box art.
  - Data folder: `hd-auto/` beside the executable, like `mods/`.
  - Pack: as before under `mods/texture-packs/SCES-01000`.
- The build runs while the game runs: it uses low priority and one core is left free (part
  2). On the Mac it showed no fps loss, though that was with a finished pack, not during a
  build. This has to be measured.
- Small logic parts get C tests in `task test`: decisions, argument lists, the file list.
  Process starts and downloads are checked on Linux and on the Mac.

### What this route gives up
- **No progress in the launcher.** The feature description says it once: "Builds in the
  background from your disc while you play; ready from the next start (10–20 min with the
  AI model)." `hd-auto/progress.json` exists for a later launcher view.
- **The build starts with the game**, not when the switch is flipped in the launcher.

## Alternative: build it into the launcher (upstream)
- A generic "background job" in recomp-ui would add a toggle, a licence dialog, process
  start, progress bar and stop. psxrecomp's `main.cpp` would hand over the disc path and the
  paths to the job.
- That means two upstream PRs, a long wait (recomp-ui#110 has been waiting since
  2026-10-20) and a large change in a 17,000-line host.
- It could follow later as progress only, on top of the recommended route.

## Left to the builder
- The exact texts of the option and the description, kept in the language of the launcher
  (English).
- How the Windows process is started: `CreateProcessW` with `DETACHED_PROCESS`, low
  priority. The job object is already in the runner.

## Acceptance
- Option off: nothing is downloaded or started, and no `hd-auto/` is created.
- Option on, no model: the next game start builds the Lanczos pack in the background, and the
  start after that shows it. W1 in HD.
- Model option on: m60 pack and model marker. Turning it off again later rebuilds as Lanczos.
- Closing the game stops the build, the next start resumes it.
- No fps loss while building (Mac, W1, 20 s, measured during a build).

## Open risks
- `psx_mod_read_disc_file` while the BIOS logo shows: duration of about 11 files with a few MB
  each. Unknown.
- `curl`/`tar` missing on old Windows versions: then error `network`, no pack, the game runs
  normally.
- GPU load from the model build (MPS) while playing: unmeasured.
