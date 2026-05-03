import argparse
import json
from datetime import datetime
from pathlib import Path
from urllib import error, request


BASE_DIR = Path(__file__).parent
SETTINGS_PATH = BASE_DIR / "settings.json"
PROMPTS_DIR = BASE_DIR / "prompts"
RUNS_DIR = BASE_DIR / "runs"


def read_text(path):
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    return path.read_text(encoding="utf-8").strip()


def load_settings():
    try:
        return json.loads(read_text(SETTINGS_PATH))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {SETTINGS_PATH}: {exc}") from exc


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


def resolve_prompt_path(file_name):
    path = PROMPTS_DIR / file_name
    if path.suffix != ".md":
        path = path.with_suffix(".md")
    return path


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


def build_judge_prompt(user_request, results):
    prompt_lines = [
        "You are a neutral judge comparing multiple model responses to a single user request.",
        "Evaluate each response on the following dimensions: accuracy, relevance, completeness, clarity, and overall effectiveness.",
        "Give each dimension a score from 1 to 10 for each model, provide a brief rationale, and then produce a final composite score and recommendation.",
        "Use Markdown headings, a comparison table, and a clear summary.",
        "Do not invent new information; judge only based on the provided responses.\n",
        "### User Request",
        user_request,
        "",
        "### Model Responses",
        "",
    ]
    for idx, result in enumerate(results, start=1):
        prompt_lines.extend(
            [
                f"#### {idx}. {result['model']}",
                result['answer'],
                "",
            ]
        )
    prompt_lines.append(
        "Please compare the above model outputs and provide the requested multi-dimensional evaluation."
    )
    return "\n".join(prompt_lines)


def build_messages(system_prompt, user_request):
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_request},
    ]


def build_payload(settings, messages, model=None):
    payload = {
        "model": model if model is not None else settings["model"],
        "messages": messages,
        "stream": settings["stream"],
        "think": settings["think"],
    }
    return payload


def stream_chat(settings, payload):
    req = request.Request(
        settings["ollama_url"],
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    thinking_parts = []
    answer_parts = []
    in_thinking = False
    show_thinking = settings["show_thinking_in_terminal"]

    print("Generating response...\n")

    with request.urlopen(req) as res:
        for line in res:
            if not line:
                continue

            data = json.loads(line.decode("utf-8"))
            message = data.get("message", {})
            thinking = message.get("thinking", "")
            content = message.get("content", "")

            if thinking:
                thinking_parts.append(thinking)
                if not in_thinking:
                    if show_thinking:
                        print("Thinking:\n", end="")
                    in_thinking = True
                if show_thinking:
                    print(thinking, end="", flush=True)
            elif content:
                answer_parts.append(content)
                if in_thinking:
                    if show_thinking:
                        print("\n\nAnswer:\n", end="")
                    in_thinking = False
                if len(answer_parts) == 1:
                    print("Answer:\n", end="")
                print(content, end="", flush=True)

            if data.get("done"):
                break

    print()
    return "".join(thinking_parts).strip(), "".join(answer_parts).strip()


def save_run(
    settings,
    system_file,
    request_file,
    system_prompt,
    user_request,
    results,
    judge_result=None,
):
    RUNS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_md_path = RUNS_DIR / f"run-{timestamp}.md"
    run_json_path = RUNS_DIR / f"run-{timestamp}.json"

    if len(results) == 1:
        result = results[0]
        output = f"""# LLM Output

## Run Settings

```json
{json.dumps(settings, indent=2)}
```

## Files

- System prompt: `{system_file}`
- User request: `{request_file}`

## System Prompt

{system_prompt}

## User Request

{user_request}

## Thinking

{result['thinking'] or 'No thinking output was returned.'}

## Answer

{result['answer'] or 'No answer output was returned.'}
"""
    else:
        output_lines = [
            "# LLM Model Comparison",
            "",
            "## Run Settings",
            "",
            "```json",
            json.dumps(settings, indent=2),
            "```",
            "",
            "## Files",
            "",
            f"- System prompt: `{system_file}`",
            f"- User request: `{request_file}`",
            "",
            "## System Prompt",
            "",
            system_prompt,
            "",
            "## User Request",
            "",
            user_request,
            "",
        ]
        for idx, result in enumerate(results, start=1):
            output_lines.extend(
                [
                    "---",
                    "",
                    f"## Result {idx}: {result['model']}",
                    "",
                    "### Thinking",
                    "",
                    result['thinking'] or 'No thinking output was returned.',
                    "",
                    "### Answer",
                    "",
                    result['answer'] or 'No answer output was returned.',
                    "",
                ]
            )
        output = "\n".join(output_lines)

    if judge_result is not None:
        output_lines = [
            "---",
            "",
            "## Judge Evaluation",
            "",
            f"- Judge model: `{judge_result['model']}`",
            "",
            "### Judge Analysis",
            "",
            judge_result["answer"],
            "",
        ]
        output += "\n".join(output_lines)

    run_md_path.write_text(output, encoding="utf-8")
    run_json_path.write_text(
        json.dumps(
            {
                "settings": settings,
                "system_file": str(system_file),
                "request_file": str(request_file),
                "system_prompt": system_prompt,
                "user_request": user_request,
                "results": results,
                "judge_result": judge_result,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return run_md_path


def main():
    args = parse_args()
    try:
        settings = apply_overrides(load_settings(), args)
        system_path = resolve_prompt_path(args.system)
        request_path = resolve_prompt_path(args.request)
        system_prompt = read_text(system_path)
        user_request = read_text(request_path)
    except (FileNotFoundError, ValueError) as exc:
        print(exc)
        return

    messages = build_messages(system_prompt, user_request)
    model_list = get_compare_models(settings)
    judge_model = get_judge_model(settings)

    results = []
    for idx, model in enumerate(model_list, start=1):
        if len(model_list) > 1:
            print(f"=== Model {idx}/{len(model_list)}: {model} ===\n")
        payload = build_payload(settings, messages, model=model)

        try:
            thinking, answer = stream_chat(settings, payload)
        except error.URLError as exc:
            print(f"Could not connect to Ollama: {exc}")
            print("Make sure Ollama is running, then try again.")
            return

        results.append(
            {
                "model": model,
                "thinking": thinking,
                "answer": answer,
            }
        )

    judge_result = None
    if judge_model is not None:
        if len(results) < 2:
            raise ValueError("judge_model requires at least two compare_models to evaluate.")
        judge_prompt = build_judge_prompt(user_request, results)
        judge_messages = [
            {"role": "system", "content": "You are a neutral judge. Compare the model outputs and score them across multiple dimensions."},
            {"role": "user", "content": judge_prompt},
        ]
        judge_payload = build_payload(settings, judge_messages, model=judge_model)
        judge_thinking, judge_answer = stream_chat(settings, judge_payload)
        judge_result = {
            "model": judge_model,
            "thinking": judge_thinking,
            "answer": judge_answer,
        }

    run_path = save_run(
        settings,
        system_path.relative_to(BASE_DIR),
        request_path.relative_to(BASE_DIR),
        system_prompt,
        user_request,
        results,
        judge_result=judge_result,
    )
    print(f"\nSaved readable run to: {run_path}")



if __name__ == "__main__":
    main()
