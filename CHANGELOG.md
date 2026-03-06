# Changelog

## 0.1.0

Initial release.

- Fix bare magic commands (`%pip`, `%sql`, `%md`, `%sh`, `%fs`, `%run`, `%python`, `%r`, `%scala`) and shell bangs (`!`) in Databricks `.py`-format notebooks by prefixing with `# MAGIC`
- Handle multiline continuations (`\`)
- Handle block-level magic: `if`, `for`, `while`, `with`, `try` blocks containing magic are prefixed entirely
- Handle nested blocks up to arbitrary depth
- Handle compound blocks: `if/elif/else`, `try/except/finally` treated as single units
- Handle magic appearing only in secondary branches (`else`, `elif`, `except`, `finally`) by prefixing the entire compound block
- Check mode (default): report unfixed magic and exit 1
- Fix mode (`--fix`): rewrite files in place
- Pre-commit hook support
- 100% branch coverage test suite
