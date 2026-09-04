import os
import sys
from pathlib import Path

import anthropic
from anthropic import Anthropic
from dotenv import load_dotenv


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def main():
    load_dotenv(BACKEND_ROOT / ".env")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    model = os.environ.get("ANTHROPIC_MODEL")
    if not api_key or api_key == "your_key_here":
        print("FAILURE: ANTHROPIC_API_KEY is not configured")
        return 1
    if not model or model == "your-supported-claude-model":
        print("FAILURE: ANTHROPIC_MODEL is not configured")
        return 1

    try:
        client = Anthropic(api_key=api_key)
        client.messages.create(
            model=model,
            max_tokens=8,
            temperature=0,
            messages=[{"role": "user", "content": "Reply with OK."}],
        )
    except anthropic.AuthenticationError:
        print("FAILURE: authentication failed")
        return 1
    except anthropic.RateLimitError:
        print("FAILURE: rate limit exceeded")
        return 1
    except anthropic.APIConnectionError:
        print("FAILURE: connection failed")
        return 1
    except anthropic.APIStatusError as exc:
        print(f"FAILURE: provider returned status {exc.status_code}")
        return 1
    except anthropic.APIError:
        print("FAILURE: provider request failed")
        return 1

    print("SUCCESS: Anthropic test call completed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
