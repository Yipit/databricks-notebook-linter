"""Fix bare magic commands in Databricks .py-format notebooks.

Databricks .py-format notebooks use `# MAGIC` to prefix non-Python lines (like %pip,
%sql, %md, !shell commands). When bare magic commands appear in a cell, tools like
ruff and ty can't parse the file because they're invalid Python syntax. Prefixing
with `# MAGIC` makes them Python comments while Databricks still executes them.

Handles:
- Single-line: %pip install foo -> # MAGIC %pip install foo
- Shell bangs: !nvidia-smi -> # MAGIC !nvidia-smi
- Multiline: %pip install -U \\ (and all continuation lines)
- Conditional: if COND: \\n    %pip install foo (prefixes the entire block)
- Nested blocks: outer and inner blocks containing magic are fully prefixed
- Compound blocks: if/else, try/except/finally treated as single units
"""

from __future__ import annotations

import argparse
import sys

DATABRICKS_HEADER = "# Databricks notebook source"
CELL_SEPARATOR = "# COMMAND ----------"

MAGIC_PREFIXES = (
    "%pip",
    "%sh",
    "%fs",
    "%run",
    "%sql",
    "%python",
    "%r",
    "%scala",
    "%md",
    "!",
)

COMPOUND_CONTINUATIONS = ("elif ", "else:", "except:", "except ", "finally:")


def is_magic_line(stripped: str) -> bool:
    return any(stripped.startswith(p) for p in MAGIC_PREFIXES)


def is_already_magic(line: str) -> bool:
    return line.lstrip().startswith("# MAGIC")


def is_continuation(line: str) -> bool:
    return line.rstrip().endswith("\\")


def get_indent(line: str) -> int:
    return len(line) - len(line.lstrip())


def _find_enclosing_block_start(cell_lines: list[str], idx: int) -> int:
    """Walk backwards from idx to find the top-level (indent 0) block starter."""
    current_indent = get_indent(cell_lines[idx])
    pos = idx

    while current_indent > 0:
        found = False
        for j in range(pos - 1, -1, -1):
            if not cell_lines[j].strip():
                continue
            if get_indent(cell_lines[j]) < current_indent:
                pos = j
                current_indent = get_indent(cell_lines[j])
                found = True
                break
        if not found:
            break

    # If we landed on a compound continuation (else, elif, except, finally),
    # walk backwards to find the true block opener at the same indent level.
    stripped = cell_lines[pos].strip()
    while any(stripped.startswith(c) for c in COMPOUND_CONTINUATIONS):
        for j in range(pos - 1, -1, -1):
            if not cell_lines[j].strip():
                continue
            if get_indent(cell_lines[j]) <= current_indent:
                pos = j
                stripped = cell_lines[pos].strip()
                break
        else:
            break

    return pos


def _find_compound_block_end(cell_lines: list[str], block_start: int) -> int:
    """Find the last line of the compound block starting at block_start."""
    block_indent = get_indent(cell_lines[block_start])
    end = block_start

    for j in range(block_start + 1, len(cell_lines)):
        stripped = cell_lines[j].strip()
        if not stripped:
            continue
        j_indent = get_indent(cell_lines[j])
        if j_indent > block_indent:
            end = j
        elif j_indent == block_indent and any(
            stripped.startswith(c) for c in COMPOUND_CONTINUATIONS
        ):
            end = j
        else:
            break

    return end


def _find_lines_needing_magic(
    cell_lines: list[str],
) -> tuple[set[int], set[int]]:
    """Analyze a cell to find lines needing ``# MAGIC`` prefix.

    Returns (needs_magic, block_lines) where both are sets of local cell
    indices.  *block_lines* is the subset whose original indentation must be
    preserved in the prefixed output.
    """
    needs_magic: set[int] = set()
    block_lines: set[int] = set()

    i = 0
    while i < len(cell_lines):
        line = cell_lines[i]
        stripped = line.lstrip()

        if is_already_magic(line) or not is_magic_line(stripped):
            i += 1
            continue

        indent = get_indent(line)

        if indent == 0:
            needs_magic.add(i)
            while is_continuation(cell_lines[i]) and i + 1 < len(cell_lines):
                i += 1
                needs_magic.add(i)
        else:
            block_start = _find_enclosing_block_start(cell_lines, i)
            block_end = _find_compound_block_end(cell_lines, block_start)
            for j in range(block_start, block_end + 1):
                if cell_lines[j].strip():
                    needs_magic.add(j)
                    block_lines.add(j)

        i += 1

    return needs_magic, block_lines


def _split_into_cells(lines: list[str]) -> list[tuple[int, list[str]]]:
    """Split notebook lines into cells on ``# COMMAND ----------`` boundaries."""
    cells: list[tuple[int, list[str]]] = []
    current_start = 0
    current: list[str] = []

    for i, line in enumerate(lines):
        if CELL_SEPARATOR in line:
            if current:
                cells.append((current_start, current))
                current = []
            cells.append((i, [line]))
            current_start = i + 1
        else:
            if not current:
                current_start = i
            current.append(line)

    if current:
        cells.append((current_start, current))

    return cells


def _analyze_file(
    filepath: str,
) -> tuple[str, list[str], set[int], set[int]] | None:
    """Read and analyze a file for bare magic commands.

    Returns ``(original, lines, needs_magic, block_lines)`` or ``None`` if the
    file is not a Databricks notebook.
    """
    with open(filepath) as f:
        original = f.read()

    lines = original.splitlines(keepends=True)

    if not lines or DATABRICKS_HEADER not in lines[0]:
        return None

    global_needs_magic: set[int] = set()
    global_block_lines: set[int] = set()

    for cell_start, cell_lines in _split_into_cells(lines):
        needs_magic, block_lines = _find_lines_needing_magic(cell_lines)
        for local_idx in needs_magic:
            global_needs_magic.add(cell_start + local_idx)
        for local_idx in block_lines:
            global_block_lines.add(cell_start + local_idx)

    return original, lines, global_needs_magic, global_block_lines


def check_file(filepath: str) -> list[str]:
    """Return diagnostic strings for bare magic commands in *filepath*."""
    result = _analyze_file(filepath)
    if result is None:
        return []

    _original, lines, global_needs_magic, _global_block_lines = result
    if not global_needs_magic:
        return []

    diagnostics = []
    for i in sorted(global_needs_magic):
        stripped = lines[i].strip()
        if is_magic_line(stripped):
            diagnostics.append(
                f"{filepath}:{i + 1}: bare magic command '{stripped}' needs '# MAGIC' prefix"
            )
        else:
            diagnostics.append(
                f"{filepath}:{i + 1}: line in block containing magic needs '# MAGIC' prefix"
            )

    return diagnostics


def fix_file(filepath: str) -> bool:
    result = _analyze_file(filepath)
    if result is None:
        return False

    original, lines, global_needs_magic, global_block_lines = result
    if not global_needs_magic:
        return False

    new_lines = []
    for i, line in enumerate(lines):
        if i in global_needs_magic and not is_already_magic(line):
            if i in global_block_lines:
                new_lines.append("# MAGIC " + line)
            else:
                new_lines.append("# MAGIC " + line.lstrip())
        else:
            new_lines.append(line)

    new_content = "".join(new_lines)
    if new_content == original:
        return False

    with open(filepath, "w") as f:
        f.write(new_content)

    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fix bare magic commands in Databricks .py-format notebooks",
    )
    parser.add_argument("files", nargs="*", help="Files to check")
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Fix files in place (default: check only)",
    )
    args = parser.parse_args()

    if args.fix:
        changed_files = []
        for filepath in args.files:
            if filepath.endswith(".py") and fix_file(filepath):
                changed_files.append(filepath)

        if changed_files:
            for f in changed_files:
                print(f"Fixed magic commands in: {f}")
            return 1

        return 0

    all_diagnostics: list[str] = []
    for filepath in args.files:
        if filepath.endswith(".py"):
            all_diagnostics.extend(check_file(filepath))

    if all_diagnostics:
        for d in all_diagnostics:
            print(d)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
