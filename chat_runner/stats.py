OLLAMA_STAT_KEYS = [
    "total_duration",
    "load_duration",
    "prompt_eval_count",
    "prompt_eval_duration",
    "eval_count",
    "eval_duration",
]


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
