import json

import pytest
from flask import Flask

from backend.app.services import recommendation_service
from backend.app.services.groq_service import GroqProviderError


@pytest.mark.parametrize(
    "metrics",
    [
        {"score_trend":[{"label":"Test 1","score":100}],"categories":[],"strongest_area":"Logical Reasoning","focus_area":"Logical Reasoning"},
        {"score_trend":[{"label":"Test 1","score":0}],"categories":[],"strongest_area":"Quantitative Aptitude","focus_area":"Quantitative Aptitude"},
        {"score_trend":[{"label":"Test 1","score":50}],"categories":[],"strongest_area":"Verbal Ability","focus_area":"Logical Reasoning"},
    ],
)
def test_recommendation_handles_perfect_zero_and_mixed_metrics(monkeypatch,metrics):
    app=Flask(__name__)
    app.config.update(
        GROQ_MODEL="primary-model",GROQ_FALLBACK_MODELS=("fast-model",),
    )
    captured=[]

    def complete(system,prompt,**options):
        captured.append((system,json.loads(prompt),options))
        return "Practice the weakest topic with short daily drills.",{
            "model":"fast-model","input_tokens":1,"output_tokens":1,"total_tokens":2,
        }

    monkeypatch.setattr(recommendation_service,"text_completion",complete)
    with app.app_context():
        text,model,_usage=recommendation_service.generate_recommendation(metrics)

    assert text=="Practice the weakest topic with short daily drills."
    assert model=="fast-model"
    assert captured[0][1]==metrics
    assert captured[0][2]["models"]==["fast-model"]
    assert captured[0][2]["reasoning_effort"]=="low"
    assert captured[0][2]["maximum_tokens"]==512


def test_recommendation_tries_second_model_after_empty_response(monkeypatch):
    app=Flask(__name__)
    app.config.update(
        GROQ_MODEL="primary-model",GROQ_FALLBACK_MODELS=("fast-model",),
    )
    attempted=[]

    def complete(_system,_prompt,**options):
        model=options["models"][0];attempted.append(model)
        if model=="fast-model":
            raise GroqProviderError(
                "empty_response","finish_reason=length completion_tokens=256",True,
            )
        return "Review missed concepts, then attempt a timed mixed drill.",{
            "model":model,"input_tokens":1,"output_tokens":1,"total_tokens":2,
        }

    monkeypatch.setattr(recommendation_service,"text_completion",complete)
    with app.app_context():
        text,model,_usage=recommendation_service.generate_recommendation({})

    assert attempted==["fast-model","primary-model"]
    assert model=="primary-model"
    assert text.startswith("Review missed concepts")
