from __future__ import annotations

from databricks_notebook_linter.fix_magic import fix_file


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


# --- Magic in else/elif/except/finally ---


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


# --- Additional edge cases ---


def test_fix_file_when_block_has_blank_line_between_starter_and_magic(notebook):
    """Blank lines inside a block should stay blank, surrounding lines prefixed."""
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        if ENV == "dev":

            %pip install debug-tools
    """)

    assert fix_file(filepath) is True
    content = notebook.read()
    assert '# MAGIC if ENV == "dev":\n' in content
    assert "# MAGIC     %pip install debug-tools\n" in content
    # The blank line between if and %pip should remain blank (not prefixed)
    lines = content.splitlines()
    block_start = next(i for i, line in enumerate(lines) if "# MAGIC if" in line)
    assert lines[block_start + 1].strip() == ""


def test_fix_file_when_with_statement_contains_magic(notebook):
    """A with block containing magic must prefix the entire block."""
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        with open("/tmp/log") as f:
            %pip install debug-tools
    """)

    assert fix_file(filepath) is True
    content = notebook.read()
    assert '# MAGIC with open("/tmp/log") as f:\n' in content
    assert "# MAGIC     %pip install debug-tools\n" in content


def test_fix_file_when_triple_nested_blocks_all_prefixed(notebook):
    """Three levels of nesting: if > for > if > magic, all prefixed."""
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        if USE_GPU:
            for pkg in PACKAGES:
                if pkg.startswith("nvidia"):
                    %pip install {pkg}
    """)

    assert fix_file(filepath) is True
    content = notebook.read()
    assert "# MAGIC if USE_GPU:\n" in content
    assert "# MAGIC     for pkg in PACKAGES:\n" in content
    assert '# MAGIC         if pkg.startswith("nvidia"):\n' in content
    assert "# MAGIC             %pip install {pkg}\n" in content


def test_fix_file_when_indented_magic_without_enclosing_block(notebook):
    """Indented magic with no block starter above it should still be prefixed."""
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

            %pip install foo
    """)

    assert fix_file(filepath) is True
    content = notebook.read()
    assert "# MAGIC     %pip install foo" in content


def test_fix_file_when_blank_line_between_if_block_and_else(notebook):
    """Blank line between if body and else during compound walk-back."""
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


def test_fix_file_when_compound_continuation_at_cell_start(notebook):
    """Compound continuation (else:) at the very start of a cell -- degenerate but handled."""
    path = notebook.path
    # Write raw content to avoid dedent issues with the unusual structure
    path.write_text(
        "# Databricks notebook source\n"
        "\n"
        "# COMMAND ----------\n"
        "\n"
        "else:\n"
        "    %pip install foo\n"
    )

    assert fix_file(str(path)) is True
    content = path.read_text()
    assert "# MAGIC else:\n" in content
    assert "# MAGIC     %pip install foo\n" in content


def test_fix_file_when_python_follows_block_containing_magic(notebook):
    """Regular Python after a block with magic -- the block is prefixed, the trailing line is not."""
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        if ENV == "dev":
            %pip install foo
        x = 1
    """)

    assert fix_file(filepath) is True
    content = notebook.read()
    assert '# MAGIC if ENV == "dev":\n' in content
    assert "# MAGIC     %pip install foo\n" in content
    assert "x = 1\n" in content
    assert "# MAGIC x = 1" not in content


def test_fix_file_when_consecutive_cell_separators(notebook):
    """Two COMMAND separators with no content between them."""
    path = notebook.path
    path.write_text(
        "# Databricks notebook source\n"
        "# COMMAND ----------\n"
        "# COMMAND ----------\n"
        "\n"
        "%pip install foo\n"
    )

    assert fix_file(str(path)) is True
    content = path.read_text()
    assert "# MAGIC %pip install foo\n" in content


def test_fix_file_when_notebook_ends_at_cell_separator(notebook):
    """Notebook whose last line is a cell separator with no trailing content."""
    path = notebook.path
    path.write_text(
        "# Databricks notebook source\n"
        "\n"
        "# COMMAND ----------\n"
        "\n"
        "%pip install foo\n"
        "\n"
        "# COMMAND ----------\n"
    )

    assert fix_file(str(path)) is True
    content = path.read_text()
    assert "# MAGIC %pip install foo\n" in content


def test_fix_file_when_magic_in_separate_cells_both_fixed(notebook):
    """Two cells each with bare magic -- both must be fixed independently."""
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        %pip install foo

        # COMMAND ----------

        %pip install bar
    """)

    assert fix_file(filepath) is True
    content = notebook.read()
    assert "# MAGIC %pip install foo\n" in content
    assert "# MAGIC %pip install bar\n" in content


def test_fix_file_when_cell_without_magic_not_touched(notebook):
    """In a multi-cell notebook, cells without magic must be left untouched."""
    filepath = notebook.write("""\
        # Databricks notebook source

        # COMMAND ----------

        import math
        x = math.pi

        # COMMAND ----------

        %pip install foo
    """)

    assert fix_file(filepath) is True
    content = notebook.read()
    # Clean cell untouched
    assert "import math\n" in content
    assert "x = math.pi\n" in content
    assert "# MAGIC import math" not in content
    assert "# MAGIC x = math" not in content
    # Dirty cell fixed
    assert "# MAGIC %pip install foo\n" in content
