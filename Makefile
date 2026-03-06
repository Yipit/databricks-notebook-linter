.PHONY: setup test clean format lint build publish tag-release push-release release all

setup:
	@test -d .venv || uv venv --seed
	@uv sync

lint:
	@uv run ruff check .

format:
	@uv run ruff format .
	@uv run ruff check --fix .

test:
	@uv run pytest

build: clean
	@uv build

publish: build
	@uv run uv-publish.py pypi

clean:
	@rm -rf __pycache__/ .pytest_cache/
	@rm -rf dist/ build/
	@find . -name "*.pyc" -delete
	@find . -name "*.egg-info" -type d -exec rm -rf {} + 2>/dev/null || true
	@find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

# Usage: make tag-release VERSION=x.y.z
#
# Validates preconditions, runs tests/lint, bumps version in pyproject.toml
# and README, commits, and creates an annotated tag. Does NOT push or publish.
tag-release: _check-version _check-clean _check-branch _check-tag-free lint test
	@echo "==> Bumping version to $(VERSION)..."
	@python3 -c "\
	import re, pathlib; \
	p = pathlib.Path('pyproject.toml'); \
	p.write_text(re.sub(r'version = \".*?\"', 'version = \"$(VERSION)\"', p.read_text(), count=1))"
	@python3 -c "\
	import re, pathlib; \
	p = pathlib.Path('README.md'); \
	p.write_text(re.sub(r'rev: v[^\s]+', 'rev: v$(VERSION)', p.read_text()))"
	@uv sync
	@git add pyproject.toml README.md uv.lock
	@git commit -m "Release v$(VERSION)"
	@git tag -a "v$(VERSION)" -m "v$(VERSION)"
	@echo "==> Tagged v$(VERSION) (local only). Run 'make push-release VERSION=$(VERSION)' to publish."

# Usage: make push-release VERSION=x.y.z
#
# Builds, publishes to PyPI, then pushes the commit and tag. Nothing reaches
# the remote until PyPI succeeds.
push-release: _check-version _check-tag-exists publish
	@git push origin main
	@git push origin "v$(VERSION)"
	@gh release create "v$(VERSION)" --generate-notes dist/*
	@echo "==> Published and pushed v$(VERSION)"

# Usage: make release VERSION=x.y.z
#
# Combines tag-release and push-release into a single command.
release: tag-release push-release

# --- internal validation targets ---

_check-version:
	@test -n "$(VERSION)" || { echo "Usage: make <target> VERSION=x.y.z"; exit 1; }
	@echo "$(VERSION)" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+$$' || { echo "Error: VERSION must be semver (e.g. 1.2.3)"; exit 1; }

_check-clean:
	@git diff --quiet && git diff --cached --quiet || { echo "Error: working tree is not clean"; exit 1; }

_check-branch:
	@test "$$(git branch --show-current)" = "main" || { echo "Error: must be on main branch"; exit 1; }

_check-tag-free:
	@git tag -l "v$(VERSION)" | grep -q . && { echo "Error: tag v$(VERSION) already exists"; exit 1; } || true

_check-tag-exists:
	@git tag -l "v$(VERSION)" | grep -q . || { echo "Error: tag v$(VERSION) does not exist. Run 'make tag-release VERSION=$(VERSION)' first."; exit 1; }

all: setup test
