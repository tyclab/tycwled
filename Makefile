.PHONY: install-hooks lint check-ledmaps check-palettes test verify

install-hooks:
	@command -v pre-commit >/dev/null 2>&1 || { echo "Error: pre-commit not installed (pip install pre-commit)."; exit 1; }
	pre-commit install
	@echo "pre-commit hooks installed. Run 'make lint' to check the whole tree."

lint: check-ledmaps check-palettes
	pre-commit run --all-files

# WLED 16 scans ledmap files for the exact bytes "map":[ — a space breaks the mapping silently;
# the curtain's committed ledmap must equal its generator output
check-ledmaps:
	@for f in glorb/*/ledmap.json curtain/ledmap.json; do grep -q '"map":\[' "$$f" || { echo "$$f: missing exact \"map\":[ — WLED 16 would ignore it"; exit 1; }; done; echo "ledmaps ok"
	@python3 curtain/mkledmap.py --check
# committed palettes must equal the generator output and respect WLED's 18-stop / 0..255 rules
check-palettes:
	@python3 glorb/mkpalettes.py --check

test:
	python3 -m unittest discover -s tests -v

REF ?=
TARGET ?=
# acceptance check against the lamps: current ratio within 15 % of the factory lamp plus the structural criteria (see README, Checks)
verify: lint
	@test -n "$(REF)" -a -n "$(TARGET)" || { echo "usage: make verify REF=<factory lamp IP> TARGET=<ported lamp IP>"; exit 2; }
	python3 wledlab.py verify --ref $(REF) --target $(TARGET) --presets-file glorb/wled16-port/presets.json --restore-preset 4
