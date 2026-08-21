# Changelog

## 0.3.0

### Added

Rules:

- `DNL002` (`leading-blank-lines`): strip leading blank lines from Python cells, including the blank line Databricks inserts after each `# COMMAND ----------` separator. Magic language cells (`# MAGIC %md`, `# MAGIC %sql`, ...) are skipped
- `DNL003` (`trailing-empty-cells`): remove empty cells, and their preceding separators, from the end of a notebook
- `DNL004` (`empty-cells`): remove empty cells anywhere in a notebook. The header cell is never removed
- `DNL005` (`no-widget-config`): report reads of notebook config via `dbutils.widgets.get()` and `dbutils.widgets.getArgument()`. Off by default and check-only -- it has no autofix, and fails the run in both check and `--fix` mode

Rule selection:

- `--select` and `--ignore` to control which rules run, and `--list-rules` to print the catalog with each rule's default state
- Check mode (the default) reports per-rule diagnostics as `path:line: [CODE] message`; `--fix` reports which rules changed each file

Configuration:

- Configuration in `pyproject.toml` under `[tool.databricks-notebook-linter]`, with `select` and `ignore` keys. The nearest `pyproject.toml` at or above the working directory is used, which is the repository root under pre-commit
- `per-path` config entries, scoping rules to files matching a list of regexes via `select`, `extend-select`, and `ignore`. This is how a rule such as `DNL005` is enabled for one folder without enabling it repository-wide
- `--config PATH` to read a specific config file, and `--no-config` to ignore configuration entirely
- Unknown keys, unknown rule codes, empty `paths` lists, invalid regexes, and malformed TOML exit 2 rather than silently linting with the wrong rule set

### Changed

- Omitting `--select` selects the default-on rules rather than every rule, so an off-by-default rule such as `DNL005` must be requested explicitly. `check_file()` and `fix_file()` default to the same set. `DNL001`-`DNL004` are all on by default, so this does not change behavior for existing configurations
- `--fix` now also runs check-only rules, so a `DNL005` violation fails a fix-mode run. Previously `--fix` only reported what it changed
- Fix rules run in a fixed pipeline order (`DNL002` -> `DNL004` -> `DNL003` -> `DNL001`) because they interact: `DNL002` can empty a cell that `DNL004` then removes, `DNL004` clears interior empty cells before `DNL003` examines trailing ones, and `DNL001` runs last against the final cell structure. All rules remain idempotent
- Rules are declared once, in `ALL_RULES`, which carries each rule's metadata alongside its `check` and `fix` functions. List order is execution order, and a rule declaring no `fix` is check-only. `ALL_RULE_CODES`, `DEFAULT_RULE_CODES`, and `FIXABLE_RULE_CODES` derive from it
- Added `Cell`, `Rule`, and `Diagnostic` types, replacing ad hoc line handling

### Dependencies

- Requires `tomli` on Python < 3.11 for TOML parsing (`tomllib` is stdlib from 3.11). This package previously had no runtime dependencies

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
