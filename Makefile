.PHONY: install-hooks lint check-ledmaps check-palettes test verify

# One-time per clone — installs the pre-commit framework hooks.
install-hooks:
	@command -v pre-commit >/dev/null 2>&1 || { echo "Error: pre-commit not installed (pip install pre-commit)."; exit 1; }
	pre-commit install
	@echo "pre-commit hooks installed. Run 'make lint' to check the whole tree."

# The whole gate: pre-commit suite over the tree plus the repo's own checks.
lint: check-ledmaps check-palettes
	pre-commit run --all-files

# WLED 16 scans ledmap files for the exact bytes "map":[ — a space breaks the mapping silently
check-ledmaps:
	@for f in glorb/*/ledmap.json; do grep -q '"map":\[' "$$f" || { echo "$$f: missing exact \"map\":[ — WLED 16 would ignore it"; exit 1; }; done; echo "ledmaps ok"
# committed palettes must equal the generator output and respect WLED's 18-stop / 0..255 rules
check-palettes:
	@python3 glorb/mkpalettes.py --check

# Offline tests: the palette emulation against known firmware values. Seconds.
test:
	python3 -m unittest discover -s tests -v

# make verify REF=<factory lamp> TARGET=<ported lamp>
REF ?=
TARGET ?=
# acceptance gate against the lamps: every ported preset within 15 % of the factory lamp's current estimate
verify: lint
	@test -n "$(REF)" -a -n "$(TARGET)" || { echo "usage: make verify REF=<factory lamp IP> TARGET=<ported lamp IP>"; exit 2; }
	python3 wledlab.py verify --ref $(REF) --target $(TARGET) --presets-file glorb/wled16-port/presets.json --restore-preset 4
