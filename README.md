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
- Multiline continuations (`%pip install -U \`)
- Conditional magic (`if COND: %pip install foo` -- prefixes both the `if` and the `%pip`)
- Mixed cells (leaves regular Python lines alone, only prefixes magic lines)

The tool is idempotent -- running it twice produces the same result.

## Usage

### As a pre-commit hook

Add to your `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/yipitdata/databricks-notebook-linter
    rev: v0.1.0
    hooks:
      - id: fix-databricks-magic
```

### As a CLI tool

```bash
pip install databricks-notebook-linter
fix-databricks-magic path/to/notebook.py
```

### Standalone

```bash
python -m databricks_notebook_linter.fix_magic path/to/notebook.py
```

## How it works

1. Checks if the file starts with `# Databricks notebook source` -- skips non-notebook files
2. Scans for lines starting with magic prefixes (`%pip`, `!`, etc.)
3. Prefixes those lines with `# MAGIC `
4. For indented magic commands, also prefixes the enclosing block statement (`if`, `for`, etc.)
5. Follows backslash continuations to prefix all continuation lines

The hook returns exit code 1 when it modifies files (standard pre-commit behavior to signal changes), and 0 when no changes are needed.

## Development

```bash
uv sync
uv run pytest
```

## License

MIT
