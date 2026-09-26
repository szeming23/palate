import os

from dotenv import load_dotenv

load_dotenv()

GOOGLE_PLACES_API_KEY = os.environ.get("GOOGLE_PLACES_API_KEY", "")
DB_PATH = os.environ.get("PALATE_DB_PATH", "palate.db")

# How many past chat turns to send back to the model each request.
HISTORY_TURNS = 20

# Daily limits reset at midnight in this timezone.
TIMEZONE = "Asia/Singapore"


def _load_llm_keys() -> dict[str, tuple[str, str]]:
    """Named LLM keys from env vars of the form PALATE_KEY_<NAME>=<provider>:<secret>.

    PALATE_KEY_ANTHROPIC_MAIN=anthropic:sk-ant-...  ->  {"anthropic-main": ("anthropic", "sk-ant-...")}
    """
    keys = {}
    for var, value in os.environ.items():
        if not var.startswith("PALATE_KEY_") or not value:
            continue
        name = var.removeprefix("PALATE_KEY_").lower().replace("_", "-")
        provider, sep, secret = value.partition(":")
        if not sep or not secret:
            raise RuntimeError(f"{var} must look like '<provider>:<secret>', e.g. 'anthropic:sk-ant-...'")
        keys[name] = (provider.strip().lower(), secret.strip())
    return keys


# name -> (provider, secret)
LLM_KEYS = _load_llm_keys()
