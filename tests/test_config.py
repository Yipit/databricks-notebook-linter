from __future__ import annotations

import textwrap

import pytest

from databricks_notebook_linter.config import ConfigError, load_config

BASE = {"DNL001", "DNL002", "DNL003", "DNL004"}


@pytest.fixture
def project(tmp_path):
    """Write a pyproject.toml into tmp_path and load the config from it."""

    def _write(body: str):
        path = tmp_path / "pyproject.toml"
        path.write_text(textwrap.dedent(body))
        return load_config(str(path))

    _write.root = tmp_path
    return _write


# --- discovery -----------------------------------------------------------


def test_load_config_when_no_pyproject_returns_none(tmp_path):
    assert load_config(start_dir=str(tmp_path)) is None


def test_load_config_when_no_tool_section_returns_none(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
    assert load_config(start_dir=str(tmp_path)) is None


def test_load_config_discovers_pyproject_in_parent_directory(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[tool.databricks-notebook-linter]\nselect = ["DNL001"]\n'
    )
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)

    config = load_config(start_dir=str(nested))
    assert config is not None
    assert config.select == ("DNL001",)
    assert config.root == tmp_path


def test_load_config_when_explicit_path_missing_raises(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(str(tmp_path / "nope.toml"))


def test_load_config_when_explicit_path_lacks_tool_section_returns_none(tmp_path):
    path = tmp_path / "custom.toml"
    path.write_text('[project]\nname = "x"\n')
    assert load_config(str(path)) is None


def test_load_config_when_toml_is_malformed_raises(tmp_path):
    path = tmp_path / "pyproject.toml"
    path.write_text("[tool.databricks-notebook-linter\nselect = [")
    with pytest.raises(ConfigError, match="invalid TOML"):
        load_config(str(path))


# --- top level keys ------------------------------------------------------


def test_load_config_reads_select_and_ignore(project):
    config = project("""\
        [tool.databricks-notebook-linter]
        select = ["DNL001", "DNL005"]
        ignore = ["DNL003"]
    """)

    assert config.select == ("DNL001", "DNL005")
    assert config.ignore == ("DNL003",)


def test_load_config_when_keys_absent_leaves_them_none(project):
    config = project("[tool.databricks-notebook-linter]\n")
    assert config.select is None
    assert config.ignore is None
    assert config.per_path == ()


def test_load_config_when_unknown_top_level_key_raises(project):
    with pytest.raises(ConfigError, match="unknown key 'selct'"):
        project("""\
            [tool.databricks-notebook-linter]
            selct = ["DNL001"]
        """)


def test_load_config_when_select_is_not_a_list_raises(project):
    with pytest.raises(ConfigError, match="'select' must be a list of strings"):
        project("""\
            [tool.databricks-notebook-linter]
            select = "DNL001"
        """)


def test_load_config_when_select_contains_non_string_raises(project):
    with pytest.raises(ConfigError, match="'select' must be a list of strings"):
        project("""\
            [tool.databricks-notebook-linter]
            select = ["DNL001", 5]
        """)


def test_load_config_when_tool_section_is_not_a_table_raises(project):
    with pytest.raises(ConfigError, match="must be a table"):
        project("""\
            [tool]
            databricks-notebook-linter = 3
        """)


# --- per-path validation -------------------------------------------------


def test_load_config_when_per_path_is_not_a_list_raises(project):
    with pytest.raises(ConfigError, match="'per-path' must be a list"):
        project("""\
            [tool.databricks-notebook-linter]
            per-path = "notebooks/"
        """)


def test_load_config_when_per_path_entry_is_not_a_table_raises(project):
    with pytest.raises(ConfigError, match="'per-path' entries must be tables"):
        project("""\
            [tool.databricks-notebook-linter]
            per-path = ["notebooks/"]
        """)


def test_load_config_when_per_path_entry_has_no_paths_raises(project):
    with pytest.raises(ConfigError, match="requires a non-empty 'paths'"):
        project("""\
            [[tool.databricks-notebook-linter.per-path]]
            extend-select = ["DNL005"]
        """)


def test_load_config_when_per_path_paths_is_empty_raises(project):
    with pytest.raises(ConfigError, match="requires a non-empty 'paths'"):
        project("""\
            [[tool.databricks-notebook-linter.per-path]]
            paths = []
            extend-select = ["DNL005"]
        """)


def test_load_config_when_per_path_regex_is_invalid_raises(project):
    with pytest.raises(ConfigError, match="invalid regex"):
        project("""\
            [[tool.databricks-notebook-linter.per-path]]
            paths = ["notebooks/(config"]
            extend-select = ["DNL005"]
        """)


def test_load_config_when_per_path_has_unknown_key_raises(project):
    with pytest.raises(ConfigError, match="unknown key 'extend-ignore'"):
        project("""\
            [[tool.databricks-notebook-linter.per-path]]
            paths = ["notebooks/"]
            extend-ignore = ["DNL005"]
        """)


def test_load_config_when_per_path_select_is_not_a_list_raises(project):
    with pytest.raises(ConfigError, match="'select' must be a list of strings"):
        project("""\
            [[tool.databricks-notebook-linter.per-path]]
            paths = ["notebooks/"]
            select = 3
        """)


# --- referenced codes ----------------------------------------------------


def test_referenced_codes_collects_every_code_in_the_file(project):
    config = project("""\
        [tool.databricks-notebook-linter]
        select = ["DNL001"]
        ignore = ["DNL002"]

        [[tool.databricks-notebook-linter.per-path]]
        paths = ["a/"]
        extend-select = ["DNL005"]

        [[tool.databricks-notebook-linter.per-path]]
        paths = ["b/"]
        select = ["DNL003"]
        ignore = ["DNL004"]
    """)

    assert config.referenced_codes() == {
        "DNL001",
        "DNL002",
        "DNL003",
        "DNL004",
        "DNL005",
    }


def test_referenced_codes_when_nothing_configured_is_empty(project):
    config = project("[tool.databricks-notebook-linter]\n")
    assert config.referenced_codes() == set()


# --- per-path resolution -------------------------------------------------


def test_rules_for_when_no_per_path_returns_base(project):
    config = project("""\
        [tool.databricks-notebook-linter]
        select = ["DNL001"]
    """)

    assert config.rules_for("notebooks/a.py", BASE) == BASE


def test_rules_for_when_path_matches_extend_select_adds_rule(project):
    config = project("""\
        [[tool.databricks-notebook-linter.per-path]]
        paths = ["^notebooks/config/"]
        extend-select = ["DNL005"]
    """)

    assert config.rules_for("notebooks/config/a.py", BASE) == BASE | {"DNL005"}


def test_rules_for_when_path_does_not_match_leaves_base_unchanged(project):
    config = project("""\
        [[tool.databricks-notebook-linter.per-path]]
        paths = ["^notebooks/config/"]
        extend-select = ["DNL005"]
    """)

    assert config.rules_for("notebooks/other/a.py", BASE) == BASE


def test_rules_for_when_select_given_replaces_base(project):
    config = project("""\
        [[tool.databricks-notebook-linter.per-path]]
        paths = ["^scratch/"]
        select = ["DNL001"]
    """)

    assert config.rules_for("scratch/a.py", BASE) == {"DNL001"}


def test_rules_for_when_ignore_given_removes_from_base(project):
    config = project("""\
        [[tool.databricks-notebook-linter.per-path]]
        paths = ["^vendor/"]
        ignore = ["DNL002", "DNL003"]
    """)

    assert config.rules_for("vendor/a.py", BASE) == {"DNL001", "DNL004"}


def test_rules_for_applies_matching_entries_in_order(project):
    config = project("""\
        [[tool.databricks-notebook-linter.per-path]]
        paths = ["^notebooks/"]
        extend-select = ["DNL005"]

        [[tool.databricks-notebook-linter.per-path]]
        paths = ["^notebooks/legacy/"]
        ignore = ["DNL005"]
    """)

    assert config.rules_for("notebooks/a.py", BASE) == BASE | {"DNL005"}
    assert config.rules_for("notebooks/legacy/a.py", BASE) == BASE


def test_rules_for_matches_any_of_several_patterns(project):
    config = project("""\
        [[tool.databricks-notebook-linter.per-path]]
        paths = ["^jobs/", "^notebooks/config/"]
        extend-select = ["DNL005"]
    """)

    assert "DNL005" in config.rules_for("jobs/a.py", BASE)
    assert "DNL005" in config.rules_for("notebooks/config/a.py", BASE)
    assert "DNL005" not in config.rules_for("src/a.py", BASE)


def test_rules_for_supports_arbitrary_regex(project):
    config = project("""\
        [[tool.databricks-notebook-linter.per-path]]
        paths = ["^notebooks/[^/]+/config/.*\\\\.py$"]
        extend-select = ["DNL005"]
    """)

    assert "DNL005" in config.rules_for("notebooks/team/config/a.py", BASE)
    assert "DNL005" not in config.rules_for("notebooks/team/config/a.sql", BASE)


def test_rules_for_when_path_is_absolute_matches_relative_to_config_root(project):
    config = project("""\
        [[tool.databricks-notebook-linter.per-path]]
        paths = ["^notebooks/config/"]
        extend-select = ["DNL005"]
    """)

    absolute = project.root / "notebooks" / "config" / "a.py"
    assert "DNL005" in config.rules_for(str(absolute), BASE)


def test_rules_for_when_path_is_outside_config_root_uses_path_as_given(
    project, tmp_path_factory
):
    config = project("""\
        [[tool.databricks-notebook-linter.per-path]]
        paths = ["^notebooks/config/"]
        extend-select = ["DNL005"]
    """)

    outside = tmp_path_factory.mktemp("elsewhere") / "notebooks" / "config" / "a.py"
    assert "DNL005" not in config.rules_for(str(outside), BASE)
