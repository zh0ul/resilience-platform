@ECHO OFF

ECHO === Running Pytest tests ===
 .\.venv\Scripts\pytest.exe tests/unit tests/rest -v
ECHO.
ECHO === Running Ruff checks ===
.\.venv\Scripts\ruff.exe check .
ECHO.
ECHO === Running MyPy checks ===
.\.venv\Scripts\mypy.exe src
