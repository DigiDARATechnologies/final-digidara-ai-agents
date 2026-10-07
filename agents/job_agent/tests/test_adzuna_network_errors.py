"""A network blip is retried, and no Adzuna error ever carries the API key."""
import traceback
from unittest.mock import MagicMock, patch

import pytest
import requests

from job_agent.providers.adzuna import AdzunaAPIError, fetch_and_normalize

SECRET_ID, SECRET_KEY = "ac26e503", "1ed8899214a6e6c8da6df1fa6df6a2ca"
LEAKY = requests.ConnectionError(
    f"HTTPSConnectionPool(host='api.adzuna.com', port=443): Max retries exceeded with url: "
    f"/v1/api/jobs/in/search/1?app_id={SECRET_ID}&app_key={SECRET_KEY} [Errno 101] Network is unreachable"
)


@pytest.fixture(autouse=True)
def credentials():
    with patch("job_agent.providers.adzuna._credentials", return_value=(SECRET_ID, SECRET_KEY)):
        yield


def ok_response():
    return MagicMock(status_code=200, json=lambda: {"results": []})


def test_a_dropped_connection_is_retried_and_then_succeeds():
    session, pauses = MagicMock(), []
    session.get.side_effect = [LEAKY, LEAKY, ok_response()]
    assert fetch_and_normalize("Data Analyst", "Chennai", session=session, sleep=pauses.append) == []
    assert session.get.call_count == 3 and pauses == [2, 5]


def test_it_gives_up_after_three_attempts_without_revealing_the_key():
    session = MagicMock()
    session.get.side_effect = LEAKY
    with pytest.raises(AdzunaAPIError) as caught:
        fetch_and_normalize("Data Analyst", "Chennai", session=session, sleep=lambda _: None)
    assert session.get.call_count == 3
    assert "Could not connect to Adzuna" in str(caught.value)
    # Not in the message, and not in the traceback the worker logs (no chained cause).
    logged = "".join(traceback.format_exception(caught.value))
    assert SECRET_KEY not in logged and SECRET_ID not in logged
    assert caught.value.__cause__ is None and caught.value.__suppress_context__


@pytest.mark.parametrize("error", [requests.Timeout(f"read timed out app_key={SECRET_KEY}"),
                                   requests.TooManyRedirects(f"app_key={SECRET_KEY}")])
def test_other_request_errors_do_not_reveal_the_key_either(error):
    session = MagicMock()
    session.get.side_effect = error
    with pytest.raises(AdzunaAPIError) as caught:
        fetch_and_normalize("Data Analyst", "Chennai", session=session, sleep=lambda _: None)
    assert SECRET_KEY not in "".join(traceback.format_exception(caught.value))
    assert session.get.call_count == 1          # only connection failures are retried


def test_the_free_plan_counts_one_call_however_many_retries():
    session, reserve = MagicMock(), MagicMock()
    session.get.side_effect = [LEAKY, ok_response()]
    fetch_and_normalize("Data Analyst", "Chennai", session=session, sleep=lambda _: None, before_request=reserve)
    reserve.assert_called_once()
