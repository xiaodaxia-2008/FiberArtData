# Python Script
- **Never** install packages to the global Python environment via `pip install`.
- Use **uv script mode** ([PEP 723](https://peps.python.org/pep-0723/)) with
  inline dependency declarations.
- Place one-off scripts in `temp/`.
- place reusable scripts in `Scripts/`

```python
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
# ... script body ...
```

Run with:
```bash
uv run temp/my_script.py
```

> **Note**: `uv` automatically creates an isolated environment, downloads de-
> pendencies, and caches them. No global installation, no venv management.