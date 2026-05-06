from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
SETTINGS_PATH = BASE_DIR / "settings.json"
PROMPTS_DIR = BASE_DIR / "prompts"
RUNS_DIR = BASE_DIR / "runs"
