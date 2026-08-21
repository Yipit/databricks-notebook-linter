from __future__ import annotations

from databricks_notebook_linter.fix_magic import main


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


def test_main_check_mode_when_issues_found_returns_1_and_prints_diagnostics(
    tmp_path,
    capsys,
    monkeypatch,
):
    path = tmp_path / "notebook.py"
    path.write_text("# Databricks notebook source\n%pip install foo\n")

    monkeypatch.setattr("sys.argv", ["fix-databricks-magic", str(path)])
    assert main() == 1

    captured = capsys.readouterr()
    assert "[DNL001]" in captured.out
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
    tmp_path,
    capsys,
    monkeypatch,
):
    path = tmp_path / "notebook.py"
    path.write_text("# Databricks notebook source\n%pip install foo\n")

    monkeypatch.setattr("sys.argv", ["fix-databricks-magic", "--fix", str(path)])
    assert main() == 1

    captured = capsys.readouterr()
    assert "Fixed [DNL001]:" in captured.out
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
        "sys.argv",
        ["fix-databricks-magic", str(clean), str(dirty)],
    )
    assert main() == 1

    captured = capsys.readouterr()
    assert "[DNL001]" in captured.out
    assert "%pip install foo" in captured.out
    assert "clean.py" not in captured.out


def test_main_list_rules_prints_catalog_and_returns_0(capsys, monkeypatch):
    monkeypatch.setattr("sys.argv", ["fix-databricks-magic", "--list-rules"])
    assert main() == 0

    captured = capsys.readouterr()
    assert "DNL001" in captured.out
    assert "DNL002" in captured.out
    assert "DNL003" in captured.out
    assert "DNL004" in captured.out
    assert "magic-prefix" in captured.out


def test_main_select_limits_rules(tmp_path, monkeypatch):
    path = tmp_path / "notebook.py"
    path.write_text("# Databricks notebook source\n%pip install foo\n")

    monkeypatch.setattr(
        "sys.argv",
        ["fix-databricks-magic", "--select", "DNL002", str(path)],
    )
    assert main() == 0


def test_main_ignore_disables_rules(tmp_path, monkeypatch):
    path = tmp_path / "notebook.py"
    path.write_text("# Databricks notebook source\n%pip install foo\n")

    monkeypatch.setattr(
        "sys.argv",
        ["fix-databricks-magic", "--ignore", "DNL001", str(path)],
    )
    assert main() == 0


def test_main_unknown_rule_code_returns_2(capsys, monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        ["fix-databricks-magic", "--select", "DNL999"],
    )
    assert main() == 2

    captured = capsys.readouterr()
    assert "DNL999" in captured.err


def test_main_fix_mode_with_select(tmp_path, monkeypatch):
    path = tmp_path / "notebook.py"
    path.write_text("# Databricks notebook source\n%pip install foo\n")

    monkeypatch.setattr(
        "sys.argv",
        ["fix-databricks-magic", "--fix", "--select", "DNL002", str(path)],
    )
    assert main() == 0
    assert path.read_text() == "# Databricks notebook source\n%pip install foo\n"


def test_main_list_rules_prints_in_numeric_code_order(capsys, monkeypatch):
    """ALL_RULES is in pipeline order; --list-rules must still read numerically."""
    monkeypatch.setattr("sys.argv", ["fix-databricks-magic", "--list-rules"])
    assert main() == 0

    codes = [line.split()[0] for line in capsys.readouterr().out.splitlines()]
    assert codes == sorted(codes)
    assert codes == ["DNL001", "DNL002", "DNL003", "DNL004", "DNL005"]
