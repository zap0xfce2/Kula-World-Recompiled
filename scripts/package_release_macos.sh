#!/usr/bin/env bash
# macOS release: psxrecomp's .app packager, plus our app icon and the HD texture runner.
#
# Usage (on the Mac, after a release build with -DPSX_RELEASE_CHANNEL=public):
#   scripts/package_release_macos.sh <build-dir>
#
# Writes: dist/Kula_World_Rerolled-<VERSION>-macOS-arm64.zip (+ .sha256)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD="$(cd "${1:?usage: $0 <build-dir>}" && pwd)"
VERSION="$(tr -d '[:space:]' <"${ROOT}/VERSION")"
BIN=Kula_World_Rerolled
APP_NAME="Kula World Rerolled"
OUT="${ROOT}/dist/macos"
SRC="${OUT}/src"

# The original cover is copyrighted: only our own box art may ship.
cmp -s "${BUILD}/assets/img/boxart.tga" "${ROOT}/assets/launcher/boxart.tga" ||
  { echo "error: ${BUILD} does not carry our own box art; reconfigure with -DPSX_RELEASE_CHANNEL" >&2; exit 1; }

# The packager reads notices from <repo>/runtime/licenses and docs from <repo>/;
# in this layout they live elsewhere, so hand it a small source folder.
rm -rf "${OUT}"
mkdir -p "${SRC}/runtime"
cp -R "${ROOT}/psxrecomp/runtime/licenses" "${SRC}/runtime/"
cp "${BUILD}/game.toml" "${BUILD}/game_options.toml" "${SRC}/"
cp -R "${BUILD}/tools" "${SRC}/tools"
sed "s/@VERSION@/${VERSION}/" "${ROOT}/packaging/macos/START_HERE.txt" >"${SRC}/START_HERE.txt"

# The packager calls python3 from PATH (mod channel filter needs 3.11+); the Mac's
# default python3 is 3.9, so put the requested interpreter first.
if [[ -n "${PYTHON:-}" ]]; then
  mkdir -p "${OUT}/bin"
  ln -sf "$(command -v "${PYTHON}")" "${OUT}/bin/python3"
  export PATH="${OUT}/bin:${PATH}"
fi

bash "${ROOT}/psxrecomp/tools/package_release_macos.sh" \
  --repo "${SRC}" --build "${BUILD}" --bin "${BIN}" \
  --app-name "${APP_NAME}" --package "${BIN}" \
  --bundle-id io.github.zap0xfce2.kulaworldrerolled --version "${VERSION}" \
  --game-config game.toml --data game_options.toml --data tools \
  --exclude-dev-mods --out "${OUT}" --no-zip

STAGE="$(echo "${OUT}"/stage/*-macos-*)"
APPDIR="${STAGE}/${APP_NAME}.app"
[[ "${STAGE}" == *-macos-arm64 ]] || { echo "error: expected an arm64 build, got ${STAGE}" >&2; exit 1; }

# Without a bundle icon Dock and Cmd+Tab show the generic exec symbol.
cp "${ROOT}/assets/launcher/kula.icns" "${APPDIR}/Contents/Resources/kula.icns"
/usr/libexec/PlistBuddy -c "Add :CFBundleIconFile string kula" "${APPDIR}/Contents/Info.plist"
# Our entry point keeps player data in ~/Library/Application Support instead of the bundle.
install -m 755 "${ROOT}/packaging/macos/launcher.sh" "${APPDIR}/Contents/MacOS/${APP_NAME}"
command rm -rf "${STAGE}/saves"
# Icon and entry point change the sealed resources: sign again like the packager does.
codesign --force --sign - "${APPDIR}/Contents/MacOS/${BIN}"
codesign --force --sign - "${APPDIR}"
codesign --verify --deep "${APPDIR}"

ZIP="${ROOT}/dist/${BIN}-${VERSION}-macOS-arm64.zip"
rm -f "${ZIP}" "${ZIP}.sha256"
# ditto keeps the symlinks and the signature intact; --norsrc leaves out the __MACOSX/ tree.
(cd "$(dirname "${STAGE}")" && ditto -c -k --norsrc --keepParent "$(basename "${STAGE}")" "${ZIP}")
(cd "${ROOT}/dist" && shasum -a 256 "$(basename "${ZIP}")" >"$(basename "${ZIP}").sha256")
echo "Wrote ${ZIP}"
