# Pull request: merge `test_branch` into `main`

## Summary

Merge the latest aptitude assessment and mock interview improvements into `main`.

## Changes

- Improves mock interview question generation, validation, scoring, and report handling.
- Removes new follow-up question generation while preserving historical report compatibility.
- Adds role and difficulty calibration coverage and related tests.
- Adds mock interview report PDF support.
- Updates mock interview and aptitude frontend flows and UI presentation.
- Adds repository test-artifact protections and frontend/backend test coverage.
- Includes the latest deployment and Judge0 configuration from `main`.

## Validation

- Docker Compose images rebuilt successfully.
- Full Compose stack restarted successfully.
- All agent services and the frontend reported healthy.
- Frontend health check returned HTTP 200.

## Branches

- Source: `test_branch`
- Target: `main`
