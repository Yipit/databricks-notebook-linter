from __future__ import annotations

from databricks_notebook_linter.fix_magic import check_file, fix_file

DNL004_ONLY = {"DNL004"}


def test_check_when_empty_cell_reports_diagnostic(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        import math

        # COMMAND ----------


        # COMMAND ----------

        x = 1
    """)

    diagnostics = check_file(filepath, DNL004_ONLY)
    assert len(diagnostics) == 1
    assert diagnostics[0].code == "DNL004"


def test_check_when_no_empty_cells_returns_empty(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        import math
    """)

    assert check_file(filepath, DNL004_ONLY) == []


def test_fix_removes_empty_cell_and_preceding_separator(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        import math

        # COMMAND ----------


        # COMMAND ----------

        x = 1
    """)

    applied = fix_file(filepath, DNL004_ONLY)
    assert "DNL004" in applied
    content = notebook.read()
    lines = content.splitlines()
    separator_count = sum(1 for line in lines if "COMMAND" in line)
    assert separator_count == 2


def test_fix_never_removes_header_cell(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        import math
    """)

    assert not fix_file(filepath, DNL004_ONLY)


def test_fix_is_idempotent(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        import math

        # COMMAND ----------


        # COMMAND ----------

        x = 1
    """)

    assert fix_file(filepath, DNL004_ONLY)
    assert not fix_file(filepath, DNL004_ONLY)


def test_fix_removes_multiple_empty_cells(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        import math

        # COMMAND ----------


        # COMMAND ----------


        # COMMAND ----------

        x = 1
    """)

    applied = fix_file(filepath, DNL004_ONLY)
    assert "DNL004" in applied
    content = notebook.read()
    lines = content.splitlines()
    separator_count = sum(1 for line in lines if "COMMAND" in line)
    assert separator_count == 2


def test_check_skips_header_cell(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        import math
    """)

    diagnostics = check_file(filepath, DNL004_ONLY)
    assert len(diagnostics) == 0


def test_fix_handles_empty_cell_after_header_without_separator(notebook):
    notebook.path.write_text(
        "# Databricks notebook source\n\n# COMMAND ----------\nimport math\n"
    )

    assert not fix_file(str(notebook.path), DNL004_ONLY)
