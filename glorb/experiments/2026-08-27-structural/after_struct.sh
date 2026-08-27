#!/usr/bin/env sh
cd /home/tycorc/git/tycstation/tycwled
S=glorb/experiments/2026-08-27-structural
while pgrep -f "python3 $S/structural.py" >/dev/null; do sleep 5; done
PYTHONPATH=. python3 $S/pat.py '{"2":{"noise-ix35-sx0-steep":{"fx":146,"sx":0,"ix":35,"pal":188,"col":[[0,0,0],[255,255,255],[255,255,255]]},"noise-ix50-sx0-steep":{"fx":146,"sx":0,"ix":50,"pal":188,"col":[[0,0,0],[255,255,255],[255,255,255]]},"noise-ix35-sx0-lin":{"fx":146,"sx":0,"ix":35,"pal":187,"col":[[0,0,0],[255,255,255],[255,255,255]]},"noise-ix35-sx80-steep":{"fx":146,"sx":80,"ix":35,"pal":188,"col":[[0,0,0],[255,255,255],[255,255,255]]},"hip-255-floor0":{"fx":180,"sx":255,"ix":255,"c3":31,"pal":3,"col":[[0,0,0],[255,255,255],[255,255,255]]},"current":{"fx":180,"sx":32,"ix":32,"c3":31,"pal":3,"col":[[150,150,150],[255,255,255],[255,255,255]]}}}' > $S/pat.log 2>&1
