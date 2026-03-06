from __future__ import annotations

import textwrap

import pytest


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
