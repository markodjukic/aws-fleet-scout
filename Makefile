SHELL := /bin/bash

.PHONY: help ensure-pixi install run test check build clean

help:
	@echo "Common targets:"
	@echo "  make install         # Install/update Pixi environment"
	@echo "  make run             # Show CLI help"
	@echo "  make test            # Run unit tests"
	@echo "  make check           # lint + typecheck + unit tests"
	@echo "  make build           # Build sdist/wheel"
	@echo "  make clean           # Remove build artifacts"

ensure-pixi:
	@command -v pixi >/dev/null 2>&1 || (echo "Pixi is not installed or not on PATH." && echo "Install it from https://pixi.sh/latest/ or use the devcontainer setup." && exit 127)

install: ensure-pixi
	pixi install

run: ensure-pixi
	pixi run cli-help

test: ensure-pixi
	pixi run test

check: ensure-pixi
	pixi run check

build: ensure-pixi
	pixi run build

clean:
	rm -rf dist build *.egg-info .pytest_cache .mypy_cache .coverage htmlcov
