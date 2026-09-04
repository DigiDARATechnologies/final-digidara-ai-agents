from backend.app.utils.explanation import normalize_explanation


EXPECTED = (
    "Step 1: 16 x 42 = 672.\n"
    "Step 2: 21 x 38 - 672 = 126.\n"
    "Step 3: Answer = 126."
)


def test_normalizes_legacy_inline_steps_to_separate_lines():
    value = (
        "Step 1: 16 x 42 = 672. "
        "Step 2: 21 x 38 - 672 = 126. "
        "Step 3: Answer = 126."
    )

    assert normalize_explanation(value) == EXPECTED


def test_preserves_canonical_newline_separated_steps():
    assert normalize_explanation(EXPECTED) == EXPECTED


def test_accepts_common_step_marker_variants_without_changing_content():
    value = "Step #1 - Identify the rule. Step 2) Apply the rule. Step 3. Answer = B."

    assert normalize_explanation(value) == (
        "Step 1: Identify the rule.\n"
        "Step 2: Apply the rule.\n"
        "Step 3: Answer = B."
    )


def test_plain_explanation_remains_a_plain_paragraph():
    value = "The pattern increases by two each time, so the correct answer is 10."

    assert normalize_explanation(value) == value
