from __future__ import annotations

import pytest

from databricks_notebook_linter.fix_magic import (
    ALL_RULE_CODES,
    ALL_RULES,
    DEFAULT_RULE_CODES,
    FIXABLE_RULE_CODES,
    Diagnostic,
    resolve_rules,
)


def test_resolve_rules_when_no_args_returns_default_rules():
    assert resolve_rules() == DEFAULT_RULE_CODES


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


def test_resolve_rules_when_empty_select_returns_default_rules():
    assert resolve_rules(select=None) == DEFAULT_RULE_CODES


def test_resolve_rules_when_off_by_default_rule_selected_enables_it():
    assert resolve_rules(select=["DNL005"]) == {"DNL005"}


def test_default_rule_codes_is_a_subset_of_all_rule_codes():
    assert DEFAULT_RULE_CODES < ALL_RULE_CODES


def test_fixable_rule_codes_is_a_subset_of_all_rule_codes():
    assert FIXABLE_RULE_CODES < ALL_RULE_CODES


def test_every_rule_code_is_unique():
    codes = [rule.code for rule in ALL_RULES]
    assert len(codes) == len(set(codes))


def test_diagnostic_str_format():
    d = Diagnostic("notebook.py", 5, "DNL001", "bare magic command")
    assert str(d) == "notebook.py:5: [DNL001] bare magic command"


# --- catalog invariants --------------------------------------------------
#
# ALL_RULES is the single declaration of every rule: check_file() and fix_file()
# both iterate it, and the code sets derive from it. A rule cannot be declared
# without a check function -- Rule.check is a required field -- so what is left
# to pin is that nothing passes a null one, and that the order stays right.


def test_every_rule_has_a_callable_check_function():
    for rule in ALL_RULES:
        assert callable(rule.check), rule.code


def test_every_fix_is_callable_or_absent():
    for rule in ALL_RULES:
        assert rule.fix is None or callable(rule.fix), rule.code


def test_fixable_rule_codes_matches_the_rules_declaring_a_fix():
    assert FIXABLE_RULE_CODES == {r.code for r in ALL_RULES if r.fix is not None}


def test_check_only_rules_declare_no_fix():
    check_only = {r.code for r in ALL_RULES if r.fix is None}
    assert check_only == ALL_RULE_CODES - FIXABLE_RULE_CODES


def test_fix_pipeline_order_is_the_documented_order():
    """DNL002 -> DNL004 -> DNL003 -> DNL001, as documented in the README.

    DNL002 can empty a cell that DNL004 then removes, DNL004 clears interior
    empty cells before DNL003 examines trailing ones, and DNL001 runs last on
    the final cell structure. This is ALL_RULES order, so reordering the
    catalog changes what --fix produces.
    """
    fix_order = [r.code for r in ALL_RULES if r.fix is not None]
    assert fix_order == ["DNL002", "DNL004", "DNL003", "DNL001"]
