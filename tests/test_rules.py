from __future__ import annotations

import pytest

from databricks_notebook_linter.fix_magic import (
    ALL_RULE_CODES,
    Diagnostic,
    resolve_rules,
)


def test_resolve_rules_when_no_args_returns_all():
    assert resolve_rules() == ALL_RULE_CODES


def test_resolve_rules_when_select_only_returns_selected():
    assert resolve_rules(select=["DNL001", "DNL002"]) == {"DNL001", "DNL002"}


def test_resolve_rules_when_ignore_only_removes_from_all():
    assert resolve_rules(ignore=["DNL003"]) == {"DNL001", "DNL002", "DNL004"}


def test_resolve_rules_when_select_and_ignore_applies_both():
    result = resolve_rules(select=["DNL001", "DNL002", "DNL003"], ignore=["DNL002"])
    assert result == {"DNL001", "DNL003"}


def test_resolve_rules_when_unknown_select_code_raises():
    with pytest.raises(ValueError, match="DNL999"):
        resolve_rules(select=["DNL999"])


def test_resolve_rules_when_unknown_ignore_code_raises():
    with pytest.raises(ValueError, match="DNL999"):
        resolve_rules(ignore=["DNL999"])


def test_resolve_rules_when_empty_select_returns_all():
    assert resolve_rules(select=None) == ALL_RULE_CODES


def test_diagnostic_str_format():
    d = Diagnostic("notebook.py", 5, "DNL001", "bare magic command")
    assert str(d) == "notebook.py:5: [DNL001] bare magic command"
