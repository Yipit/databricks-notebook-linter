from __future__ import annotations

from databricks_notebook_linter.fix_magic import fix_file


def test_fix_file_when_not_databricks_notebook_returns_false(notebook):
    filepath = notebook.write("""\
        import math
        %pip install foo
    """)
    assert fix_file(filepath) is False


def test_fix_file_when_bare_pip_prepends_magic(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        %pip install some-package==1.0.4
    """)

    assert fix_file(filepath) is True
    content = notebook.read()
    assert "# MAGIC %pip install some-package==1.0.4" in content
    assert "\n%pip" not in content


def test_fix_file_when_already_has_magic_returns_false(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        # MAGIC %pip install some-package==1.0.4
    """)

    assert fix_file(filepath) is False


def test_fix_file_when_shell_bang_prepends_magic(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        !nvidia-smi
    """)

    assert fix_file(filepath) is True
    content = notebook.read()
    assert "# MAGIC !nvidia-smi" in content
    assert "\n!nvidia-smi" not in content


def test_fix_file_when_multiline_pip_prepends_magic_on_all_lines(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        %pip install -U \\
          transformers==4.57.6 \\
          datasets==4.5.0 \\
          peft==0.18.1
    """)

    assert fix_file(filepath) is True
    content = notebook.read()
    assert "# MAGIC %pip install -U \\\n" in content
    assert "# MAGIC transformers==4.57.6 \\\n" in content
    assert "# MAGIC datasets==4.5.0 \\\n" in content
    assert "# MAGIC peft==0.18.1\n" in content


def test_fix_file_when_conditional_pip_prefixes_both_if_and_pip(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        if COMPUTE_ENV == "serverless":
            %pip install -U hf_transfer
    """)

    assert fix_file(filepath) is True
    content = notebook.read()
    assert '# MAGIC if COMPUTE_ENV == "serverless":\n' in content
    assert "# MAGIC     %pip install -U hf_transfer" in content


def test_fix_file_when_mixed_cell_with_python_and_pip(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        INDEX_URL = dbutils.secrets.get("pip", "index_url")
        %pip install some-package==1.0.4 --index-url $INDEX_URL
    """)

    assert fix_file(filepath) is True
    content = notebook.read()
    assert 'INDEX_URL = dbutils.secrets.get("pip", "index_url")' in content
    assert "# MAGIC %pip install some-package==1.0.4 --index-url $INDEX_URL" in content


def test_fix_file_when_multiple_magic_commands_fixes_all(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        !nvidia-smi

        %pip install -U foo

        if ENV == "test":
            %pip install bar
    """)

    assert fix_file(filepath) is True
    content = notebook.read()
    assert "# MAGIC !nvidia-smi" in content
    assert "# MAGIC %pip install -U foo" in content
    assert '# MAGIC if ENV == "test":\n' in content
    assert "# MAGIC     %pip install bar" in content


def test_fix_file_is_idempotent(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        %pip install foo
    """)

    assert fix_file(filepath) is True
    assert fix_file(filepath) is False


def test_fix_file_preserves_non_magic_lines(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        import math
        x = 1 + 2
        print("hello")
    """)

    assert fix_file(filepath) is False


def test_fix_file_when_multiline_continuation_last_line_no_backslash(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        %pip install -U \\
          foo \\
          bar
    """)

    assert fix_file(filepath) is True
    content = notebook.read()
    assert "# MAGIC %pip install -U \\\n" in content
    assert "# MAGIC foo \\\n" in content
    assert "# MAGIC bar\n" in content


def test_fix_file_when_python_equality_not_treated_as_magic(notebook):
    """Regular Python using == should never be prefixed with # MAGIC."""
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        version = "1.0"
        if version == "1.0":
            print("correct")
    """)

    assert fix_file(filepath) is False
    content = notebook.read()
    assert "# MAGIC" not in content


def test_fix_file_when_python_string_contains_percent_not_treated_as_magic(notebook):
    """A string containing % should not trigger magic prefixing."""
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        msg = "%pip is a magic command"
        print(msg)
    """)

    assert fix_file(filepath) is False
    content = notebook.read()
    assert "# MAGIC" not in content


def test_fix_file_when_python_modulo_operator_not_treated_as_magic(notebook):
    """Python modulo operator should not be treated as magic."""
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        result = 10 % 3
        print(f"{result}%")
    """)

    assert fix_file(filepath) is False
    content = notebook.read()
    assert "# MAGIC" not in content


def test_fix_file_when_comment_contains_magic_prefix_not_treated_as_magic(notebook):
    """Comments that mention %pip should not be double-prefixed."""
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        # Use %pip to install packages
        import math
    """)

    assert fix_file(filepath) is False
    content = notebook.read()
    assert "# MAGIC" not in content


def test_fix_file_when_python_if_without_magic_body_not_treated_as_magic(notebook):
    """An if-block with no magic commands should be left alone."""
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        if True:
            print("hello")
    """)

    assert fix_file(filepath) is False
    content = notebook.read()
    assert "# MAGIC" not in content


def test_fix_file_when_mixed_cell_preserves_regular_python_exactly(notebook):
    """In a cell with both magic and Python, Python lines must be untouched."""
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        import os
        env = os.getenv("ENV", "prod")
        %pip install foo
        result = 1 + 2
    """)

    assert fix_file(filepath) is True
    content = notebook.read()
    assert "import os\n" in content
    assert 'env = os.getenv("ENV", "prod")\n' in content
    assert "# MAGIC %pip install foo\n" in content
    assert "result = 1 + 2\n" in content
    # Regular Python lines must NOT be prefixed
    assert "# MAGIC import os" not in content
    assert "# MAGIC env =" not in content
    assert "# MAGIC result" not in content


def test_fix_file_when_sql_magic_prepends_magic(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        %sql SELECT * FROM my_table
    """)

    assert fix_file(filepath) is True
    content = notebook.read()
    assert "# MAGIC %sql SELECT * FROM my_table" in content


def test_fix_file_when_md_magic_prepends_magic(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        %md # My Notebook Title
    """)

    assert fix_file(filepath) is True
    content = notebook.read()
    assert "# MAGIC %md # My Notebook Title" in content


def test_fix_file_when_bare_restart_python_prepends_magic(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        dbutils.library.restartPython()
    """)

    assert fix_file(filepath) is True
    content = notebook.read()
    assert "# MAGIC dbutils.library.restartPython()" in content


def test_fix_file_when_restart_python_already_has_magic_returns_false(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        # MAGIC dbutils.library.restartPython()
    """)

    assert fix_file(filepath) is False


def test_fix_file_when_restart_python_is_idempotent(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        dbutils.library.restartPython()
    """)

    assert fix_file(filepath) is True
    assert fix_file(filepath) is False


def test_fix_file_when_empty_notebook_returns_false(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source
    """)

    assert fix_file(filepath) is False


def test_fix_file_when_not_equal_operator_at_line_start_not_treated_as_magic(notebook):
    """!= at the start of a line (from black-formatted expressions) is not a shell bang."""
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        result = (
            some_value
            != other_value
        )
    """)

    assert fix_file(filepath) is False
    content = notebook.read()
    assert "# MAGIC" not in content


def test_fix_file_when_not_equal_inside_function_body_not_treated_as_magic(notebook):
    """!= inside a function should not cause the entire function to be magic-prefixed."""
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        def check_values(df):
            df_wrong = df.filter(
                (F.col("gold_name").isNotNull())
                & (F.col("gold_name")
                    != F.col("pred_name"))
            )
            return df_wrong
    """)

    assert fix_file(filepath) is False
    content = notebook.read()
    assert "# MAGIC" not in content


def test_fix_file_when_not_equal_in_chained_pyspark_not_treated_as_magic(notebook):
    """!= on its own line in a chained PySpark expression is not a shell bang."""
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        df_filtered = df.filter(
            (F.col("a").isNotNull())
            & (F.col("a")
                != F.col("b"))
        )
    """)

    assert fix_file(filepath) is False
    content = notebook.read()
    assert "# MAGIC" not in content
