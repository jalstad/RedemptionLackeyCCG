# Redemption LackeyCCG plugin — update tool
#
# Common commands. If you've never used `make`, just open a terminal in this
# folder and type one of:
#
#   make setup     # one-time: install the optional image-cropping library
#   make run       # start the update tool (opens in your web browser)
#   make test      # run the automated checks (for developers)
#
# Non-technical maintainers can skip `make` entirely and just double-click
# "Start Update Tool.command" (macOS) or "Start Update Tool.bat" (Windows)
# inside the tools/updater/ folder.

PYTHON ?= python3

.DEFAULT_GOAL := help

.PHONY: help setup run test clean

help:
	@echo "Redemption plugin update tool — available commands:"
	@echo ""
	@echo "  make run      Start the tool (opens http://127.0.0.1:8765 in your browser)"
	@echo "  make setup    One-time: install Pillow (only needed for image cropping)"
	@echo "  make test     Run the automated test suite"
	@echo "  make clean    Remove Python cache files"
	@echo ""
	@echo "Not comfortable with the terminal? Double-click"
	@echo "  tools/updater/Start Update Tool.command   (macOS)"
	@echo "  tools/updater/Start Update Tool.bat       (Windows)"

setup:
	$(PYTHON) -m pip install -r tools/updater/requirements.txt

run:
	$(PYTHON) -m tools.updater.server

test:
	$(PYTHON) -m unittest discover -s tools/updater/tests -v

clean:
	find tools/updater -name '__pycache__' -type d -prune -exec rm -rf {} +
