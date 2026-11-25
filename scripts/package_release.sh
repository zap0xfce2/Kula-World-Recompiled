#!/usr/bin/env bash
# Thin wrapper around the shared psxrecomp bundled-release packager.
# Autofilled by tools/new_project_layout/setup_project.{sh,ps1}.
#
# Ships the COMPILED game built from this repo's committed generated/ C:
# executable, runtime data, bundled OpenBIOS, mod catalog, overlay toolchain.
# No sources, emitters, CLI, generated C, or BIOS dumps.
#
# Usage:
#   scripts/package_release.sh <build-dir> <artifact-tag> [recompiler-build-dir]
#   artifact-tag: Linux-x64 or Windows-x64 (system and CPU, as RecompStore expects)
#
# Writes: dist/Kula_World_Rerolled-<VERSION>-<artifact-tag>.zip
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD_DIR="${1:-}"
ARTIFACT_TAG="${2:-}"
RECOMPILER_BUILD="${3:-build-recompiler}"

if [[ -z "${BUILD_DIR}" || -z "${ARTIFACT_TAG}" ]]; then
  echo "usage: $0 <build-dir> <artifact-tag> [recompiler-build-dir]" >&2
  exit 2
fi

PACKAGER="${ROOT}/psxrecomp/tools/package_game_release.sh"
if [[ ! -f "${PACKAGER}" ]]; then
  echo "error: missing ${PACKAGER} (psxrecomp submodule predates bundled releases -- bump it)" >&2
  exit 1
fi
chmod +x "${PACKAGER}" 2>/dev/null || true

EXTRA=()
# Overlay shard cache. It is compiled FROM THE DISC, so CI (no disc) cannot
# build one: the committed static AOT shard is linked into the executable and
# the bundled overlay_toolchain/ compiles the rest from the player's disc at
# runtime. A developer packaging locally with a cache can ship it instead:
#   PSX_OVERLAY_CACHE_ROOT=/path/to/cache scripts/package_release.sh ...
if [[ -n "${PSX_OVERLAY_CACHE_ROOT:-}" ]]; then
  EXTRA+=(--overlay-cache-root "${PSX_OVERLAY_CACHE_ROOT}")
else
  EXTRA+=(--ship-without-overlay-cache-because \
    "Kula World streams no overlays (no Load/Exec in the EXE), the whole game is compiled in")
fi
# Extra docs shipped at the zip root (DISC.md tells players which dump works).
for _doc in DISC.md; do
  if [[ -f "${ROOT}/${_doc}" ]]; then
    EXTRA+=(--doc "${_doc}")
  fi
done

# The original cover is copyrighted: only our own box art may ship.
if ! cmp -s "${ROOT}/${BUILD_DIR}/assets/img/boxart.tga" "${ROOT}/assets/launcher/boxart.tga"; then
  echo "error: ${BUILD_DIR} does not carry our own box art (original cover?); reconfigure with -DPSX_RELEASE_CHANNEL" >&2
  exit 1
fi
# Kula World streams no overlays (no Load/Exec in the EXE), so the overlay compiler stays out.
EXTRA+=(--no-overlay-toolchain)
# HD texture runner (tools/hd), started by the kula.hd-textures plugin beside the exe.
EXTRA+=(--runtime-dir tools)

cd "${ROOT}"
bash "${PACKAGER}" --stage-only \
  --root "${ROOT}" \
  --build-dir "${BUILD_DIR}" \
  --artifact "${ARTIFACT_TAG}" \
  --zip-prefix Kula_World_Rerolled \
  --exe-name Kula_World_Rerolled \
  --display-name "Kula World Rerolled" \
  --recompiler-build "${RECOMPILER_BUILD}" \
  --version-env RELEASE_VERSION \
  --disc-hint "your legally owned Kula World disc" \
  "${EXTRA[@]}"

# The framework README describes overlay_toolchain/, which this release leaves out.
VERSION="$(tr -d '[:space:]' <"${ROOT}/VERSION")"
STAGE="${ROOT}/dist/stage-game-${ARTIFACT_TAG}"
ZIP="${ROOT}/dist/Kula_World_Rerolled-${VERSION}-${ARTIFACT_TAG}.zip"
sed -i '/^overlay_toolchain\//,$d' "${STAGE}/README.txt"
cat >>"${STAGE}/README.txt" <<EOF
HD Textures (off by default, see the launcher's Mods page) builds an HD pack
from your disc in the background; tools/ holds its builder.
EOF
command rm -f "${ZIP}" "${ZIP}.sha256"
python3 "${ROOT}/psxrecomp/tools/create_release_zip.py" --source "${STAGE}" --output "${ZIP}" >/dev/null
(cd "${ROOT}/dist" && sha256sum "$(basename "${ZIP}")" >"$(basename "${ZIP}").sha256")
echo "Wrote ${ZIP}"
