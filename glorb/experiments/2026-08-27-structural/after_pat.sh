#!/usr/bin/env sh
# Preset 14 single-segment candidates on the plain Fire-span palettes (186/185); pat.py uploads palettes 12-15.
set -eu
S=$(cd "$(dirname "$0")" && pwd)
cd "$S/../../.."
while pgrep -f "after_struct.sh" >/dev/null || pgrep -f "pat.py" >/dev/null; do sleep 5; done
PYTHONPATH=. python3 "$S/pat.py" '{"14":{"hip-single-112-fire":{"single":true,"fx":180,"sx":112,"ix":112,"c3":31,"pal":186,"bri":255},"hip-single-255-fire":{"single":true,"fx":180,"sx":255,"ix":255,"c3":31,"pal":186,"bri":255},"hip-single-180-fire64":{"single":true,"fx":180,"sx":180,"ix":180,"c3":31,"pal":185,"bri":255},"noise-ix35-fire":{"single":true,"fx":146,"sx":0,"ix":35,"pal":186,"bri":255}}}' > "$S/pat14.log" 2>&1
