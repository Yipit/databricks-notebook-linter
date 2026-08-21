# databricks-notebook-linter

A pre-commit hook that lints and fixes Databricks `.py`-format notebooks.

## Problem

Databricks exports notebooks as `.py` files with special comment markers. Magic commands like `%pip install` and `!nvidia-smi` appear as bare lines, which are invalid Python syntax. This breaks linters (ruff, flake8) and type checkers (ty, mypy) that try to parse these files. Notebooks also accumulate empty cells and formatting inconsistencies over time.

## Rules

| Code | Name | Description | Default |
|------|------|-------------|---------|
| DNL001 | `magic-prefix` | Prefix bare magic commands with `# MAGIC` | Enabled |
| DNL002 | `leading-blank-lines` | Strip leading blank lines from Python cells | Enabled |
| DNL003 | `trailing-empty-cells` | Remove trailing empty cells at end of notebook | Enabled |
| DNL004 | `empty-cells` | Remove empty cells with no content | Enabled |
| DNL005 | `no-widget-config` | Disallow reading config via `dbutils.widgets.get()` | Disabled |

DNL001-DNL004 are enabled by default. DNL005 is opt-in and must be requested
explicitly, either with `--select` or through a `per-path` config entry. Use
`--select` and `--ignore` to control which rules run, and
[configuration](#configuration) to scope a rule to part of the repository.

Every rule except DNL005 has an autofix. DNL005 is check-only: `--fix` reports
it and exits non-zero without modifying the file.

### DNL001: magic-prefix

Prefixes bare magic commands with `# MAGIC`, converting them to Python comments that Databricks still recognizes and executes:

```python
# Before
%pip install some-package==1.0.4

# After
# MAGIC %pip install some-package==1.0.4
```

Handles:

- Single-line magic commands (`%pip`, `%sql`, `%md`, `%sh`, `%fs`, `%run`, `%python`, `%r`, `%scala`)
- Shell bang commands (`!nvidia-smi`)
- `dbutils.library.restartPython()` calls
- Multiline continuations (`%pip install -U \`)
- Block-level magic -- if a `%pip` or `!` command is inside an `if`, `for`, `try`, or other block, the entire block is prefixed
- Nested blocks -- magic three levels deep prefixes all enclosing levels
- Compound blocks -- `if/elif/else`, `try/except/finally` treated as single units
- Mixed cells -- regular Python lines outside blocks are left untouched

### DNL002: leading-blank-lines

Strips all leading blank lines from Python cells. This removes the conventional blank line that Databricks inserts after `# COMMAND ----------` separators.

Scope: Python cells only. Cells containing `# MAGIC %md`, `# MAGIC %sql`, and other magic language cells are skipped (they may have intentional formatting).

This rule is compatible with ruff -- ruff's E302/E303 rules are fine with zero blank lines between a comment and a definition, it's the single blank line case that triggers a violation. By stripping all leading blanks, DNL002 avoids the ruff conflict rather than causing one.

### DNL003: trailing-empty-cells

Removes empty cells (and their preceding `# COMMAND ----------` separators) from the end of the notebook.

### DNL004: empty-cells

Removes empty cells with no content anywhere in the notebook (and their preceding separators). The header cell is never removed.

### DNL005: no-widget-config

Reports any read of notebook config from a widget:

```python
env = dbutils.widgets.get("env")                    # DNL005
table = dbutils.widgets.getArgument("table", "x")   # DNL005
```

`getArgument` is the legacy alias for the same read, so both are flagged.
Widget *declaration* and removal (`dbutils.widgets.text`, `dropdown`,
`removeAll`, ...) are not flagged -- the rule targets config reads, not the
widgets themselves.

Use this when config for a notebook must come from a known place -- a config
module, a job parameter contract, a settings table -- rather than being pulled
in ad hoc wherever a value happens to be needed. Because that expectation
usually applies to some notebooks and not others, DNL005 is off by default and
is most useful scoped to a path (see [configuration](#configuration)).

This rule has no autofix; there is no way to guess where the value should have
come from. It reports and fails the run in both check and `--fix` mode.

Detection is line-based, and ignores matches inside comments and single-line
string literals:

```python
# env = dbutils.widgets.get("env")             # not flagged, commented out
msg = "call dbutils.widgets.get for config"    # not flagged, string literal
# MAGIC env = dbutils.widgets.get("env")       # flagged: Databricks executes this
```

The known gap is a match inside a multi-line (triple-quoted) string, which is
reported as a violation.

### Pipeline order

When multiple rules are active, they run in this order: DNL002 -> DNL004 -> DNL003 -> DNL001. This matters because:

- DNL002 can turn a cell with only blank lines into an empty cell, which DNL004 then removes
- DNL004 removes interior empty cells before DNL003 checks trailing cells
- DNL001 runs last so it operates on the final cell structure

DNL005 has no autofix and so takes no part in the pipeline; it is checked
against the file as read from disk.

All rules are idempotent -- running the tool twice produces the same result.

## Configuration

Rules can be configured in `pyproject.toml` under
`[tool.databricks-notebook-linter]`. The nearest `pyproject.toml` at or above
the working directory is used, which is the repository root under pre-commit.

```toml
[tool.databricks-notebook-linter]
select = ["DNL001", "DNL002", "DNL003", "DNL004"]
ignore = []
```

| Key | Meaning |
|-----|---------|
| `select` | The rules that run. Replaces the defaults, so an off-by-default rule listed here is enabled. |
| `ignore` | Rules removed from the selected set. |
| `per-path` | A list of tables that adjust the rule set for matching files (below). |

`--select` and `--ignore` on the command line override the corresponding
config key. `--config PATH` reads a specific file; `--no-config` ignores
configuration entirely.

### Scoping rules to a path

Each `[[tool.databricks-notebook-linter.per-path]]` entry lists `paths`
regexes and the adjustment to apply to files matching any of them. This is how
DNL005 gets enabled for the notebooks whose config should be centralized,
without imposing it on the rest of the repository:

```toml
[tool.databricks-notebook-linter]
select = ["DNL001", "DNL002", "DNL003", "DNL004"]

# DNL001-DNL004 run everywhere; DNL005 only under notebooks/config/.
[[tool.databricks-notebook-linter.per-path]]
paths = ["^notebooks/config/"]
extend-select = ["DNL005"]
```

| Key | Meaning |
|-----|---------|
| `paths` | Required, non-empty. Python regexes, matched with `re.search`. |
| `extend-select` | Rules added to the active set for matching files. |
| `ignore` | Rules removed from the active set for matching files. |
| `select` | Replaces the active set for matching files outright. |

Patterns are matched against the file path relative to the directory holding
the config file, using forward slashes. Anchor with `^` to match from the
repository root; omit it to match anywhere in the path:

```toml
[[tool.databricks-notebook-linter.per-path]]
# Any notebook under a "config" directory, at any depth.
paths = ["(^|/)config/"]
extend-select = ["DNL005"]

[[tool.databricks-notebook-linter.per-path]]
# Vendored notebooks: check nothing but the magic prefix.
paths = ["^vendor/"]
select = ["DNL001"]
```

Entries are applied in file order, so a later entry can narrow an earlier one:

```toml
[[tool.databricks-notebook-linter.per-path]]
paths = ["^notebooks/"]
extend-select = ["DNL005"]

# ...except the legacy notebooks, which are not migrated yet.
[[tool.databricks-notebook-linter.per-path]]
paths = ["^notebooks/legacy/"]
ignore = ["DNL005"]
```

An unknown key, an unknown rule code, an empty `paths` list, or an invalid
regex is an error, and the tool exits 2 rather than silently linting with the
wrong rule set.

## Usage

### As a pre-commit hook

Add to your `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/Yipit/databricks-notebook-linter
    rev: v0.3.0
    hooks:
      - id: fix-databricks-magic
        args: [--fix]
```

This auto-fixes files on commit. To check without modifying files, omit `args`:

```yaml
hooks:
  - id: fix-databricks-magic
```

#### Selecting rules

```yaml
hooks:
  # Only magic prefix and leading blank lines
  - id: fix-databricks-magic
    args: [--fix, --select, "DNL001,DNL002"]

  # All rules except empty cell removal
  - id: fix-databricks-magic
    args: [--fix, --ignore, "DNL004"]

  # Defaults plus DNL005 everywhere
  - id: fix-databricks-magic
    args: [--fix, --select, "DNL001,DNL002,DNL003,DNL004,DNL005"]
```

To scope DNL005 to part of the repository instead, leave it out of `args` and
configure `per-path` in `pyproject.toml` -- see
[configuration](#configuration). The hook runs from the repository root, so
the config file is picked up automatically.

### As a CLI tool

```bash
pip install databricks-notebook-linter

# Check mode (default): report issues, exit 1 if any found
fix-databricks-magic path/to/notebook.py

# Fix mode: rewrite files in place, exit 1 if any changed
fix-databricks-magic --fix path/to/notebook.py

# Select specific rules
fix-databricks-magic --fix --select DNL001,DNL002 path/to/notebook.py

# Ignore specific rules
fix-databricks-magic --fix --ignore DNL003,DNL004 path/to/notebook.py

# Read a specific config file, or ignore configuration entirely
fix-databricks-magic --config path/to/pyproject.toml path/to/notebook.py
fix-databricks-magic --no-config path/to/notebook.py

# List available rules, with their default state
fix-databricks-magic --list-rules
```

Exit codes: `0` clean, `1` issues found (or files changed under `--fix`), `2`
bad rule codes or bad configuration.

### Check mode output

```
notebook.py:5: [DNL001] bare magic command '%pip install foo' needs '# MAGIC' prefix
notebook.py:10: [DNL001] line in block containing magic needs '# MAGIC' prefix
notebook.py:3: [DNL002] leading blank line in Python cell
notebook.py:15: [DNL004] empty cell
notebook.py:8: [DNL005] dbutils.widgets.get() reads notebook config from a widget; source config explicitly instead
```

### Fix mode output

```
Fixed [DNL001, DNL002]: notebook.py
```

Check-only rules are still reported in fix mode, and still fail the run:

```
Fixed [DNL001]: notebook.py
notebook.py:8: [DNL005] dbutils.widgets.get() reads notebook config from a widget; source config explicitly instead
```

## Examples

### Bare magic commands

```python
# Before                              # After
%pip install transformers             # MAGIC %pip install transformers
!nvidia-smi                           # MAGIC !nvidia-smi
%sql SELECT * FROM my_table           # MAGIC %sql SELECT * FROM my_table
dbutils.library.restartPython()       # MAGIC dbutils.library.restartPython()
```

### Multiline continuations

```python
# Before
%pip install -U \
  transformers==4.57.6 \
  datasets==4.5.0 \
  peft==0.18.1

# After
# MAGIC %pip install -U \
# MAGIC   transformers==4.57.6 \
# MAGIC   datasets==4.5.0 \
# MAGIC   peft==0.18.1
```

### Conditional installs

```python
# Before
if COMPUTE_ENV == "serverless":
    %pip install -U hf_transfer

# After
# MAGIC if COMPUTE_ENV == "serverless":
# MAGIC     %pip install -U hf_transfer
```

### Compound blocks (if/else, try/except)

```python
# Before
try:
    import bitsandbytes
except:
    %pip install bitsandbytes

# After
# MAGIC try:
# MAGIC     import bitsandbytes
# MAGIC except:
# MAGIC     %pip install bitsandbytes
```

### Leading blank lines (DNL002)

```python
# Before                              # After
# COMMAND ----------                  # COMMAND ----------
                                      import math
import math
```

### Empty cells (DNL004) and trailing empty cells (DNL003)

```python
# Before                              # After
# COMMAND ----------                  # COMMAND ----------
import math                           import math
                                      # COMMAND ----------
# COMMAND ----------                  x = 1
                                      
# COMMAND ----------
x = 1

# COMMAND ----------

```

## Development

```bash
make setup    # install dependencies
make test     # run tests (with 100% branch coverage enforcement)
make lint     # run ruff
make format   # auto-format
```

### Releasing

```bash
# All at once: tag, publish to PyPI, push
make release VERSION=x.y.z

# Or in two steps:
make tag-release VERSION=x.y.z    # bump, commit, tag (local only)
make push-release VERSION=x.y.z   # build, publish to PyPI, push commit + tag
```

`tag-release` validates a clean working tree on `main`, runs tests and lint, bumps the version in `pyproject.toml` and `README.md`, commits, and creates an annotated tag. `push-release` builds, publishes to PyPI, then pushes. Nothing reaches the remote until the PyPI publish succeeds.

## Contributing

PRs are welcome. Run `make test` and `make lint` before submitting.

## License

MIT

---

**NOTE:** This codebase dictated but not read.*

\* Claude wrote most of this at my prompting. I have reviewed the logic and tests, but I am still responsible for errors in the codebase, notwithstanding the original meaning of the introductory phrase.
