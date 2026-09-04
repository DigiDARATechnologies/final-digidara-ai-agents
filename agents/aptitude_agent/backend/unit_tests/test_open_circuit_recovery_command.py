from pathlib import Path


def test_bank_recovery_commands_are_not_registered():
    source=(Path(__file__).resolve().parents[1]/"app"/"__init__.py").read_text(encoding="utf-8")
    assert "recover-open-circuit-bank-jobs" not in source
    assert "seed-question-bank" not in source
    assert "retry-bank-jobs" not in source
