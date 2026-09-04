def to_score10(score):
    if score is None:
        return None
    try:
        value = float(score)
    except (TypeError, ValueError):
        return None
    if value > 10:
        value = value / 10
    return round(max(0, min(value, 10)), 1)


def convert_scores_dict(scores):
    if not isinstance(scores, dict):
        return scores
    converted = {}
    for key, value in scores.items():
        converted[key] = to_score10(value) if key != "feedback" else value
    return converted
