#!/usr/bin/env bash
# Build our lamps' firmware into fleet/out/<env>.bin.
# usage: fleet/build.sh <WLED checkout at v16.0.1> [env ...]   (default: fleet_esp32 fleet_glorb)
# Needs pio and node on PATH, e.g. nix shell nixpkgs#platformio-core nixpkgs#nodejs --command ...
set -euo pipefail
repo=$(cd "$(dirname "$0")/.." && pwd)
wled=$(cd "${1:?usage: fleet/build.sh <WLED v16.0.1 checkout> [env ...]}" && pwd)
shift
envs=("$@")
[ ${#envs[@]} -gt 0 ] || envs=(fleet_esp32 fleet_glorb)

# The glorb_fx effect ids and every fleet config were checked against this tag only.
tag=$(git -C "$wled" describe --tags --exact-match 2>/dev/null || true)
[ "$tag" = v16.0.1 ] || { echo "WLED checkout is at '${tag:-untagged}', expected v16.0.1" >&2; exit 1; }

# Pending upstream fixes belong to every fleet build. Accept an already-applied
# patch on a repeat build; fail before compiling if the source no longer matches.
for patch in "$repo"/fleet/patches/*.patch; do
  if git -C "$wled" apply --reverse --check "$patch" 2>/dev/null; then
    echo "already applied: $(basename "$patch")"
  else
    git -C "$wled" apply --check "$patch"
    git -C "$wled" apply "$patch"
    echo "applied: $(basename "$patch")"
  fi
done

ln -sfn "$repo/glorb/usermod/glorb_fx" "$wled/usermods/glorb_fx"
ln -sfn "$repo/usermods/syslog_events" "$wled/usermods/syslog_events"
cat "$repo/glorb/usermod/glorb_fx/platformio_override.ini" "$repo/fleet/platformio_override.ini" \
  > "$wled/platformio_override.ini"
# Upstream CI stamps the build day the same way, so /json/info "vid" tells builds apart.
# Rebuilding at the same tycwled commit with WLED_VID=<vid from a crash line> regains the ELF
# that decodes its backtrace.
sed -i -r -e "s/define VERSION .+/define VERSION ${WLED_VID:-$(date +%y%m%d0)}/" "$wled/wled00/wled.h"

args=()
for e in "${envs[@]}"; do args+=(-e "$e"); done
(cd "$wled" && pio run "${args[@]}")

mkdir -p "$repo/fleet/out"
for e in "${envs[@]}"; do
  cp "$wled/.pio/build/$e/firmware.bin" "$repo/fleet/out/$e.bin"
  cp "$wled/.pio/build/$e/firmware.elf" "$repo/fleet/out/$e.elf"  # decodes crash backtraces
done
ls -l "$repo/fleet/out"
