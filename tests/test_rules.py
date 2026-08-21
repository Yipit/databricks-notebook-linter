from __future__ import annotations

import pytest

from databricks_notebook_linter.fix_magic import (
    ALL_RULE_CODES,
    ALL_RULES,
    CHECK_RULES,
    DEFAULT_RULE_CODES,
    FIX_RULES,
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


# --- registry invariants -------------------------------------------------
#
# CHECK_RULES and FIX_RULES are what check_file()/fix_file() iterate, so a rule
# added to ALL_RULES but not registered would silently never run.


def test_every_rule_has_a_check_function_registered():
    assert set(CHECK_RULES) == ALL_RULE_CODES


def test_fix_rules_only_reference_known_rule_codes():
    assert set(FIX_RULES) <= ALL_RULE_CODES


def test_fixable_rule_codes_matches_the_fix_registry():
    assert FIXABLE_RULE_CODES == set(FIX_RULES)


def test_fix_registry_order_is_the_documented_pipeline_order():
    """DNL002 -> DNL004 -> DNL003 -> DNL001, as documented in the README.

    DNL002 can empty a cell that DNL004 then removes, DNL004 clears interior
    empty cells before DNL003 examines trailing ones, and DNL001 runs last on
    the final cell structure.
    """
    assert list(FIX_RULES) == ["DNL002", "DNL004", "DNL003", "DNL001"]
