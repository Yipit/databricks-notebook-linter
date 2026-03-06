# databricks-notebook-linter

A pre-commit hook that fixes bare magic commands in Databricks `.py`-format notebooks.

## Problem

Databricks exports notebooks as `.py` files with special comment markers. Magic commands like `%pip install` and `!nvidia-smi` appear as bare lines, which are invalid Python syntax. This breaks linters (ruff, flake8) and type checkers (ty, mypy) that try to parse these files.

## Solution

This tool prefixes bare magic commands with `# MAGIC`, converting them to Python comments that Databricks still recognizes and executes:

```python
# Before
%pip install some-package==1.0.4

# After
# MAGIC %pip install some-package==1.0.4
```

It handles:

- Single-line magic commands (`%pip`, `%sql`, `%md`, `%sh`, `%fs`, `%run`, `%python`, `%r`, `%scala`)
- Shell bang commands (`!nvidia-smi`)
- `dbutils.library.restartPython()` calls
- Multiline continuations (`%pip install -U \`)
- Block-level magic -- if a `%pip` or `!` command is inside an `if`, `for`, `try`, or other block, the entire block is prefixed
- Nested blocks -- magic three levels deep prefixes all enclosing levels
- Compound blocks -- `if/elif/else`, `try/except/finally` treated as single units
- Mixed cells -- regular Python lines outside blocks are left untouched

The tool is idempotent -- running it twice produces the same result.

## Usage

### As a pre-commit hook

Add to your `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/Yipit/databricks-notebook-linter
    rev: v0.2.0
    hooks:
      - id: fix-databricks-magic
        args: [--fix]
```

This auto-fixes files on commit. To check without modifying files, omit `args`:

```yaml
hooks:
  - id: fix-databricks-magic
```

### As a CLI tool

```bash
pip install databricks-notebook-linter

# Check mode (default): report issues, exit 1 if any found
fix-databricks-magic path/to/notebook.py

# Fix mode: rewrite files in place, exit 1 if any changed
fix-databricks-magic --fix path/to/notebook.py
```

### Check mode output

```
notebook.py:5: bare magic command '%pip install foo' needs '# MAGIC' prefix
notebook.py:10: line in block containing magic needs '# MAGIC' prefix
```

## How it works

1. Checks if the file starts with `# Databricks notebook source` -- skips non-notebook files
2. Splits the file into cells on `# COMMAND ----------` boundaries
3. For each cell, scans for bare magic lines (lines starting with `%pip`, `!`, etc.)
4. If magic is at the top level, marks just that line (and any continuation lines)
5. If magic is indented inside a block, walks backwards to find the top-level enclosing block and forwards to find the end of compound blocks (`else`, `except`, `finally`), then marks every line in the block
6. Prefixes all marked lines with `# MAGIC`, preserving relative indentation for block-internal lines

## Examples

### Bare magic commands

The simplest case -- a magic command on its own line gets prefixed:

```python
# Before                              # After
%pip install transformers             # MAGIC %pip install transformers
!nvidia-smi                           # MAGIC !nvidia-smi
%sql SELECT * FROM my_table           # MAGIC %sql SELECT * FROM my_table
dbutils.library.restartPython()       # MAGIC dbutils.library.restartPython()
```

### Multiline continuations

When a `%pip install` spans multiple lines with `\`, all continuation lines are prefixed:

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

When a magic command is inside a block, the entire block is prefixed -- the `if` statement itself and all lines inside it. This is necessary because Databricks needs the whole block to be in magic context:

```python
# Before
if COMPUTE_ENV == "serverless":
    %pip install -U hf_transfer

# After
# MAGIC if COMPUTE_ENV == "serverless":
# MAGIC     %pip install -U hf_transfer
```

### Compound blocks (if/else, try/except)

The tool treats `if/elif/else` and `try/except/finally` as single units. If magic appears in any branch, the entire compound block is prefixed:

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

This also works when magic only appears in a secondary branch like `else` or `except` -- the entire block from the opening `if` or `try` is prefixed.

### Mixed cells

When a cell contains both regular Python and magic commands, only the magic lines (and their enclosing blocks) are prefixed. Regular Python is left untouched:

```python
# Before
INDEX_URL = dbutils.secrets.get("pip", "index_url")
%pip install some-package --index-url $INDEX_URL
result = process_data()

# After
INDEX_URL = dbutils.secrets.get("pip", "index_url")
# MAGIC %pip install some-package --index-url $INDEX_URL
result = process_data()
```

### What is NOT treated as magic

The tool avoids false positives. These patterns are left alone:

```python
# Not touched -- % inside a string
msg = "%pip is a magic command"

# Not touched -- modulo operator
result = 10 % 3

# Not touched -- % in a comment
# Use %pip to install packages

# Not touched -- if block without any magic in its body
if version == "1.0":
    print("correct")
```

### Non-notebook files

Files that don't start with `# Databricks notebook source` are skipped entirely, and non-`.py` files are ignored by the CLI and pre-commit hook.

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

## License

MIT
