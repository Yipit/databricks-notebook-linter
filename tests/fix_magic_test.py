from __future__ import annotations

import textwrap

import pytest

from databricks_notebook_linter.fix_magic import check_file, fix_file, main


@pytest.fixture
def notebook(tmp_path):
    """Create a temp .py file and return a helper to write/read it."""
    path = tmp_path / "notebook.py"

    class NotebookHelper:
        def __init__(self, path):
            self.path = path

        def write(self, content: str) -> str:
            self.path.write_text(textwrap.dedent(content))
            return str(self.path)

        def read(self) -> str:
            return self.path.read_text()

    return NotebookHelper(path)


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


def test_fix_file_when_empty_notebook_returns_false(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source
    """)

    assert fix_file(filepath) is False


def test_fix_file_when_not_py_extension_skipped_by_main(tmp_path):
    """The main() entrypoint filters by .py extension."""
    import sys

    path = tmp_path / "notebook.sql"
    path.write_text("# Databricks notebook source\n%pip install foo\n")

    orig_argv = sys.argv
    sys.argv = ["fix-databricks-magic", "--fix", str(path)]
    try:
        assert main() == 0
    finally:
        sys.argv = orig_argv


# --- Edge cases for block/multiline magic that need a state machine ---


def test_fix_file_when_conditional_preserves_relative_indentation(notebook):
    """Magic lines inside a block must preserve indentation relative to the block."""
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        if COMPUTE_ENV == "serverless":
            %pip install -U hf_transfer
    """)

    assert fix_file(filepath) is True
    content = notebook.read()
    # The %pip must keep its indentation relative to the if
    assert '# MAGIC if COMPUTE_ENV == "serverless":\n' in content
    assert "# MAGIC     %pip install -U hf_transfer\n" in content


def test_fix_file_when_block_has_python_between_starter_and_magic(notebook):
    """All lines in a block containing magic must be prefixed, not just the
    block starter and the magic line."""
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        if COMPUTE_ENV == "serverless":
            TOKEN = dbutils.secrets.get("hf", "token")
            %pip install -U hf_transfer
    """)

    assert fix_file(filepath) is True
    content = notebook.read()
    # The intermediate Python line must also be prefixed
    assert '# MAGIC if COMPUTE_ENV == "serverless":\n' in content
    assert '# MAGIC     TOKEN = dbutils.secrets.get("hf", "token")\n' in content
    assert "# MAGIC     %pip install -U hf_transfer\n" in content


def test_fix_file_when_if_else_both_have_magic(notebook):
    """Both branches of an if/else containing magic must be fully prefixed."""
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        if ENV == "dev":
            %pip install foo --index-url $DEV_INDEX
        else:
            %pip install foo
    """)

    assert fix_file(filepath) is True
    content = notebook.read()
    assert '# MAGIC if ENV == "dev":\n' in content
    assert "# MAGIC     %pip install foo --index-url $DEV_INDEX\n" in content
    assert "# MAGIC else:\n" in content
    assert "# MAGIC     %pip install foo\n" in content


def test_fix_file_when_nested_if_both_levels_prefixed(notebook):
    """Nested blocks containing magic must prefix all enclosing levels."""
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        if USE_GPU:
            if COMPUTE_ENV == "serverless":
                %pip install -U hf_transfer
    """)

    assert fix_file(filepath) is True
    content = notebook.read()
    assert "# MAGIC if USE_GPU:\n" in content
    assert '# MAGIC     if COMPUTE_ENV == "serverless":\n' in content
    assert "# MAGIC         %pip install -U hf_transfer\n" in content


def test_fix_file_when_for_loop_contains_magic(notebook):
    """A for-loop body with magic must prefix the entire block."""
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        for pkg in ["transformers", "datasets"]:
            %pip install {pkg}
    """)

    assert fix_file(filepath) is True
    content = notebook.read()
    assert '# MAGIC for pkg in ["transformers", "datasets"]:\n' in content
    assert "# MAGIC     %pip install {pkg}\n" in content


def test_fix_file_when_try_except_contains_magic(notebook):
    """try/except blocks with magic must prefix the entire block."""
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        try:
            %pip install experimental_pkg
        except:
            %pip install fallback_pkg
    """)

    assert fix_file(filepath) is True
    content = notebook.read()
    assert "# MAGIC try:\n" in content
    assert "# MAGIC     %pip install experimental_pkg\n" in content
    assert "# MAGIC except:\n" in content
    assert "# MAGIC     %pip install fallback_pkg\n" in content


# --- Idempotency tests ---


def test_fix_file_is_idempotent_with_conditional_block(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        if COMPUTE_ENV == "serverless":
            %pip install -U hf_transfer
    """)

    assert fix_file(filepath) is True
    first_pass = notebook.read()
    assert fix_file(filepath) is False
    second_pass = notebook.read()
    assert first_pass == second_pass


def test_fix_file_is_idempotent_with_nested_blocks(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        if USE_GPU:
            if COMPUTE_ENV == "serverless":
                %pip install -U hf_transfer
    """)

    assert fix_file(filepath) is True
    first_pass = notebook.read()
    assert fix_file(filepath) is False
    second_pass = notebook.read()
    assert first_pass == second_pass


def test_fix_file_is_idempotent_with_if_else(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        if ENV == "dev":
            %pip install foo --index-url $DEV_INDEX
        else:
            %pip install foo
    """)

    assert fix_file(filepath) is True
    first_pass = notebook.read()
    assert fix_file(filepath) is False
    second_pass = notebook.read()
    assert first_pass == second_pass


def test_fix_file_is_idempotent_with_intermediate_python(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        if COMPUTE_ENV == "serverless":
            TOKEN = dbutils.secrets.get("hf", "token")
            %pip install -U hf_transfer
    """)

    assert fix_file(filepath) is True
    first_pass = notebook.read()
    assert fix_file(filepath) is False
    second_pass = notebook.read()
    assert first_pass == second_pass


def test_fix_file_is_idempotent_with_multiline_continuation(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        %pip install -U \\
          transformers==4.57.6 \\
          datasets==4.5.0
    """)

    assert fix_file(filepath) is True
    first_pass = notebook.read()
    assert fix_file(filepath) is False
    second_pass = notebook.read()
    assert first_pass == second_pass


def test_fix_file_is_idempotent_with_mixed_cell(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        import os
        env = os.getenv("ENV", "prod")
        %pip install foo
        result = 1 + 2
    """)

    assert fix_file(filepath) is True
    first_pass = notebook.read()
    assert fix_file(filepath) is False
    second_pass = notebook.read()
    assert first_pass == second_pass


# --- check_file tests ---


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


# --- main() integration tests ---


def test_main_check_mode_when_issues_found_returns_1_and_prints_diagnostics(
    tmp_path, capsys, monkeypatch,
):
    path = tmp_path / "notebook.py"
    path.write_text("# Databricks notebook source\n%pip install foo\n")

    monkeypatch.setattr("sys.argv", ["fix-databricks-magic", str(path)])
    assert main() == 1

    captured = capsys.readouterr()
    assert "%pip install foo" in captured.out
    assert "needs '# MAGIC' prefix" in captured.out
    # Check mode must NOT modify the file
    assert path.read_text() == "# Databricks notebook source\n%pip install foo\n"


def test_main_check_mode_when_clean_returns_0(tmp_path, monkeypatch):
    path = tmp_path / "notebook.py"
    path.write_text("# Databricks notebook source\n# MAGIC %pip install foo\n")

    monkeypatch.setattr("sys.argv", ["fix-databricks-magic", str(path)])
    assert main() == 0


def test_main_fix_mode_when_changes_made_returns_1_and_prints_filenames(
    tmp_path, capsys, monkeypatch,
):
    path = tmp_path / "notebook.py"
    path.write_text("# Databricks notebook source\n%pip install foo\n")

    monkeypatch.setattr("sys.argv", ["fix-databricks-magic", "--fix", str(path)])
    assert main() == 1

    captured = capsys.readouterr()
    assert "Fixed magic commands in:" in captured.out
    assert "# MAGIC %pip install foo" in path.read_text()


def test_main_fix_mode_when_no_changes_returns_0(tmp_path, monkeypatch):
    path = tmp_path / "notebook.py"
    path.write_text("# Databricks notebook source\n# MAGIC %pip install foo\n")

    monkeypatch.setattr("sys.argv", ["fix-databricks-magic", "--fix", str(path)])
    assert main() == 0


def test_main_when_non_py_file_skipped_in_check_mode(tmp_path, monkeypatch):
    path = tmp_path / "notebook.sql"
    path.write_text("# Databricks notebook source\n%pip install foo\n")

    monkeypatch.setattr("sys.argv", ["fix-databricks-magic", str(path)])
    assert main() == 0


def test_main_with_multiple_files(tmp_path, capsys, monkeypatch):
    clean = tmp_path / "clean.py"
    clean.write_text("# Databricks notebook source\nimport math\n")

    dirty = tmp_path / "dirty.py"
    dirty.write_text("# Databricks notebook source\n%pip install foo\n")

    monkeypatch.setattr(
        "sys.argv", ["fix-databricks-magic", str(clean), str(dirty)],
    )
    assert main() == 1

    captured = capsys.readouterr()
    assert "%pip install foo" in captured.out
    assert "clean.py" not in captured.out


# --- Magic in else/elif/except/finally (bug fix) ---


def test_fix_file_when_magic_only_in_else_prefixes_entire_if_else(notebook):
    """Magic only in else branch -- entire if/else must be prefixed."""
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        if ENV == "prod":
            print("production")
        else:
            %pip install debug-tools
    """)

    assert fix_file(filepath) is True
    content = notebook.read()
    assert '# MAGIC if ENV == "prod":\n' in content
    assert '# MAGIC     print("production")\n' in content
    assert "# MAGIC else:\n" in content
    assert "# MAGIC     %pip install debug-tools\n" in content


def test_fix_file_when_magic_only_in_else_is_idempotent(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        if ENV == "prod":
            print("production")
        else:
            %pip install debug-tools
    """)

    assert fix_file(filepath) is True
    first_pass = notebook.read()
    # Verify correctness (entire block prefixed, not just the else branch)
    assert '# MAGIC if ENV == "prod":\n' in first_pass
    assert "# MAGIC else:\n" in first_pass
    assert fix_file(filepath) is False
    second_pass = notebook.read()
    assert first_pass == second_pass


def test_fix_file_when_magic_only_in_elif_prefixes_entire_chain(notebook):
    """Magic only in elif branch -- entire if/elif/else chain must be prefixed."""
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        if ENV == "prod":
            print("production")
        elif ENV == "dev":
            %pip install dev-tools
        else:
            print("other")
    """)

    assert fix_file(filepath) is True
    content = notebook.read()
    assert '# MAGIC if ENV == "prod":\n' in content
    assert '# MAGIC     print("production")\n' in content
    assert '# MAGIC elif ENV == "dev":\n' in content
    assert "# MAGIC     %pip install dev-tools\n" in content
    assert "# MAGIC else:\n" in content
    assert '# MAGIC     print("other")\n' in content


def test_fix_file_when_magic_only_in_elif_is_idempotent(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        if ENV == "prod":
            print("production")
        elif ENV == "dev":
            %pip install dev-tools
        else:
            print("other")
    """)

    assert fix_file(filepath) is True
    first_pass = notebook.read()
    # Verify correctness (entire chain prefixed, not just elif onward)
    assert '# MAGIC if ENV == "prod":\n' in first_pass
    assert '# MAGIC elif ENV == "dev":\n' in first_pass
    assert fix_file(filepath) is False
    second_pass = notebook.read()
    assert first_pass == second_pass


def test_fix_file_when_magic_only_in_except_prefixes_entire_try_except(notebook):
    """Magic only in except branch -- entire try/except must be prefixed."""
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        try:
            import pandas
        except:
            %pip install pandas
    """)

    assert fix_file(filepath) is True
    content = notebook.read()
    assert "# MAGIC try:\n" in content
    assert "# MAGIC     import pandas\n" in content
    assert "# MAGIC except:\n" in content
    assert "# MAGIC     %pip install pandas\n" in content


def test_fix_file_when_magic_only_in_except_is_idempotent(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        try:
            import pandas
        except:
            %pip install pandas
    """)

    assert fix_file(filepath) is True
    first_pass = notebook.read()
    # Verify correctness (entire try/except prefixed, not just except)
    assert "# MAGIC try:\n" in first_pass
    assert "# MAGIC except:\n" in first_pass
    assert fix_file(filepath) is False
    second_pass = notebook.read()
    assert first_pass == second_pass


def test_fix_file_when_magic_only_in_finally_prefixes_entire_try_finally(notebook):
    """Magic only in finally branch -- entire try/finally must be prefixed."""
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        try:
            import pandas
        finally:
            %pip install pandas
    """)

    assert fix_file(filepath) is True
    content = notebook.read()
    assert "# MAGIC try:\n" in content
    assert "# MAGIC     import pandas\n" in content
    assert "# MAGIC finally:\n" in content
    assert "# MAGIC     %pip install pandas\n" in content


def test_fix_file_when_magic_only_in_finally_is_idempotent(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        try:
            import pandas
        finally:
            %pip install pandas
    """)

    assert fix_file(filepath) is True
    first_pass = notebook.read()
    # Verify correctness (entire try/finally prefixed, not just finally)
    assert "# MAGIC try:\n" in first_pass
    assert "# MAGIC finally:\n" in first_pass
    assert fix_file(filepath) is False
    second_pass = notebook.read()
    assert first_pass == second_pass


# --- Multiline continuation inside a block ---


def test_fix_file_when_multiline_continuation_inside_block_preserves_indent(notebook):
    """Multiline continuation inside a conditional block must prefix all lines."""
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        if ENV == "serverless":
            %pip install -U \\
              transformers \\
              datasets
    """)

    assert fix_file(filepath) is True
    content = notebook.read()
    assert '# MAGIC if ENV == "serverless":\n' in content
    assert "# MAGIC     %pip install -U \\\n" in content
    assert "# MAGIC       transformers \\\n" in content
    assert "# MAGIC       datasets\n" in content


def test_fix_file_when_multiline_continuation_inside_block_is_idempotent(notebook):
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        if ENV == "serverless":
            %pip install -U \\
              transformers \\
              datasets
    """)

    assert fix_file(filepath) is True
    first_pass = notebook.read()
    assert '# MAGIC if ENV == "serverless":\n' in first_pass
    assert fix_file(filepath) is False
    second_pass = notebook.read()
    assert first_pass == second_pass
