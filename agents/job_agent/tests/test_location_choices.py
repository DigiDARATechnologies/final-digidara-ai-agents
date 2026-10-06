from job_agent.chat_service import (
    LOCATION_CHOICES,
    _next_onboarding_prompt,
    _with_location_choices,
    extract_locations_from_text,
    onboarding_actions,
)
from job_agent.providers.config_loader import get_prlabs_config

PROFILE_AT_LOCATION_STEP = {
    "full_name": "Prem", "skills": ["Python"], "experience_provided": True,
    "experience_years": 0, "preferred_titles": ["Python Developer"], "preferred_locations": [],
}


def test_the_location_question_offers_only_the_five_cities():
    step, prompt = _next_onboarding_prompt(PROFILE_AT_LOCATION_STEP)
    assert step == "preferred_locations"
    for city in LOCATION_CHOICES:
        assert f"**{city}**" in prompt
    assert "Bengaluru" not in prompt and "Any location" not in prompt
    assert [action["label"] for action in onboarding_actions(step)] == [
        "Chennai", "Coimbatore", "Madurai", "Tiruchirappalli", "Salem"]


def test_every_city_button_is_understood_as_that_city():
    for city in LOCATION_CHOICES:
        assert extract_locations_from_text(city) == [city]


def test_any_reply_asking_for_a_city_gets_the_buttons():
    reply = {"reply": "You haven't saved a preferred city yet. Which city would you like to work in?", "suggested_actions": []}
    assert [a["value"] for a in _with_location_choices(reply)["suggested_actions"]] == LOCATION_CHOICES
    other = {"reply": "Here are your jobs.", "suggested_actions": []}
    assert _with_location_choices(other)["suggested_actions"] == []
    kept = {"reply": "Which city would you like to work in?", "suggested_actions": [{"label": "x", "value": "x"}]}
    assert _with_location_choices(kept)["suggested_actions"] == [{"label": "x", "value": "x"}]


def test_other_steps_keep_their_buttons():
    assert onboarding_actions("resume") == [{"label": "Skip resume", "value": "skip"}]
    assert onboarding_actions("skills") == []


def test_prlabs_searches_the_state_and_each_offered_city():
    locations = list(dict.fromkeys(q["location"] for q in get_prlabs_config()["queries"]))
    assert sorted(locations) == sorted(["Tamil Nadu, India"] + [f"{city}, Tamil Nadu, India" for city in LOCATION_CHOICES])
