from __future__ import annotations

from databricks_notebook_linter.fix_magic import check_file, fix_file

DNL002_ONLY = {"DNL002"}


def test_check_when_leading_blank_lines_in_python_cell_reports_diagnostic(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------


        import math
    """)

    diagnostics = check_file(filepath, DNL002_ONLY)
    assert len(diagnostics) == 1
    assert diagnostics[0].code == "DNL002"


def test_check_when_no_leading_blank_lines_returns_empty(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------
        import math
    """)

    assert check_file(filepath, DNL002_ONLY) == []


def test_check_when_magic_cell_skipped(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------


        # MAGIC %md ## Title
    """)

    assert check_file(filepath, DNL002_ONLY) == []


def test_fix_strips_all_leading_blank_lines(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------



        import math
        x = 1
    """)

    applied = fix_file(filepath, DNL002_ONLY)
    assert "DNL002" in applied
    content = notebook.read()
    assert "import math\n" in content
    assert content.index("import math") < content.index("x = 1")


def test_fix_when_no_leading_blanks_returns_empty(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------
        import math
    """)

    assert not fix_file(filepath, DNL002_ONLY)


def test_fix_skips_magic_md_cell(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------


        # MAGIC %md ## Title
    """)

    assert not fix_file(filepath, DNL002_ONLY)


def test_fix_skips_magic_sql_cell(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------


        # MAGIC %sql SELECT 1
    """)

    assert not fix_file(filepath, DNL002_ONLY)


def test_fix_is_idempotent(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------



        import math
    """)

    assert fix_file(filepath, DNL002_ONLY)
    assert not fix_file(filepath, DNL002_ONLY)


def test_fix_strips_blanks_from_multiple_cells(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------


        import math

        # COMMAND ----------


        x = 1
    """)

    applied = fix_file(filepath, DNL002_ONLY)
    assert "DNL002" in applied
    content = notebook.read()
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if "# COMMAND" in line and i + 1 < len(lines):
            next_line = lines[i + 1]
            if next_line.strip():
                assert next_line.strip() != ""


def test_fix_skips_all_blank_cell(notebook):
    notebook.path.write_text(
        "# Databricks notebook source\n"
        "# COMMAND ----------\n"
        "\n"
        "\n"
        "# COMMAND ----------\n"
        "import math\n"
    )

    applied = fix_file(str(notebook.path), DNL002_ONLY)
    assert "DNL002" not in applied


def test_fix_preserves_separator_blank_line_pattern(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------
        import math
    """)

    assert not fix_file(filepath, DNL002_ONLY)
    content = notebook.read()
    assert "# Databricks notebook source\n\n# COMMAND" in content
