from __future__ import annotations

from databricks_notebook_linter.fix_magic import fix_file, main

REALISTIC_NOTEBOOK = """\
# Databricks notebook source

# COMMAND ----------

# MAGIC %md # Model Training Notebook

# COMMAND ----------

import os
from datetime import datetime

# COMMAND ----------

COMPUTE_ENV = os.getenv("COMPUTE_ENV", "standard")
MODEL_NAME = "distilbert-base-uncased"

# COMMAND ----------

if COMPUTE_ENV == "serverless":
    %pip install -U \\
      transformers \\
      datasets

# COMMAND ----------

for pkg in ["accelerate", "evaluate"]:
    %pip install {pkg}

# COMMAND ----------

try:
    import bitsandbytes
except:
    %pip install bitsandbytes

# COMMAND ----------

print(f"Training {MODEL_NAME} at {datetime.now()}")
"""

REALISTIC_NOTEBOOK_EXPECTED = """\
# Databricks notebook source

# COMMAND ----------

# MAGIC %md # Model Training Notebook

# COMMAND ----------

import os
from datetime import datetime

# COMMAND ----------

COMPUTE_ENV = os.getenv("COMPUTE_ENV", "standard")
MODEL_NAME = "distilbert-base-uncased"

# COMMAND ----------

# MAGIC if COMPUTE_ENV == "serverless":
# MAGIC     %pip install -U \\
# MAGIC       transformers \\
# MAGIC       datasets

# COMMAND ----------

# MAGIC for pkg in ["accelerate", "evaluate"]:
# MAGIC     %pip install {pkg}

# COMMAND ----------

# MAGIC try:
# MAGIC     import bitsandbytes
# MAGIC except:
# MAGIC     %pip install bitsandbytes

# COMMAND ----------

print(f"Training {MODEL_NAME} at {datetime.now()}")
"""


def test_fix_file_with_realistic_notebook(notebook):
    filepath = notebook.write(REALISTIC_NOTEBOOK)

    assert fix_file(filepath) is True
    content = notebook.read()
    assert content == REALISTIC_NOTEBOOK_EXPECTED


def test_fix_file_with_realistic_notebook_is_idempotent(notebook):
    filepath = notebook.write(REALISTIC_NOTEBOOK)

    assert fix_file(filepath) is True
    first_pass = notebook.read()
    assert first_pass == REALISTIC_NOTEBOOK_EXPECTED
    assert fix_file(filepath) is False
    second_pass = notebook.read()
    assert first_pass == second_pass


def test_main_check_mode_with_realistic_notebook_reports_all_issues(
    tmp_path, capsys, monkeypatch,
):
    path = tmp_path / "notebook.py"
    path.write_text(REALISTIC_NOTEBOOK)

    monkeypatch.setattr("sys.argv", ["fix-databricks-magic", str(path)])
    assert main() == 1

    captured = capsys.readouterr()
    # Should report diagnostics for: conditional pip cell, for-loop cell, try/except cell
    assert "%pip install -U" in captured.out or "block containing magic" in captured.out
    assert "%pip install {pkg}" in captured.out or "block containing magic" in captured.out
    assert "%pip install bitsandbytes" in captured.out or "block containing magic" in captured.out
    # Clean cells should NOT appear in diagnostics
    assert "import os" not in captured.out
    assert "MODEL_NAME" not in captured.out


def test_main_fix_mode_with_realistic_notebook_fixes_and_is_idempotent(
    tmp_path, capsys, monkeypatch,
):
    path = tmp_path / "notebook.py"
    path.write_text(REALISTIC_NOTEBOOK)

    monkeypatch.setattr("sys.argv", ["fix-databricks-magic", "--fix", str(path)])
    assert main() == 1
    captured = capsys.readouterr()
    assert "Fixed magic commands in:" in captured.out
    assert path.read_text() == REALISTIC_NOTEBOOK_EXPECTED

    # Second run: no changes needed
    monkeypatch.setattr("sys.argv", ["fix-databricks-magic", "--fix", str(path)])
    assert main() == 0
