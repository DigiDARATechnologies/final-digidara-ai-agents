"""The writing report shows every score out of 10, in India time."""
from datetime import datetime

from app.services import writing_report


def test_chat_scores_on_the_100_scale_are_shown_out_of_10():
    # "Chat with AI" is scored 0-100: 60 used to print as "60 / 10".
    assert writing_report._out_of_ten(60) == 6.0
    assert writing_report._out_of_ten(7.5) == 7.5


def test_a_missing_score_is_a_dash_never_a_made_up_number():
    assert writing_report._out_of_ten(None) == "—"


def test_the_report_time_is_india_time():
    # 10:00 UTC is 3:30 PM IST.
    assert writing_report._ist(datetime(2026, 10, 21, 10, 0)).strftime("%I:%M %p") == "03:30 PM"
