# Nila Home Store - Customer Support Reply Prompts

Three versions of a prompt that classifies a customer email and drafts a reply for
**Nila Home Store**, a hypothetical online home-goods shop. Each version is run on the
same 8 test emails and scored with the same 5 automatic checks, so the improvement
from one version to the next is measured, not guessed.

## What is in this folder

| Path | What it is |
|------|------------|
| `src/prompts/` | The three prompt versions: baseline, role + rules, few-shot + strict JSON |
| `data/test_cases.json` | 8 test emails with the expected category and whether a refund is allowed |
| `outputs/` | The model's response to every test email, for each prompt version |
| `src/checks.py` | The 5 checks: valid JSON, correct category, refund-safe, under 120 words, greeting and sign-off |
| `src/evaluate.py` | Scores every version and writes `results/scores.csv` |
| `results/scores.csv` | The scores |
| `tests/` | Tests for the checks |
| `output_screenshots/` | Screenshots of the comparison, a failure list and the tests passing |

## How to run

Python 3.10+, no packages needed except pytest for the tests.

```
python src/evaluate.py
python src/evaluate.py --failures v2_role_and_rules
python -m pytest -q
```

## How the outputs were produced

Each prompt in `src/prompts/` was sent once per test email with `{email}` replaced by the
email text, at temperature 0.2, and the raw response was saved in `outputs/`.
Saving them means the scores can be re-checked by anyone, without an API key, and give
the same result every time. To test a new prompt version, save its responses in the same
format and add its name to `VERSIONS` in `src/evaluate.py`.

## Results

| Version | Score |
|---------|-------|
| v1 baseline | 32.5% |
| v2 role and rules | 67.5% |
| v3 few-shot and strict JSON | 97.5% |
