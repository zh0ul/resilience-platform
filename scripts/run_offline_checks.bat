@ECHO OFF

ECHO === Running Ruff checks ===
.\.venv\Scripts\ruff.exe check .
ECHO.
ECHO === Running MyPy checks ===
.\.venv\Scripts\mypy.exe src
ECHO.
ECHO === Running Pytest tests ===
 .\.venv\Scripts\pytest.exe tests/unit tests/rest -v
