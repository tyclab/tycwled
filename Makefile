.PHONY: lint check-ledmaps check-palettes verify
# make verify REF=<factory lamp> TARGET=<ported lamp>
REF ?=
TARGET ?=
lint: check-ledmaps check-palettes
	python3 -m py_compile wledlab.py glorb/mkpalettes.py
	python3 -c "import json,glob; [json.load(open(f)) for f in glob.glob('glorb/**/*.json', recursive=True)]"
# WLED 16 scans ledmap files for the exact bytes "map":[ — a space breaks the mapping silently
check-ledmaps:
	@for f in glorb/*/ledmap.json; do grep -q '"map":\[' "$$f" || { echo "$$f: missing exact \"map\":[ — WLED 16 would ignore it"; exit 1; }; done; echo "ledmaps ok"
# committed palettes must equal the generator output and respect WLED's 18-stop / 0..255 rules
check-palettes:
	@python3 glorb/mkpalettes.py --check
# acceptance gate against the lamps: every ported preset within 15 % of the factory lamp's current estimate
verify: lint
	@test -n "$(REF)" -a -n "$(TARGET)" || { echo "usage: make verify REF=<factory lamp IP> TARGET=<ported lamp IP>"; exit 2; }
	python3 wledlab.py verify --ref $(REF) --target $(TARGET) --presets-file glorb/wled16-port/presets.json --restore-preset 4
