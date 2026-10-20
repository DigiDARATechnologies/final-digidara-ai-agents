from backend.app.services.pdf_service import _plain


def test_math_symbols_print_as_text_not_question_marks():
    text = _plain("60 − 40, √16, ₹500, π ≈ 3.14, x⁴, H₂O")
    assert "?" not in text
    assert text == "60 - 40, sqrt(16), Rs. 500, pi ~= 3.14, x^4, H2O"
