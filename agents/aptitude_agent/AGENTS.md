# AptiDARA workspace instructions

## Python environment

- The project virtual environment is `.venv` and uses Python 3.12.8 from
  `C:\Users\DELL\AppData\Local\Programs\Python\Python312`.
- Always invoke project tooling explicitly, for example:
  `D:\Aptitude_ai_agent\.venv\Scripts\python.exe -m pytest`.
- In a managed Codex sandbox, the base interpreter is outside the writable
  workspace. If the venv launcher reports `No Python at ...Python312`, rerun
  the same command with the required filesystem escalation. That message in
  the restricted sandbox does not mean the venv or base installation is
  missing.
- Do not recreate `.venv` solely because the restricted sandbox cannot read
  its base interpreter. First verify `pyvenv.cfg` and the base executable with
  an approved read-only check.

## Test database safety

- Backend integration tests require `TEST_DATABASE_URL` to reference a
  dedicated MySQL database whose name ends in `_test`.
- Never point tests at `aptitude_ai_dev`; the test fixtures delete table data.
