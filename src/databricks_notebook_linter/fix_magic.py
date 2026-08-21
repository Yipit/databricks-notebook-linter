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
import re
import sys
from typing import NamedTuple

from databricks_notebook_linter.config import Config, ConfigError, load_config

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

MAGIC_CONTAINS = ("dbutils.library.restartPython()",)

MAGIC_COMMENT_PREFIX = "# MAGIC "

# Single-line string literals, stripped before scanning a line for code so that
# a method name mentioned inside a string is not mistaken for a call.
STRING_LITERAL_PATTERN = re.compile(
    r"'''.*?'''" r'|""".*?"""' r"|'[^'\n]*'" r'|"[^"\n]*"'
)

WIDGET_READ_PATTERN = re.compile(r"\bdbutils\s*\.\s*widgets\s*\.\s*(getArgument|get)\b")

COMPOUND_CONTINUATIONS = ("elif ", "else:", "except:", "except ", "finally:")


class Cell(NamedTuple):
    start: int
    lines: list[str]
    is_separator: bool


class Rule(NamedTuple):
    code: str
    name: str
    description: str
    default: bool = True
    fixable: bool = True


class Diagnostic(NamedTuple):
    filepath: str
    line: int
    code: str
    message: str

    def __str__(self) -> str:
        return f"{self.filepath}:{self.line}: [{self.code}] {self.message}"


ALL_RULES = [
    Rule("DNL001", "magic-prefix", "Prefix bare magic commands with # MAGIC"),
    Rule(
        "DNL002", "leading-blank-lines", "Strip leading blank lines from Python cells"
    ),
    Rule(
        "DNL003",
        "trailing-empty-cells",
        "Remove trailing empty cells at end of notebook",
    ),
    Rule("DNL004", "empty-cells", "Remove empty cells with no content"),
    Rule(
        "DNL005",
        "no-widget-config",
        "Disallow reading config via dbutils.widgets.get()/getArgument()",
        default=False,
        fixable=False,
    ),
]
ALL_RULE_CODES = {r.code for r in ALL_RULES}
DEFAULT_RULE_CODES = {r.code for r in ALL_RULES if r.default}
FIXABLE_RULE_CODES = {r.code for r in ALL_RULES if r.fixable}


def resolve_rules(
    select: list[str] | None = None,
    ignore: list[str] | None = None,
) -> set[str]:
    """Resolve the active rule codes.

    Without *select*, the default-on rules run. Rules that are off by default
    (see ``Rule.default``) must be requested explicitly.
    """
    unknown = set()
    if select:
        unknown |= set(select) - ALL_RULE_CODES
    if ignore:
        unknown |= set(ignore) - ALL_RULE_CODES
    if unknown:
        raise ValueError(f"Unknown rule codes: {', '.join(sorted(unknown))}")

    if select:
        active = set(select)
    else:
        active = set(DEFAULT_RULE_CODES)

    if ignore:
        active -= set(ignore)

    return active


def is_magic_line(stripped: str) -> bool:
    if stripped.startswith("!"):
        return not stripped.startswith("!=")
    return any(stripped.startswith(p) for p in MAGIC_PREFIXES) or any(
        c in stripped for c in MAGIC_CONTAINS
    )


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


def _split_into_cells(lines: list[str]) -> list[Cell]:
    """Split notebook lines into cells on ``# COMMAND ----------`` boundaries."""
    cells: list[Cell] = []
    current_start = 0
    current: list[str] = []

    for i, line in enumerate(lines):
        if CELL_SEPARATOR in line:
            if current:
                cells.append(Cell(current_start, current, is_separator=False))
                current = []
            cells.append(Cell(i, [line], is_separator=True))
            current_start = i + 1
        else:
            if not current:
                current_start = i
            current.append(line)

    if current:
        cells.append(Cell(current_start, current, is_separator=False))

    return cells


def is_python_cell(cell: Cell) -> bool:
    if cell.is_separator:
        return False
    for line in cell.lines:
        stripped = line.strip()
        if stripped:
            return not stripped.startswith("# MAGIC %")
    return False


def is_empty_cell(cell: Cell) -> bool:
    if cell.is_separator:
        return False
    return all(line.strip() == "" for line in cell.lines)


def _check_leading_blank_lines(
    cells: list[Cell],
    filepath: str,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for cell in cells:
        if not is_python_cell(cell):
            continue
        if cell.lines and cell.lines[0].strip() == "":
            diagnostics.append(
                Diagnostic(
                    filepath,
                    cell.start + 1,
                    "DNL002",
                    "leading blank line in Python cell",
                ),
            )
    return diagnostics


def _fix_leading_blank_lines(cells: list[Cell]) -> tuple[list[Cell], bool]:
    changed = False
    new_cells: list[Cell] = []
    for cell in cells:
        if not is_python_cell(cell):
            new_cells.append(cell)
            continue
        first_non_blank = next(
            (i for i, line in enumerate(cell.lines) if line.strip() != ""),
            0,
        )
        if first_non_blank > 0:
            changed = True
            new_cells.append(
                Cell(
                    cell.start + first_non_blank,
                    cell.lines[first_non_blank:],
                    cell.is_separator,
                ),
            )
        else:
            new_cells.append(cell)
    return new_cells, changed


def _check_empty_cells(cells: list[Cell], filepath: str) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for i, cell in enumerate(cells):
        if i == 0:
            continue
        if is_empty_cell(cell):
            diagnostics.append(
                Diagnostic(filepath, cell.start + 1, "DNL004", "empty cell"),
            )
    return diagnostics


def _fix_empty_cells(cells: list[Cell]) -> tuple[list[Cell], bool]:
    changed = False
    new_cells: list[Cell] = []
    i = 0
    while i < len(cells):
        cell = cells[i]
        if i > 0 and is_empty_cell(cell):
            changed = True
            if new_cells and new_cells[-1].is_separator:  # pragma: no branch
                new_cells.pop()
            i += 1
            continue
        new_cells.append(cell)
        i += 1
    return new_cells, changed


def _check_trailing_empty_cells(cells: list[Cell], filepath: str) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    i = len(cells) - 1
    while i > 0:
        cell = cells[i]
        if is_empty_cell(cell):
            diagnostics.append(
                Diagnostic(filepath, cell.start + 1, "DNL003", "trailing empty cell"),
            )
            i -= 1
            if i > 0 and cells[i].is_separator:  # pragma: no branch
                i -= 1
        else:
            break
    return diagnostics


def _fix_trailing_empty_cells(cells: list[Cell]) -> tuple[list[Cell], bool]:
    original_len = len(cells)
    while len(cells) > 1 and is_empty_cell(cells[-1]):
        cells = cells[:-1]
        if cells and cells[-1].is_separator:  # pragma: no branch
            cells = cells[:-1]
    return cells, len(cells) != original_len


def _read_notebook(filepath: str) -> tuple[str, list[Cell]] | None:
    with open(filepath) as f:
        original = f.read()

    lines = original.splitlines(keepends=True)

    if not lines or DATABRICKS_HEADER not in lines[0]:
        return None

    return original, _split_into_cells(lines)


def _check_magic_prefixes(cells: list[Cell], filepath: str) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for cell in cells:
        if cell.is_separator:
            continue
        needs_magic, _block_lines = _find_lines_needing_magic(cell.lines)
        for local_idx in sorted(needs_magic):
            stripped = cell.lines[local_idx].strip()
            if is_magic_line(stripped):
                msg = f"bare magic command '{stripped}' needs '# MAGIC' prefix"
            else:
                msg = "line in block containing magic needs '# MAGIC' prefix"
            diagnostics.append(
                Diagnostic(filepath, cell.start + local_idx + 1, "DNL001", msg)
            )
    return diagnostics


def _fix_magic_prefixes(cells: list[Cell]) -> tuple[list[Cell], bool]:
    changed = False
    new_cells: list[Cell] = []
    for cell in cells:
        if cell.is_separator:
            new_cells.append(cell)
            continue
        needs_magic, block_lines = _find_lines_needing_magic(cell.lines)
        if not needs_magic:
            new_cells.append(cell)
            continue
        changed = True
        new_lines = []
        for i, line in enumerate(cell.lines):
            if i in needs_magic and not is_already_magic(line):
                if i in block_lines:
                    new_lines.append("# MAGIC " + line)
                else:
                    new_lines.append("# MAGIC " + line.lstrip())
            else:
                new_lines.append(line)
        new_cells.append(Cell(cell.start, new_lines, cell.is_separator))
    return new_cells, changed


def _code_portion(line: str) -> str:
    """Return the executable part of a line.

    Drops a ``# MAGIC`` prefix (Databricks still executes those lines), string
    literals, and trailing comments, so only real code is scanned.
    """
    stripped = line.lstrip()
    if stripped.startswith(MAGIC_COMMENT_PREFIX):
        stripped = stripped[len(MAGIC_COMMENT_PREFIX) :]
    return STRING_LITERAL_PATTERN.sub("", stripped).split("#", 1)[0]


def _check_widget_config(cells: list[Cell], filepath: str) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for cell in cells:
        if cell.is_separator:
            continue
        for local_idx, line in enumerate(cell.lines):
            match = WIDGET_READ_PATTERN.search(_code_portion(line))
            if match is None:
                continue
            diagnostics.append(
                Diagnostic(
                    filepath,
                    cell.start + local_idx + 1,
                    "DNL005",
                    f"dbutils.widgets.{match.group(1)}() reads notebook config from "
                    "a widget; source config explicitly instead",
                ),
            )
    return diagnostics


def _cells_to_text(cells: list[Cell]) -> str:
    return "".join(line for cell in cells for line in cell.lines)


def check_file(
    filepath: str,
    active_rules: set[str] | None = None,
) -> list[Diagnostic]:
    result = _read_notebook(filepath)
    if result is None:
        return []

    _original, cells = result
    if active_rules is None:
        active_rules = DEFAULT_RULE_CODES

    diagnostics: list[Diagnostic] = []
    if "DNL002" in active_rules:
        diagnostics.extend(_check_leading_blank_lines(cells, filepath))
    if "DNL004" in active_rules:
        diagnostics.extend(_check_empty_cells(cells, filepath))
    if "DNL003" in active_rules:
        diagnostics.extend(_check_trailing_empty_cells(cells, filepath))
    if "DNL001" in active_rules:
        diagnostics.extend(_check_magic_prefixes(cells, filepath))
    if "DNL005" in active_rules:
        diagnostics.extend(_check_widget_config(cells, filepath))
    return diagnostics


def fix_file(
    filepath: str,
    active_rules: set[str] | None = None,
) -> set[str]:
    result = _read_notebook(filepath)
    if result is None:
        return set()

    original, cells = result
    if active_rules is None:
        active_rules = DEFAULT_RULE_CODES

    applied: set[str] = set()

    # Pipeline order: DNL002 -> DNL004 -> DNL003 -> DNL001
    if "DNL002" in active_rules:
        cells, changed = _fix_leading_blank_lines(cells)
        if changed:
            applied.add("DNL002")

    if "DNL004" in active_rules:
        cells, changed = _fix_empty_cells(cells)
        if changed:
            applied.add("DNL004")

    if "DNL003" in active_rules:
        cells, changed = _fix_trailing_empty_cells(cells)
        if changed:
            applied.add("DNL003")

    if "DNL001" in active_rules:
        cells, changed = _fix_magic_prefixes(cells)
        if changed:
            applied.add("DNL001")

    if not applied:
        return set()

    new_content = _cells_to_text(cells)
    if new_content == original:  # pragma: no cover
        return set()

    with open(filepath, "w") as f:
        f.write(new_content)

    return applied


def _rules_for_path(
    filepath: str,
    base_rules: set[str],
    config: Config | None,
) -> set[str]:
    if config is None:
        return base_rules
    return config.rules_for(filepath, base_rules)


def _split_codes(value: str | None) -> list[str] | None:
    return value.split(",") if value else None


def _resolve_base_rules(args: argparse.Namespace) -> tuple[set[str], Config | None]:
    """Load configuration and resolve the repository-wide rule set."""
    config = None if args.no_config else load_config(args.config)

    if config is not None:
        unknown = config.referenced_codes() - ALL_RULE_CODES
        if unknown:
            raise ConfigError(
                f"{config.path}: unknown rule codes: {', '.join(sorted(unknown))}"
            )

    file_select = list(config.select) if config and config.select else None
    file_ignore = list(config.ignore) if config and config.ignore else None
    select = _split_codes(args.select) or file_select
    ignore = _split_codes(args.ignore) or file_ignore

    return resolve_rules(select, ignore), config


def _notebook_paths(files: list[str]) -> list[str]:
    return [f for f in files if f.endswith(".py")]


def _run_fix(
    files: list[str],
    base_rules: set[str],
    config: Config | None,
) -> int:
    changed_files: list[tuple[str, set[str]]] = []
    diagnostics: list[Diagnostic] = []

    for filepath in _notebook_paths(files):
        rules = _rules_for_path(filepath, base_rules, config)
        applied = fix_file(filepath, rules)
        if applied:
            changed_files.append((filepath, applied))
        # Rules with no autofix still have to fail the run.
        check_only = rules - FIXABLE_RULE_CODES
        if check_only:
            diagnostics.extend(check_file(filepath, check_only))

    for filepath, applied in changed_files:
        print(f"Fixed [{', '.join(sorted(applied))}]: {filepath}")
    for diagnostic in diagnostics:
        print(diagnostic)

    return 1 if changed_files or diagnostics else 0


def _run_check(
    files: list[str],
    base_rules: set[str],
    config: Config | None,
) -> int:
    diagnostics: list[Diagnostic] = []
    for filepath in _notebook_paths(files):
        rules = _rules_for_path(filepath, base_rules, config)
        diagnostics.extend(check_file(filepath, rules))

    if diagnostics:
        for diagnostic in diagnostics:
            print(diagnostic)
        return 1

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Lint and fix Databricks .py-format notebooks",
    )
    parser.add_argument("files", nargs="*", help="Files to check")
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Fix files in place (default: check only)",
    )
    parser.add_argument(
        "--select",
        type=str,
        default=None,
        help="Comma-separated rule codes to enable (e.g. DNL001,DNL002)",
    )
    parser.add_argument(
        "--ignore",
        type=str,
        default=None,
        help="Comma-separated rule codes to disable (e.g. DNL003,DNL004)",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to a TOML config file (default: nearest pyproject.toml)",
    )
    parser.add_argument(
        "--no-config",
        action="store_true",
        help="Ignore any pyproject.toml configuration",
    )
    parser.add_argument(
        "--list-rules",
        action="store_true",
        help="Print available rules and exit",
    )
    args = parser.parse_args()

    if args.list_rules:
        for rule in ALL_RULES:
            state = "on" if rule.default else "off"
            print(f"{rule.code}  {rule.name:20s}  {state:3s}  {rule.description}")
        return 0

    try:
        base_rules, config = _resolve_base_rules(args)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2

    if args.fix:
        return _run_fix(args.files, base_rules, config)

    return _run_check(args.files, base_rules, config)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
