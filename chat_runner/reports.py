import json
from datetime import datetime

from report_html import render_html_report

from .files import write_json
from .paths import RUNS_DIR
from .stats import render_stats_markdown


def build_markdown_report(
    settings,
    system_file,
    request_file,
    system_prompt,
    user_request,
    results,
    judge_result=None,
):
    if len(results) == 1:
        output = build_single_result_report(
            settings,
            system_file,
            request_file,
            system_prompt,
            user_request,
            results[0],
        )
    else:
        output = build_comparison_report(
            settings,
            system_file,
            request_file,
            system_prompt,
            user_request,
            results,
        )

    if judge_result is not None:
        output += build_judge_report(judge_result)
    return output


def build_single_result_report(
    settings,
    system_file,
    request_file,
    system_prompt,
    user_request,
    result,
):
    return f"""# LLM Output

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


def build_comparison_report(
    settings,
    system_file,
    request_file,
    system_prompt,
    user_request,
    results,
):
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
                result["thinking"] or "No thinking output was returned.",
                "",
                "### Efficiency",
                "",
                render_stats_markdown(result),
                "",
                "### Answer",
                "",
                result["answer"] or "No answer output was returned.",
                "",
            ]
        )
    return "\n".join(output_lines)


def build_judge_report(judge_result):
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
    return "\n".join(output_lines)


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

    output = build_markdown_report(
        settings,
        system_file,
        request_file,
        system_prompt,
        user_request,
        results,
        judge_result=judge_result,
    )
    run_md_path.write_text(output, encoding="utf-8")
    write_json(
        run_json_path,
        {
            "settings": settings,
            "system_file": str(system_file),
            "request_file": str(request_file),
            "system_prompt": system_prompt,
            "user_request": user_request,
            "results": results,
            "judge_result": judge_result,
        },
    )
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
