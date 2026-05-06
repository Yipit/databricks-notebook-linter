from __future__ import annotations

from databricks_notebook_linter.fix_magic import check_file, fix_file

DNL003_ONLY = {"DNL003"}


def test_check_when_trailing_empty_cell_reports_diagnostic(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        import math

        # COMMAND ----------

    """)

    diagnostics = check_file(filepath, DNL003_ONLY)
    assert len(diagnostics) == 1
    assert diagnostics[0].code == "DNL003"


def test_check_when_no_trailing_empty_cell_returns_empty(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        import math
    """)

    assert check_file(filepath, DNL003_ONLY) == []


def test_fix_removes_trailing_empty_cell_and_separator(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        import math

        # COMMAND ----------

    """)

    applied = fix_file(filepath, DNL003_ONLY)
    assert "DNL003" in applied
    content = notebook.read()
    lines = content.splitlines()
    separator_count = sum(1 for line in lines if "COMMAND" in line)
    assert separator_count == 1


def test_fix_removes_multiple_trailing_empty_cells(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        import math

        # COMMAND ----------


        # COMMAND ----------

    """)

    applied = fix_file(filepath, DNL003_ONLY)
    assert "DNL003" in applied
    content = notebook.read()
    lines = content.splitlines()
    separator_count = sum(1 for line in lines if "COMMAND" in line)
    assert separator_count == 1


def test_fix_when_no_trailing_empty_cells_returns_empty(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        import math
    """)

    assert not fix_file(filepath, DNL003_ONLY)


def test_fix_is_idempotent(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        import math

        # COMMAND ----------

    """)

    assert fix_file(filepath, DNL003_ONLY)
    assert not fix_file(filepath, DNL003_ONLY)


def test_fix_preserves_non_trailing_empty_cell(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        import math

        # COMMAND ----------


        # COMMAND ----------

        x = 1
    """)

    assert not fix_file(filepath, DNL003_ONLY)
