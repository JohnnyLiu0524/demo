from .files import read_text
from .paths import PROMPTS_DIR


def resolve_prompt_path(file_name):
    path = PROMPTS_DIR / file_name
    if path.suffix != ".md":
        path = path.with_suffix(".md")
    return path


def load_prompt_pair(system_file, request_file):
    system_path = resolve_prompt_path(system_file)
    request_path = resolve_prompt_path(request_file)
    return system_path, request_path, read_text(system_path), read_text(request_path)


def build_messages(system_prompt, user_request):
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_request},
    ]
