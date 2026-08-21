from __future__ import annotations

from databricks_notebook_linter.fix_magic import (
    DEFAULT_RULE_CODES,
    FIXABLE_RULE_CODES,
    check_file,
    fix_file,
)

DNL005_ONLY = {"DNL005"}


def test_dnl005_is_not_enabled_by_default():
    assert "DNL005" not in DEFAULT_RULE_CODES


def test_dnl005_is_not_fixable():
    assert "DNL005" not in FIXABLE_RULE_CODES


def test_check_when_widgets_get_reports_diagnostic(notebook):
    # Given: a notebook that reads config from a widget
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        env = dbutils.widgets.get("env")
    """)

    # When
    diagnostics = check_file(filepath, DNL005_ONLY)

    # Then
    assert len(diagnostics) == 1
    assert diagnostics[0].code == "DNL005"
    assert "dbutils.widgets.get" in diagnostics[0].message
    assert diagnostics[0].line == 5


def test_check_when_widgets_get_argument_reports_diagnostic(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        env = dbutils.widgets.getArgument("env", "dev")
    """)

    diagnostics = check_file(filepath, DNL005_ONLY)
    assert len(diagnostics) == 1
    assert "dbutils.widgets.getArgument" in diagnostics[0].message


def test_check_when_default_rules_does_not_report_dnl005(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        env = dbutils.widgets.get("env")
    """)

    codes = {d.code for d in check_file(filepath)}
    assert "DNL005" not in codes


def test_check_when_reference_is_commented_out_returns_empty(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        # env = dbutils.widgets.get("env")
        env = "dev"  # was dbutils.widgets.get("env")
    """)

    assert check_file(filepath, DNL005_ONLY) == []


def test_check_when_reference_is_inside_string_literal_returns_empty(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        msg = "call dbutils.widgets.get to read config"
        other = 'dbutils.widgets.getArgument'
    """)

    assert check_file(filepath, DNL005_ONLY) == []


def test_check_when_magic_prefixed_line_reports_diagnostic(notebook):
    """# MAGIC-prefixed Python is still executed by Databricks."""
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        # MAGIC env = dbutils.widgets.get("env")
    """)

    diagnostics = check_file(filepath, DNL005_ONLY)
    assert len(diagnostics) == 1
    assert diagnostics[0].code == "DNL005"


def test_check_when_spaces_around_dots_reports_diagnostic(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        env = dbutils . widgets . get("env")
    """)

    assert len(check_file(filepath, DNL005_ONLY)) == 1


def test_check_when_bound_without_call_reports_diagnostic(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        reader = dbutils.widgets.get
    """)

    assert len(check_file(filepath, DNL005_ONLY)) == 1


def test_check_when_other_widget_methods_returns_empty(notebook):
    """DNL005 targets config reads, not widget declaration or removal."""
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        dbutils.widgets.text("env", "dev")
        dbutils.widgets.dropdown("mode", "a", ["a", "b"])
        dbutils.widgets.removeAll()
        dbutils.fs.ls("/")
        widgets.get("env")
    """)

    assert check_file(filepath, DNL005_ONLY) == []


def test_check_when_similar_method_name_returns_empty(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        dbutils.widgets.getAll()
    """)

    assert check_file(filepath, DNL005_ONLY) == []


def test_check_when_multiple_reads_reports_each(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        env = dbutils.widgets.get("env")
        table = dbutils.widgets.get("table")

        # COMMAND ----------

        mode = dbutils.widgets.getArgument("mode")
    """)

    diagnostics = check_file(filepath, DNL005_ONLY)
    assert len(diagnostics) == 3
    assert [d.line for d in diagnostics] == [5, 6, 10]


def test_check_when_two_reads_on_one_line_reports_once(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        pair = (dbutils.widgets.get("a"), dbutils.widgets.get("b"))
    """)

    assert len(check_file(filepath, DNL005_ONLY)) == 1


def test_fix_never_claims_dnl005(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        env = dbutils.widgets.get("env")
    """)

    assert fix_file(filepath, DNL005_ONLY) == set()
    assert 'dbutils.widgets.get("env")' in notebook.read()


def test_check_when_not_databricks_notebook_returns_empty(notebook):
    filepath = notebook.write("""\
        env = dbutils.widgets.get("env")
    """)

    assert check_file(filepath, DNL005_ONLY) == []


def test_check_when_single_line_triple_quoted_string_returns_empty(notebook):
    filepath = notebook.write('''\
        # Databricks notebook source

        # COMMAND ----------

        doc = """dbutils.widgets.get is banned here"""
    ''')

    assert check_file(filepath, DNL005_ONLY) == []


def test_check_when_multiline_string_mentions_widget_get_reports_it(notebook):
    """Known limitation: detection is line-based, so a match inside a
    multi-line string is reported. Documented in the README."""
    filepath = notebook.write('''\
        # Databricks notebook source

        # COMMAND ----------

        doc = """
        Do not call dbutils.widgets.get here.
        """
    ''')

    assert len(check_file(filepath, DNL005_ONLY)) == 1
