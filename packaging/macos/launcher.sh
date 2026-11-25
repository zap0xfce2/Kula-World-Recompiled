#!/bin/sh
# Bundle entry point (CFBundleExecutable). Player data must live outside the .app: the
# bundle is signed, replaced on update, and read-only when macOS translocates it.
RES="$(cd "$(dirname "$0")/../Resources" && pwd)"
DATA="$HOME/Library/Application Support/Kula World Rerolled"
mkdir -p "$DATA" || exit 1

# Mirror the bundle's files as symlinks (the bundle path changes under translocation, so
# rebuild them each start). Files the game writes replace their link with a real file.
find "$DATA" -type l -delete
(cd "$RES" && find . -type d) | while IFS= read -r dir; do mkdir -p "$DATA/$dir"; done
(cd "$RES" && find . -type f ! -name game.toml) | while IFS= read -r file; do
    [ -e "$DATA/$file" ] || ln -s "$RES/$file" "$DATA/$file"
done
# The launcher rewrites game.toml in place: give it a copy, never the bundle's file.
cp -f "$RES/game.toml" "$DATA/game.toml"

# The runtime anchors every file it reads or writes at the folder of $APPIMAGE.
export APPIMAGE="$DATA/Kula_World_Rerolled"
export SDL_JOYSTICK_HIDAPI_STEAM=1
cd "$DATA" || exit 1
if [ "$#" -eq 0 ]; then
    exec "$(dirname "$0")/Kula_World_Rerolled" --game "$DATA/game.toml"
fi
exec "$(dirname "$0")/Kula_World_Rerolled" "$@"
