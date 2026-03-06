from __future__ import annotations

from databricks_notebook_linter.fix_magic import check_file


def test_check_file_when_bare_magic_returns_diagnostics(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        %pip install foo
    """)

    diagnostics = check_file(filepath)
    assert len(diagnostics) == 1
    assert "%pip install foo" in diagnostics[0]
    assert "needs '# MAGIC' prefix" in diagnostics[0]
    assert f"{filepath}:" in diagnostics[0]


def test_check_file_when_no_magic_returns_empty(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        import math
    """)

    assert check_file(filepath) == []


def test_check_file_when_already_fixed_returns_empty(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        # MAGIC %pip install foo
    """)

    assert check_file(filepath) == []


def test_check_file_when_block_magic_reports_all_lines(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        if ENV == "dev":
            %pip install foo
    """)

    diagnostics = check_file(filepath)
    assert len(diagnostics) == 2
    magic_diags = [d for d in diagnostics if "%pip install foo" in d]
    block_diags = [d for d in diagnostics if "block containing magic" in d]
    assert len(magic_diags) == 1
    assert len(block_diags) == 1


def test_check_file_when_not_databricks_returns_empty(notebook):
    filepath = notebook.write("""\
        import math
        %pip install foo
    """)

    assert check_file(filepath) == []
