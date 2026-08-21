"""Load linter configuration from ``pyproject.toml``.

Configuration lives under ``[tool.databricks-notebook-linter]``. The top-level
``select``/``ignore`` keys set the rules that run everywhere; ``per-path``
entries adjust that set for files whose path matches a regex, which is how a
rule can be scoped to one folder without enabling it repository-wide::

    [tool.databricks-notebook-linter]
    select = ["DNL001", "DNL002", "DNL003", "DNL004"]

    [[tool.databricks-notebook-linter.per-path]]
    paths = ["^notebooks/config/"]
    extend-select = ["DNL005"]

Within a ``per-path`` entry, ``select`` replaces the active rule set, while
``extend-select`` and ``ignore`` add to and subtract from it. Entries are
applied in file order, so a later entry can narrow an earlier one.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any, NamedTuple

if sys.version_info >= (3, 11):  # pragma: no cover
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib

TOOL_SECTION = "databricks-notebook-linter"

TOP_LEVEL_KEYS = frozenset({"select", "ignore", "per-path"})
PER_PATH_KEYS = frozenset({"paths", "select", "extend-select", "ignore"})


class ConfigError(ValueError):
    """Raised when a configuration file is missing or malformed."""


class PathRules(NamedTuple):
    """Rule adjustments applied to files matching any of ``patterns``."""

    patterns: tuple[re.Pattern[str], ...]
    select: tuple[str, ...] | None
    extend_select: tuple[str, ...]
    ignore: tuple[str, ...]

    def matches(self, target: str) -> bool:
        return any(pattern.search(target) for pattern in self.patterns)


class Config(NamedTuple):
    path: Path
    root: Path
    select: tuple[str, ...] | None
    ignore: tuple[str, ...] | None
    per_path: tuple[PathRules, ...]

    def referenced_codes(self) -> set[str]:
        """Every rule code mentioned anywhere in the file, for validation."""
        codes: set[str] = set(self.select or ()) | set(self.ignore or ())
        for entry in self.per_path:
            codes |= set(entry.select or ())
            codes |= set(entry.extend_select)
            codes |= set(entry.ignore)
        return codes

    def rules_for(self, filepath: str, base: set[str]) -> set[str]:
        """Resolve the active rules for ``filepath`` from the ``base`` set."""
        if not self.per_path:
            return set(base)

        target = self._match_target(filepath)
        active = set(base)
        for entry in self.per_path:
            if not entry.matches(target):
                continue
            if entry.select is not None:
                active = set(entry.select)
            active |= set(entry.extend_select)
            active -= set(entry.ignore)
        return active

    def _match_target(self, filepath: str) -> str:
        """Path that ``paths`` regexes are matched against.

        Patterns are written relative to the config file's directory, so an
        absolute path is made relative to it when possible. Paths outside that
        directory are matched as given.
        """
        path = Path(filepath)
        if path.is_absolute():
            try:
                return path.relative_to(self.root).as_posix()
            except ValueError:
                return path.as_posix()
        return path.as_posix()


def load_config(
    explicit_path: str | None = None,
    start_dir: str | None = None,
) -> Config | None:
    """Load configuration, or return ``None`` when none is configured.

    With ``explicit_path`` the file must exist. Otherwise the nearest
    ``pyproject.toml`` at or above ``start_dir`` (default: the working
    directory) is used, and a file without a
    ``[tool.databricks-notebook-linter]`` section counts as no configuration.
    """
    if explicit_path is not None:
        path = Path(explicit_path)
        if not path.is_file():
            raise ConfigError(f"config file not found: {explicit_path}")
    else:
        found = _discover(Path(start_dir) if start_dir is not None else Path.cwd())
        if found is None:
            return None
        path = found

    return _parse(path)


def _discover(start: Path) -> Path | None:
    for directory in (start, *start.parents):
        candidate = directory / "pyproject.toml"
        if candidate.is_file():
            return candidate
    return None


def _parse(path: Path) -> Config | None:
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{path}: invalid TOML: {e}") from e

    tool = data.get("tool")
    if not isinstance(tool, dict) or TOOL_SECTION not in tool:
        return None

    where = f"{path}: [tool.{TOOL_SECTION}]"
    section = tool[TOOL_SECTION]
    if not isinstance(section, dict):
        raise ConfigError(f"{where} must be a table")

    _reject_unknown_keys(section, TOP_LEVEL_KEYS, where)

    raw_per_path = section.get("per-path", [])
    if not isinstance(raw_per_path, list):
        raise ConfigError(f"{where}: 'per-path' must be a list of tables")

    return Config(
        path=path,
        root=path.parent,
        select=_optional_string_list(section, "select", where),
        ignore=_optional_string_list(section, "ignore", where),
        per_path=tuple(
            _parse_path_rules(entry, index, path)
            for index, entry in enumerate(raw_per_path)
        ),
    )


def _parse_path_rules(entry: Any, index: int, path: Path) -> PathRules:
    where = f"{path}: [[tool.{TOOL_SECTION}.per-path]] entry {index + 1}"
    if not isinstance(entry, dict):
        raise ConfigError(f"{where}: 'per-path' entries must be tables")

    _reject_unknown_keys(entry, PER_PATH_KEYS, where)

    raw_paths = _string_list(entry.get("paths", []), "paths", where)
    if not raw_paths:
        raise ConfigError(f"{where}: requires a non-empty 'paths' list of regexes")

    patterns = []
    for pattern in raw_paths:
        try:
            patterns.append(re.compile(pattern))
        except re.error as e:
            raise ConfigError(f"{where}: invalid regex {pattern!r}: {e}") from e

    return PathRules(
        patterns=tuple(patterns),
        select=_optional_string_list(entry, "select", where),
        extend_select=_string_list(
            entry.get("extend-select", []), "extend-select", where
        ),
        ignore=_string_list(entry.get("ignore", []), "ignore", where),
    )


def _reject_unknown_keys(table: dict, allowed: frozenset[str], where: str) -> None:
    unknown = set(table) - allowed
    if unknown:
        valid = ", ".join(sorted(allowed))
        raise ConfigError(
            f"{where}: unknown key '{sorted(unknown)[0]}' (valid keys: {valid})"
        )


def _optional_string_list(
    table: dict,
    key: str,
    where: str,
) -> tuple[str, ...] | None:
    if key not in table:
        return None
    return _string_list(table[key], key, where)


def _string_list(value: Any, key: str, where: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ConfigError(f"{where}: '{key}' must be a list of strings")
    return tuple(value)
