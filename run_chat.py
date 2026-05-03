import argparse
import json
import time
from datetime import datetime
from pathlib import Path
from urllib import error, request

from report_html import render_html_report


# Project paths are centralized so prompts, settings, and run outputs stay portable.
BASE_DIR = Path(__file__).parent
SETTINGS_PATH = BASE_DIR / "settings.json"
PROMPTS_DIR = BASE_DIR / "prompts"
RUNS_DIR = BASE_DIR / "runs"
# Ollama returns these timing/token fields in the final streaming chunk.
OLLAMA_STAT_KEYS = [
    "total_duration",
    "load_duration",
    "prompt_eval_count",
    "prompt_eval_duration",
    "eval_count",
    "eval_duration",
]


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


# The judge sees only the user question and participant answers, then writes a scorecard.
def build_judge_prompt(user_request, results):
    prompt_lines = [
        "You are a neutral judge comparing multiple model responses to the same user request.",
        "Write the entire evaluation in English.",
        "Evaluate each model on accuracy, relevance, completeness, clarity, and overall effectiveness.",
        "Score each dimension from 1 to 10, give concise reasons, and provide a final recommendation.",
        "Do not invent new information; judge only from the provided model responses.",
        "You must strictly use the following Markdown format. Do not add, remove, or rename any top-level or second-level headings:",
        "",
        "## Score Overview",
        "",
        "| Rank | Model | Accuracy | Relevance | Completeness | Clarity | Overall Effectiveness | Final Score | One-Sentence Assessment |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        "| 1 | Model name | 1-10 | 1-10 | 1-10 | 1-10 | 1-10 | 1-10 | Brief assessment |",
        "",
        "## Per-Model Notes",
        "",
        "### Model name",
        "",
        "- Strength: one sentence.",
        "- Weakness: one sentence.",
        "- Best suited for: one sentence.",
        "",
        "## Final Recommendation",
        "",
        "- Recommended model: model name",
        "- Reason: two or three sentences explaining why it is the best fit for this request.",
        "",
        "## Notes",
        "",
        "- List only limitations or risks readers should know about. If there are no obvious extra notes, write \"No obvious additional notes.\"",
        "",
        "Below are the user request and model responses to evaluate.\n",
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
        "Strictly follow the fixed Markdown template above and write the evaluation in English."
    )
    return "\n".join(prompt_lines)


def ns_to_seconds(value):
    if not isinstance(value, (int, float)):
        return None
    return value / 1_000_000_000


def format_seconds(value):
    if not isinstance(value, (int, float)):
        return "N/A"
    if value < 1:
        return f"{value * 1000:.0f} ms"
    return f"{value:.2f} s"


def format_number(value):
    if not isinstance(value, (int, float)):
        return "N/A"
    return f"{value:,.0f}"


def format_rate(value):
    if not isinstance(value, (int, float)):
        return "N/A"
    return f"{value:.2f} tok/s"


# Normalize Ollama nanosecond durations and token counts into report-friendly metrics.
def build_response_stats(done_data, wall_time_seconds):
    raw = {key: done_data.get(key) for key in OLLAMA_STAT_KEYS if key in done_data}
    prompt_tokens = raw.get("prompt_eval_count")
    output_tokens = raw.get("eval_count")
    total_tokens = None
    if isinstance(prompt_tokens, int) and isinstance(output_tokens, int):
        total_tokens = prompt_tokens + output_tokens

    eval_seconds = ns_to_seconds(raw.get("eval_duration"))
    prompt_eval_seconds = ns_to_seconds(raw.get("prompt_eval_duration"))
    total_seconds = ns_to_seconds(raw.get("total_duration"))
    load_seconds = ns_to_seconds(raw.get("load_duration"))

    output_tokens_per_second = None
    if isinstance(output_tokens, int) and eval_seconds and eval_seconds > 0:
        output_tokens_per_second = output_tokens / eval_seconds

    prompt_tokens_per_second = None
    if isinstance(prompt_tokens, int) and prompt_eval_seconds and prompt_eval_seconds > 0:
        prompt_tokens_per_second = prompt_tokens / prompt_eval_seconds

    overall_tokens_per_second = None
    if isinstance(total_tokens, int) and total_seconds and total_seconds > 0:
        overall_tokens_per_second = total_tokens / total_seconds

    return {
        "wall_time_seconds": wall_time_seconds,
        "total_duration_seconds": total_seconds,
        "load_duration_seconds": load_seconds,
        "prompt_eval_duration_seconds": prompt_eval_seconds,
        "eval_duration_seconds": eval_seconds,
        "prompt_tokens": prompt_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "prompt_tokens_per_second": prompt_tokens_per_second,
        "output_tokens_per_second": output_tokens_per_second,
        "overall_tokens_per_second": overall_tokens_per_second,
        "raw": raw,
    }


def get_stats(result):
    return result.get("stats") or {}


def render_stats_markdown(result):
    stats = get_stats(result)
    lines = [
        "| Metric | Value |",
        "| --- | --- |",
        f"| Wall-clock time | {format_seconds(stats.get('wall_time_seconds'))} |",
        f"| Ollama total duration | {format_seconds(stats.get('total_duration_seconds'))} |",
        f"| Load duration | {format_seconds(stats.get('load_duration_seconds'))} |",
        f"| Prompt eval time | {format_seconds(stats.get('prompt_eval_duration_seconds'))} |",
        f"| Generation time | {format_seconds(stats.get('eval_duration_seconds'))} |",
        f"| Prompt tokens | {format_number(stats.get('prompt_tokens'))} |",
        f"| Output tokens | {format_number(stats.get('output_tokens'))} |",
        f"| Total tokens | {format_number(stats.get('total_tokens'))} |",
        f"| Output speed | {format_rate(stats.get('output_tokens_per_second'))} |",
        f"| Overall speed | {format_rate(stats.get('overall_tokens_per_second'))} |",
    ]
    return "\n".join(lines)


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


# Stream one Ollama chat response while collecting the final timing/token statistics.
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
    done_data = {}

    print("Generating response...\n")

    started_at = time.perf_counter()
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
                done_data = data
                break

    wall_time_seconds = time.perf_counter() - started_at
    print()
    stats = build_response_stats(done_data, wall_time_seconds)
    return "".join(thinking_parts).strip(), "".join(answer_parts).strip(), stats


# Save all three artifacts for a run: Markdown for reading, JSON for data, HTML for sharing.
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
    run_html_path = RUNS_DIR / f"run-{timestamp}.html"

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

## Efficiency

{render_stats_markdown(result)}

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
                    "### Efficiency",
                    "",
                    render_stats_markdown(result),
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
            "### Judge Efficiency",
            "",
            render_stats_markdown(judge_result),
            "",
            "### Judge Analysis",
            "",
            judge_result["answer"],
            "",
        ]
        output += "\n".join(output_lines)

    # Markdown is useful for quick inspection in editors and terminals.
    run_md_path.write_text(output, encoding="utf-8")

    # JSON preserves the structured data for future analysis or alternate report formats.
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

    # HTML is the polished artifact intended for readers.
    run_html_path.write_text(
        render_html_report(
            settings,
            system_file,
            request_file,
            system_prompt,
            user_request,
            results,
            judge_result=judge_result,
        ),
        encoding="utf-8",
    )
    return run_md_path, run_html_path


# Main orchestration: load prompts, run participants, run the judge, then write reports.
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

    # Run every participant against the same messages so the comparison is fair.
    results = []
    for idx, model in enumerate(model_list, start=1):
        if len(model_list) > 1:
            print(f"=== Model {idx}/{len(model_list)}: {model} ===\n")
        payload = build_payload(settings, messages, model=model)

        try:
            thinking, answer, stats = stream_chat(settings, payload)
        except error.URLError as exc:
            print(f"Could not connect to Ollama: {exc}")
            print("Make sure Ollama is running, then try again.")
            return

        results.append(
            {
                "model": model,
                "thinking": thinking,
                "answer": answer,
                "stats": stats,
            }
        )

    judge_result = None
    if judge_model is not None:
        if len(results) < 2:
            raise ValueError("judge_model requires at least two compare_models to evaluate.")
        # The judge evaluates completed answers; it does not call tools or see hidden thinking.
        judge_prompt = build_judge_prompt(user_request, results)
        judge_messages = [
            {"role": "system", "content": "You are a neutral judge. Compare model outputs in English and score them across multiple dimensions."},
            {"role": "user", "content": judge_prompt},
        ]
        judge_payload = build_payload(settings, judge_messages, model=judge_model)
        judge_thinking, judge_answer, judge_stats = stream_chat(settings, judge_payload)
        judge_result = {
            "model": judge_model,
            "thinking": judge_thinking,
            "answer": judge_answer,
            "stats": judge_stats,
        }

    run_path, html_path = save_run(
        settings,
        system_path.relative_to(BASE_DIR),
        request_path.relative_to(BASE_DIR),
        system_prompt,
        user_request,
        results,
        judge_result=judge_result,
    )
    print(f"\nSaved readable run to: {run_path}")
    print(f"Saved HTML report to: {html_path}")



if __name__ == "__main__":
    main()
