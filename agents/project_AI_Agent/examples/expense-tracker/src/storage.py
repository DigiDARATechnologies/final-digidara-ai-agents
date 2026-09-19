"""JSON-file persistence for expenses."""
import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_PATH = DATA_DIR / "expenses.json"


def load_expenses(path=DEFAULT_PATH):
    """Return the saved expenses as a list of dicts (empty if none saved yet)."""
    path = Path(path)
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def save_expenses(expenses, path=DEFAULT_PATH):
    """Write the expenses list to disk, creating the folder if needed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(expenses, handle, indent=2)
