#!/usr/bin/env sh
cd /home/tycorc/git/tycstation/tycwled
S=glorb/experiments/2026-08-27-structural
while pgrep -f "$S/after_struct.sh" >/dev/null || pgrep -f "python3 $S/pat.py" >/dev/null; do sleep 5; done
for n in 14 15; do PYTHONPATH=. python3 -c "import wledlab; print(wledlab.upload('10.27.4.158','/palette$n.json','$S/palette$n.json'))"; done
PYTHONPATH=. python3 $S/pat.py '{"14":{"hip-single-112-fire":{"fx":180,"sx":112,"ix":112,"c3":31,"pal":186,"bri":255},"hip-single-255-fire":{"fx":180,"sx":255,"ix":255,"c3":31,"pal":186,"bri":255},"hip-single-180-fire64":{"fx":180,"sx":180,"ix":180,"c3":31,"pal":185,"bri":255},"noise-ix35-fire":{"fx":146,"sx":0,"ix":35,"pal":186,"bri":255}}}' > $S/pat14.log 2>&1
