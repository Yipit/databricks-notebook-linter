# Changelog

## 0.2.1

### Fixed

- `!=` operator at the start of a line (from black/ruff-formatted expressions) was misidentified as a shell bang (`!`) magic command, causing entire enclosing blocks and function bodies to be incorrectly prefixed with `# MAGIC`

## 0.2.0

### Added

- Detect and prefix `dbutils.library.restartPython()` calls with `# MAGIC`, including when nested inside conditional or loop blocks

### Fixed

- Prevent credential leaks in `uv-publish.py` by catching publish failures without exposing the full command (including credentials) in a traceback (`e0d4f08`)

### Changed

- `push-release` Makefile target now creates a GitHub Release with release notes extracted from `CHANGELOG.md` and attaches built distribution artifacts (`d3c234e`)
- `tag-release` Makefile target now validates that a `CHANGELOG.md` entry exists for the target version before proceeding (`bee2f90`)
- Fixed repository URLs in `README.md` and `pyproject.toml` to use the correct GitHub org name (`d3c234e`)

## 0.1.0

Initial release.

- Fix bare magic commands (`%pip`, `%sql`, `%md`, `%sh`, `%fs`, `%run`, `%python`, `%r`, `%scala`) and shell bangs (`!`) in Databricks `.py`-format notebooks by prefixing with `# MAGIC`
- Handle multiline continuations (`\`)
- Handle block-level magic: `if`, `for`, `while`, `with`, `try` blocks containing magic are prefixed entirely
- Handle nested blocks up to arbitrary depth
- Handle compound blocks: `if/elif/else`, `try/except/finally` treated as single units
- Handle magic appearing only in secondary branches (`else`, `elif`, `except`, `finally`) by prefixing the entire compound block
- Check mode (default): report unfixed magic and exit 1
- Fix mode (`--fix`): rewrite files in place
- Pre-commit hook support
- 100% branch coverage test suite
