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

All rules are enabled by default. Use `--select` and `--ignore` to control which rules run.

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

### Pipeline order

When multiple rules are active, they run in this order: DNL002 -> DNL004 -> DNL003 -> DNL001. This matters because:

- DNL002 can turn a cell with only blank lines into an empty cell, which DNL004 then removes
- DNL004 removes interior empty cells before DNL003 checks trailing cells
- DNL001 runs last so it operates on the final cell structure

All rules are idempotent -- running the tool twice produces the same result.

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
```

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

# List available rules
fix-databricks-magic --list-rules
```

### Check mode output

```
notebook.py:5: [DNL001] bare magic command '%pip install foo' needs '# MAGIC' prefix
notebook.py:10: [DNL001] line in block containing magic needs '# MAGIC' prefix
notebook.py:3: [DNL002] leading blank line in Python cell
notebook.py:15: [DNL004] empty cell
```

### Fix mode output

```
Fixed [DNL001, DNL002]: notebook.py
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
