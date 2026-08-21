"""main() integration with pyproject.toml configuration and per-path scoping."""

from __future__ import annotations

import textwrap

import pytest

from databricks_notebook_linter.fix_magic import main

WIDGET_NOTEBOOK = '# Databricks notebook source\nenv = dbutils.widgets.get("env")\n'
MAGIC_NOTEBOOK = "# Databricks notebook source\n%pip install foo\n"

# DNL001-DNL004 everywhere, DNL005 only under notebooks/config/.
SCOPED_CONFIG = """\
    [tool.databricks-notebook-linter]
    select = ["DNL001", "DNL002", "DNL003", "DNL004"]

    [[tool.databricks-notebook-linter.per-path]]
    paths = ["^notebooks/config/"]
    extend-select = ["DNL005"]
"""


@pytest.fixture
def repo(tmp_path):
    """A fake repo root with a config file and notebooks at arbitrary paths."""

    class Repo:
        root = tmp_path

        def config(self, body: str) -> str:
            path = tmp_path / "pyproject.toml"
            path.write_text(textwrap.dedent(body))
            return str(path)

        def notebook(self, relative: str, content: str) -> str:
            path = tmp_path / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
            return str(path)

    return Repo()


def test_main_when_per_path_enables_rule_inside_scope_reports_it(
    repo, capsys, monkeypatch
):
    # Given: DNL005 scoped to notebooks/config/, and a notebook inside it
    config = repo.config(SCOPED_CONFIG)
    notebook = repo.notebook("notebooks/config/settings.py", WIDGET_NOTEBOOK)

    # When
    monkeypatch.setattr(
        "sys.argv", ["fix-databricks-magic", "--config", config, notebook]
    )
    exit_code = main()

    # Then
    assert exit_code == 1
    assert "[DNL005]" in capsys.readouterr().out


def test_main_when_per_path_rule_is_out_of_scope_does_not_report_it(
    repo, capsys, monkeypatch
):
    config = repo.config(SCOPED_CONFIG)
    notebook = repo.notebook("notebooks/etl/load.py", WIDGET_NOTEBOOK)

    monkeypatch.setattr(
        "sys.argv", ["fix-databricks-magic", "--config", config, notebook]
    )
    assert main() == 0
    assert capsys.readouterr().out == ""


def test_main_when_out_of_scope_still_applies_repository_wide_rules(
    repo, capsys, monkeypatch
):
    config = repo.config(SCOPED_CONFIG)
    notebook = repo.notebook("notebooks/etl/load.py", MAGIC_NOTEBOOK)

    monkeypatch.setattr(
        "sys.argv", ["fix-databricks-magic", "--config", config, notebook]
    )
    assert main() == 1
    assert "[DNL001]" in capsys.readouterr().out


def test_main_when_config_only_has_per_path_uses_default_rules_as_base(
    repo, capsys, monkeypatch
):
    config = repo.config("""\
        [[tool.databricks-notebook-linter.per-path]]
        paths = ["^notebooks/config/"]
        extend-select = ["DNL005"]
    """)
    notebook = repo.notebook("notebooks/config/settings.py", WIDGET_NOTEBOOK)

    monkeypatch.setattr(
        "sys.argv", ["fix-databricks-magic", "--config", config, notebook]
    )
    assert main() == 1
    assert "[DNL005]" in capsys.readouterr().out


def test_main_when_per_path_select_replaces_base_rules(repo, capsys, monkeypatch):
    config = repo.config("""\
        [[tool.databricks-notebook-linter.per-path]]
        paths = ["^scratch/"]
        select = ["DNL005"]
    """)
    notebook = repo.notebook("scratch/play.py", MAGIC_NOTEBOOK)

    monkeypatch.setattr(
        "sys.argv", ["fix-databricks-magic", "--config", config, notebook]
    )
    assert main() == 0
    assert capsys.readouterr().out == ""


def test_main_when_config_ignores_a_rule_it_does_not_run(repo, monkeypatch):
    config = repo.config("""\
        [tool.databricks-notebook-linter]
        ignore = ["DNL001", "DNL002"]
    """)
    notebook = repo.notebook("notebooks/a.py", MAGIC_NOTEBOOK)

    monkeypatch.setattr(
        "sys.argv", ["fix-databricks-magic", "--config", config, notebook]
    )
    assert main() == 0


def test_main_when_cli_select_given_it_overrides_config_select(repo, monkeypatch):
    config = repo.config("""\
        [tool.databricks-notebook-linter]
        select = ["DNL001"]
    """)
    notebook = repo.notebook("notebooks/a.py", MAGIC_NOTEBOOK)

    monkeypatch.setattr(
        "sys.argv",
        ["fix-databricks-magic", "--config", config, "--select", "DNL003", notebook],
    )
    assert main() == 0


def test_main_when_no_config_flag_given_config_is_ignored(repo, monkeypatch):
    config = repo.config(SCOPED_CONFIG)
    notebook = repo.notebook("notebooks/config/settings.py", WIDGET_NOTEBOOK)

    monkeypatch.setattr(
        "sys.argv",
        ["fix-databricks-magic", "--config", config, "--no-config", notebook],
    )
    assert main() == 0


def test_main_when_config_references_unknown_rule_code_returns_2(
    repo, capsys, monkeypatch
):
    config = repo.config("""\
        [[tool.databricks-notebook-linter.per-path]]
        paths = ["^notebooks/"]
        extend-select = ["DNL999"]
    """)

    monkeypatch.setattr("sys.argv", ["fix-databricks-magic", "--config", config])
    assert main() == 2
    assert "DNL999" in capsys.readouterr().err


def test_main_when_config_file_is_missing_returns_2(repo, capsys, monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        ["fix-databricks-magic", "--config", str(repo.root / "absent.toml")],
    )
    assert main() == 2
    assert "not found" in capsys.readouterr().err


def test_main_when_config_is_malformed_returns_2(repo, capsys, monkeypatch):
    config = repo.config("[tool.databricks-notebook-linter]\nselect = [\n")

    monkeypatch.setattr("sys.argv", ["fix-databricks-magic", "--config", config])
    assert main() == 2
    assert "invalid TOML" in capsys.readouterr().err


# --- fix mode with a check-only rule -------------------------------------


def test_main_fix_mode_when_unfixable_rule_violated_returns_1(
    repo, capsys, monkeypatch
):
    """DNL005 has no autofix, so --fix must still fail the run."""
    config = repo.config(SCOPED_CONFIG)
    notebook = repo.notebook("notebooks/config/settings.py", WIDGET_NOTEBOOK)

    monkeypatch.setattr(
        "sys.argv", ["fix-databricks-magic", "--fix", "--config", config, notebook]
    )
    assert main() == 1

    out = capsys.readouterr().out
    assert "[DNL005]" in out
    assert "Fixed" not in out


def test_main_fix_mode_leaves_unfixable_violation_in_place(repo, monkeypatch):
    config = repo.config(SCOPED_CONFIG)
    notebook = repo.notebook("notebooks/config/settings.py", WIDGET_NOTEBOOK)

    monkeypatch.setattr(
        "sys.argv", ["fix-databricks-magic", "--fix", "--config", config, notebook]
    )
    main()

    with open(notebook) as f:
        assert f.read() == WIDGET_NOTEBOOK


def test_main_fix_mode_reports_fixes_and_unfixable_violations_together(
    repo, capsys, monkeypatch
):
    config = repo.config(SCOPED_CONFIG)
    notebook = repo.notebook(
        "notebooks/config/settings.py",
        '# Databricks notebook source\n%pip install foo\nenv = dbutils.widgets.get("e")\n',
    )

    monkeypatch.setattr(
        "sys.argv", ["fix-databricks-magic", "--fix", "--config", config, notebook]
    )
    assert main() == 1

    out = capsys.readouterr().out
    assert "Fixed [DNL001]:" in out
    assert "[DNL005]" in out


def test_main_fix_mode_when_unfixable_rule_is_clean_returns_0(repo, monkeypatch):
    config = repo.config(SCOPED_CONFIG)
    notebook = repo.notebook(
        "notebooks/config/settings.py",
        "# Databricks notebook source\nenv = CONFIG[\"env\"]\n",
    )

    monkeypatch.setattr(
        "sys.argv", ["fix-databricks-magic", "--fix", "--config", config, notebook]
    )
    assert main() == 0


def test_main_list_rules_marks_off_by_default_rules(capsys, monkeypatch):
    monkeypatch.setattr("sys.argv", ["fix-databricks-magic", "--list-rules"])
    assert main() == 0

    lines = capsys.readouterr().out.splitlines()
    by_code = {line.split()[0]: line for line in lines}
    assert " on " in by_code["DNL001"]
    assert " off " in by_code["DNL005"]
    assert "no-widget-config" in by_code["DNL005"]


def test_main_discovers_pyproject_from_working_directory(repo, capsys, monkeypatch):
    """The pre-commit path: no --config, cwd is the repo root."""
    repo.config(SCOPED_CONFIG)
    repo.notebook("notebooks/config/settings.py", WIDGET_NOTEBOOK)

    monkeypatch.chdir(repo.root)
    monkeypatch.setattr(
        "sys.argv", ["fix-databricks-magic", "notebooks/config/settings.py"]
    )
    assert main() == 1
    assert "[DNL005]" in capsys.readouterr().out
