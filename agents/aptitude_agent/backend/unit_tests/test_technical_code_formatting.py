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


def test_rejects_multiline_unfenced_program_code():
    question="What is the output?\ndef add(a, b):\n    return a + b"
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
