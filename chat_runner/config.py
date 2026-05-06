import argparse
import json

from .files import read_text
from .paths import SETTINGS_PATH


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run a model comparison for the same Markdown prompt across configured Ollama models."
    )
    parser.add_argument(
        "--system",
        default="system.md",
        help="System prompt file inside prompts/. Default: system.md",
    )
    parser.add_argument(
        "--request",
        default="request.md",
        help="User request file inside prompts/. Default: request.md",
    )
    parser.add_argument(
        "--show-thinking",
        action="store_true",
        help="Show thinking output live in the terminal.",
    )
    parser.add_argument(
        "--no-think",
        action="store_true",
        help="Disable thinking for this run.",
    )
    return parser.parse_args()


def load_settings():
    try:
        return json.loads(read_text(SETTINGS_PATH))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {SETTINGS_PATH}: {exc}") from exc


def apply_overrides(settings, args):
    settings = settings.copy()
    if args.show_thinking:
        settings["show_thinking_in_terminal"] = True
    if args.no_think:
        settings["think"] = False
    return settings


def get_compare_models(settings):
    compare_models = settings.get("compare_models")
    if compare_models is None:
        return [settings["model"]]
    if isinstance(compare_models, str):
        models = [m.strip() for m in compare_models.split(",") if m.strip()]
    elif isinstance(compare_models, list):
        models = [str(m).strip() for m in compare_models if str(m).strip()]
    else:
        raise ValueError(
            "Invalid compare_models in settings.json: must be a list or comma-separated string."
        )
    if not models:
        raise ValueError(
            "compare_models in settings.json must contain at least one model name."
        )
    return models


def get_judge_model(settings):
    judge_model = settings.get("judge_model")
    if judge_model is None:
        return None
    return str(judge_model).strip()
