"""Human-readable assessment labels derived from persisted questions."""


__test__ = False

def test_label(test):
    if getattr(test,"test_mode","mixed")=="category_practice":
        return f"{test.selected_category} Practice · {test.selected_level}"
    if getattr(test,"focus_category",None):
        return f"{test.focus_category} Practice"
    categories={question.category for question in test.questions if question.category}
    if test.total_questions<20 and len(categories)==1:
        return f"{next(iter(categories))} Practice"
    return "Mixed Aptitude Assessment"
