"""verify_password must never crash the request, whatever is stored in password_hash."""
import pytest

from app.auth.security import hash_password, verify_password


def test_a_correct_password_verifies_and_a_wrong_one_does_not():
    stored = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", stored) is True
    assert verify_password("wrong password", stored) is False


@pytest.mark.parametrize("corrupted", ["", "not-a-bcrypt-hash", "$2b$04$tooshort", "12345", "🙂" * 20])
def test_a_malformed_stored_hash_fails_the_check_instead_of_crashing(corrupted):
    # The live failure: bcrypt.checkpw raised ValueError("Invalid salt") for a
    # corrupted/legacy hash, which crashed /auth/login with a 500 instead of a
    # normal "incorrect password" 401.
    assert verify_password("anything", corrupted) is False
