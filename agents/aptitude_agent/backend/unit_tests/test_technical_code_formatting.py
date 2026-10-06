import pytest

from backend.app.services.question_validation import validate_generated_item
from backend.app.utils.code_formatting import decode_literal_layout, normalize_fenced_text


TECHNICAL_SLOT={"category":"Technical Aptitude","topic":"Programming Fundamentals","difficulty":"Easy"}


def technical_item(question):
    return {
        "question":question,
        "options":{"A":"3","B":"4","C":"5","D":"Error"},
        "correct_answer":"A",
        "explanation":"The function adds both values, so the answer is 3.",
        **TECHNICAL_SLOT,
    }


def test_preserves_fenced_code_indentation_and_language():
    question="""What is printed by this program?
```python
def add(a, b):
    return a + b

print(add(1, 2))
```"""

    validated=validate_generated_item(technical_item(question),TECHNICAL_SLOT)

    assert "```python\ndef add(a, b):\n    return a + b" in validated["question"]
    assert validated["question"].endswith("print(add(1, 2))\n```")


def test_converts_json_safe_structured_code_to_fenced_public_text():
    item=technical_item("What is printed by this program?")
    item["question_code"]={
        "language":"python",
        "code":"def add(a, b):\n    return a + b\n\nprint(add(1, 2))",
    }

    validated=validate_generated_item(item,TECHNICAL_SLOT)

    assert validated["question"]==(
        "What is printed by this program?\n\n"
        "```python\n"
        "def add(a, b):\n"
        "    return a + b\n\n"
        "print(add(1, 2))\n"
        "```"
    )


def test_labels_complete_unlabelled_block_with_selected_language():
    slot={**TECHNICAL_SLOT,"technical_language":"Java"}
    item={
        **technical_item("""What is printed by this program?
```
System.out.println(3);
```"""),
        **slot,
    }

    validated=validate_generated_item(item,slot)

    assert "```java\nSystem.out.println(3);\n```" in validated["question"]


def test_structured_code_discards_duplicate_markdown_from_prose():
    slot={**TECHNICAL_SLOT,"technical_language":"Python"}
    item={
        **technical_item("""What is printed?
```
print(3)
```"""),
        **slot,
        "question_code":{"language":"python","code":"print(3)"},
    }

    validated=validate_generated_item(item,slot)

    assert validated["question"]=="What is printed?\n\n```python\nprint(3)\n```"


def test_rejects_code_in_a_language_other_than_selected():
    slot={**TECHNICAL_SLOT,"technical_language":"Java"}
    item={
        **technical_item("""What is printed?
```python
print(3)
```"""),
        **slot,
    }

    with pytest.raises(ValueError,match="technical code language must be java"):
        validate_generated_item(item,slot)


def test_rejects_unfenced_program_code_for_technical_questions():
    question="What is printed? def add(a, b): return a + b; print(add(1, 2))"

    with pytest.raises(ValueError,match="fenced code block"):
        validate_generated_item(technical_item(question),TECHNICAL_SLOT)


def test_allows_single_inline_code_reference_in_technical_prose():
    question="What does print() do in Python?"
    assert validate_generated_item(technical_item(question),TECHNICAL_SLOT)["question"]==question


def test_multiline_bare_code_is_fenced_instead_of_failing_the_test():
    # The model sometimes writes a question's code on plain lines and repeats
    # it on every retry; one such question used to fail a whole Mixed Test.
    question="What is the output?\ndef add(a, b):\n    return a + b\nprint(add(1, 2))"
    stored=validate_generated_item(technical_item(question),TECHNICAL_SLOT)["question"]
    assert stored=="What is the output?\n\n```python\ndef add(a, b):\n    return a + b\nprint(add(1, 2))\n```"


@pytest.mark.parametrize("question,expected_code", [
    ("What is the output of the following code?\nprint(type([]) == list)", "print(type([]) == list)"),
    ("Consider the code below:\nx = [1, 2, 3]\nfor i in x:\n    print(i * 2)\nWhat is printed last?", "x = [1, 2, 3]\nfor i in x:\n    print(i * 2)"),
])
def test_bare_code_around_prose_becomes_one_fenced_block(question,expected_code):
    stored=validate_generated_item(technical_item(question),TECHNICAL_SLOT)["question"]
    assert f"```python\n{expected_code}\n```" in stored
    assert stored.count("```")==2


def test_the_repair_never_touches_valid_or_already_fenced_text():
    from backend.app.utils.code_formatting import fence_bare_code
    fenced="What does this print?\n\n```python\nprint(1)\n```"
    assert fence_bare_code(fenced,"python")==fenced
    prose="Which keyword defines a function in Python?\nChoose the best answer."
    assert fence_bare_code(prose,"python")==prose


def test_a_broken_fence_is_still_rejected():
    question="What is the output?\n```python\nprint(1)"
    with pytest.raises(ValueError,match="fenced code block"):
        validate_generated_item(technical_item(question),TECHNICAL_SLOT)


def test_nontechnical_content_is_not_subject_to_code_fence_validation():
    slot={"category":"Verbal Ability","topic":"Sentence Correction","difficulty":"Easy"}
    item={
        "question":"Which sentence correctly uses the word function in context?",
        "options":{"A":"The machine can function well.","B":"Function machine well.","C":"Well the function.","D":"A function the."},
        "correct_answer":"A",
        "explanation":"The first sentence uses function as a verb with a clear subject and adverb, so option A is correct.",
        **slot,
    }

    assert validate_generated_item(item,slot)["question"]==item["question"]


def test_normalizer_keeps_prose_outside_fence():
    value="Question prose\n\n```javascript\nfunction add(a, b) {\n  return a + b;\n}\n```\n\nMore prose"

    assert normalize_fenced_text(value)==value


def test_decodes_double_escaped_layout_without_changing_lone_code_escape():
    broken=r'Consider this C code:\\n\\n#include <stdio.h>\\nint main() {\\n    return 0;\\n}'
    decoded=decode_literal_layout(broken)

    assert decoded.startswith("Consider this C code:\n\n#include <stdio.h>\n")
    assert "\\n" not in decoded
    source=r'printf("%d\n", result);'
    assert decode_literal_layout(source)==source


def test_validates_double_escaped_unlabelled_code_block():
    slot={**TECHNICAL_SLOT,"technical_language":"C"}
    item={
        **technical_item(r'What is printed?\\n\\n```\\n#include <stdio.h>\\nint main() { return 0; }\\n```'),
        **slot,
    }

    validated=validate_generated_item(item,slot)

    assert "```c\n#include <stdio.h>\nint main() { return 0; }\n```" in validated["question"]


def test_a_code_layout_failure_gets_a_targeted_retry_and_a_no_code_final_retry():
    from backend.app.services.test_generation import _retry_context
    error = ValueError("question 6: technical code must be inside a language-labelled fenced code block")
    second = _retry_context("BASE", error, [], 1, final=False)
    assert "CODE LAYOUT:" in second and "question_code" in second and "NO program code" not in second
    final = _retry_context("BASE", error, [], 2, final=True)
    assert "CODE LAYOUT, FINAL" in final and "NO program code" in final
    other = _retry_context("BASE", ValueError("options must be unique and non-empty"), [], 2, final=True)
    assert "CODE LAYOUT" not in other


def test_a_conceptual_technical_question_without_code_is_valid():
    slot = {"category": "Technical Aptitude", "topic": "Advanced Recursion", "difficulty": "Medium"}
    item = {
        "question": "Which condition stops a recursive function from calling itself forever?",
        "options": {"A": "The base case", "B": "The recursive case", "C": "A global variable", "D": "The call stack size"},
        "correct_answer": "A",
        "explanation": "A recursive function needs a base case that returns without recursing, which ends the chain of calls.",
        **slot,
    }
    assert validate_generated_item(item, slot)["question"].startswith("Which condition")


def test_bare_code_after_a_fenced_block_is_fenced_too():
    question = "What does this print?\n```python\nprint(1)\n```\nprint(2)\nprint(3)"
    stored = validate_generated_item(technical_item(question), TECHNICAL_SLOT)["question"]
    assert stored.count("```") == 4 and "```python\nprint(2)\nprint(3)\n```" in stored
