import argparse
import html
import json
import re
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


def get_model_info(model_name, role="Participant"):
    family, _, tag = model_name.partition(":")
    display_role = "裁判" if role == "Judge" else "参赛者"
    return {
        "name": model_name,
        "family": family or model_name,
        "tag": tag or "default",
        "role": display_role,
        "runtime": "Ollama",
    }


def render_inline_markdown(text):
    escaped = html.escape(text)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", escaped)
    return escaped


def render_markdown(text):
    if not text:
        return '<p class="muted">No content was returned.</p>'

    lines = text.strip().splitlines()
    parts = []
    paragraph = []
    in_code = False
    code_lines = []
    list_items = []
    ordered_items = []

    def flush_paragraph():
        if paragraph:
            parts.append(f"<p>{render_inline_markdown(' '.join(paragraph))}</p>")
            paragraph.clear()

    def flush_list():
        if list_items:
            parts.append(
                "<ul>"
                + "".join(f"<li>{render_inline_markdown(item)}</li>" for item in list_items)
                + "</ul>"
            )
            list_items.clear()

    def flush_ordered_list():
        if ordered_items:
            parts.append(
                "<ol>"
                + "".join(f"<li>{render_inline_markdown(item)}</li>" for item in ordered_items)
                + "</ol>"
            )
            ordered_items.clear()

    def flush_code():
        if code_lines:
            parts.append(f"<pre><code>{html.escape(chr(10).join(code_lines))}</code></pre>")
            code_lines.clear()

    def is_table_start(index):
        if index + 1 >= len(lines):
            return False
        return "|" in lines[index] and re.fullmatch(r"\s*\|?[\s:|-]+\|?\s*", lines[index + 1])

    def render_table(start_index):
        header = [cell.strip() for cell in lines[start_index].strip().strip("|").split("|")]
        body_rows = []
        index = start_index + 2
        while index < len(lines) and "|" in lines[index].strip():
            body_rows.append(
                [cell.strip() for cell in lines[index].strip().strip("|").split("|")]
            )
            index += 1

        table = ["<div class=\"table-wrap\"><table><thead><tr>"]
        table.extend(f"<th>{render_inline_markdown(cell)}</th>" for cell in header)
        table.append("</tr></thead><tbody>")
        for row in body_rows:
            table.append("<tr>")
            table.extend(f"<td>{render_inline_markdown(cell)}</td>" for cell in row)
            table.append("</tr>")
        table.append("</tbody></table></div>")
        return "".join(table), index

    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        if stripped.startswith("```"):
            if in_code:
                flush_code()
                in_code = False
            else:
                flush_paragraph()
                flush_list()
                flush_ordered_list()
                in_code = True
            index += 1
            continue

        if in_code:
            code_lines.append(line)
            index += 1
            continue

        if not stripped:
            flush_paragraph()
            flush_list()
            flush_ordered_list()
            index += 1
            continue

        if is_table_start(index):
            flush_paragraph()
            flush_list()
            flush_ordered_list()
            table_html, index = render_table(index)
            parts.append(table_html)
            continue

        heading_match = re.match(r"^(#{1,4})\s+(.+)$", stripped)
        if heading_match:
            flush_paragraph()
            flush_list()
            flush_ordered_list()
            level = min(len(heading_match.group(1)) + 1, 5)
            parts.append(
                f"<h{level}>{render_inline_markdown(heading_match.group(2))}</h{level}>"
            )
            index += 1
            continue

        list_match = re.match(r"^[-*]\s+(.+)$", stripped)
        if list_match:
            flush_paragraph()
            flush_ordered_list()
            list_items.append(list_match.group(1))
            index += 1
            continue

        ordered_match = re.match(r"^\d+[.)]\s+(.+)$", stripped)
        if ordered_match:
            flush_paragraph()
            flush_list()
            ordered_items.append(ordered_match.group(1))
            index += 1
            continue

        paragraph.append(stripped)
        index += 1

    flush_paragraph()
    flush_list()
    flush_ordered_list()
    if in_code:
        flush_code()
    return "\n".join(parts)


def render_html_report(
    settings,
    system_file,
    request_file,
    system_prompt,
    user_request,
    results,
    judge_result=None,
):
    participant_infos = [get_model_info(result["model"]) for result in results]
    judge_info = (
        get_model_info(judge_result["model"], role="Judge") if judge_result is not None else None
    )
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    judge_model_name = judge_result["model"] if judge_result else "Not configured"
    score_section = (
        render_markdown(judge_result["answer"])
        if judge_result is not None
        else '<p class="muted">No judge evaluation was generated for this run.</p>'
    )

    model_cards = []
    for idx, info in enumerate(participant_infos, start=1):
        model_cards.append(
            f"""
            <article class="model-card">
              <div class="card-kicker">参赛模型 {idx}</div>
              <h3>{html.escape(info["name"])}</h3>
              <dl>
                <div><dt>运行环境</dt><dd>{html.escape(info["runtime"])}</dd></div>
                <div><dt>模型族</dt><dd>{html.escape(info["family"])}</dd></div>
                <div><dt>标签</dt><dd>{html.escape(info["tag"])}</dd></div>
                <div><dt>角色</dt><dd>{html.escape(info["role"])}</dd></div>
              </dl>
            </article>
            """
        )
    if judge_info is not None:
        model_cards.append(
            f"""
            <article class="model-card judge-card">
              <div class="card-kicker">裁判模型</div>
              <h3>{html.escape(judge_info["name"])}</h3>
              <dl>
                <div><dt>运行环境</dt><dd>{html.escape(judge_info["runtime"])}</dd></div>
                <div><dt>模型族</dt><dd>{html.escape(judge_info["family"])}</dd></div>
                <div><dt>标签</dt><dd>{html.escape(judge_info["tag"])}</dd></div>
                <div><dt>角色</dt><dd>{html.escape(judge_info["role"])}</dd></div>
              </dl>
            </article>
            """
        )

    answer_cards = []
    for idx, result in enumerate(results, start=1):
        answer_cards.append(
            f"""
            <article class="answer-card">
              <header>
                <span>答案 {idx}</span>
                <h3>{html.escape(result["model"])}</h3>
              </header>
              <div class="answer-body">
                {render_markdown(result["answer"])}
              </div>
            </article>
            """
        )

    settings_summary = [
        ("流式输出", str(settings.get("stream", "unknown"))),
        ("Thinking", str(settings.get("think", "unknown"))),
        ("终端显示思考", str(settings.get("show_thinking_in_terminal", "unknown"))),
        ("Ollama 地址", str(settings.get("ollama_url", "unknown"))),
    ]
    settings_items = "".join(
        f"<div><dt>{html.escape(label)}</dt><dd>{html.escape(value)}</dd></div>"
        for label, value in settings_summary
    )

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>模型 PK 报告</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #16202a;
      --muted: #667481;
      --line: #dde4ea;
      --paper: #fbfcfd;
      --panel: #ffffff;
      --accent: #0f766e;
      --accent-2: #b45309;
      --accent-soft: #e6f4f1;
      --shadow: 0 18px 45px rgba(22, 32, 42, 0.08);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--paper);
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.65;
    }}
    .hero {{
      background: linear-gradient(135deg, #f7faf9 0%, #eef7f5 52%, #fff7ed 100%);
      border-bottom: 1px solid var(--line);
    }}
    .wrap {{
      width: min(1120px, calc(100% - 32px));
      margin: 0 auto;
    }}
    .hero-inner {{
      padding: 52px 0 36px;
    }}
    .eyebrow {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      margin: 0 0 16px;
      color: var(--accent);
      font-size: 13px;
      font-weight: 750;
      letter-spacing: 0;
      text-transform: uppercase;
    }}
    h1 {{
      max-width: 860px;
      margin: 0;
      font-size: clamp(34px, 5vw, 64px);
      line-height: 1.02;
      letter-spacing: 0;
    }}
    .subtitle {{
      max-width: 820px;
      margin: 18px 0 0;
      color: var(--muted);
      font-size: 18px;
    }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      margin-top: 28px;
    }}
    .metric {{
      padding: 16px;
      background: rgba(255, 255, 255, 0.72);
      border: 1px solid rgba(221, 228, 234, 0.9);
      border-radius: 8px;
    }}
    .metric span {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
    }}
    .metric strong {{
      display: block;
      margin-top: 6px;
      overflow-wrap: anywhere;
      font-size: 15px;
    }}
    main {{
      padding: 34px 0 56px;
    }}
    section {{
      margin-top: 30px;
    }}
    .section-head {{
      display: flex;
      align-items: end;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 14px;
    }}
    h2 {{
      margin: 0;
      font-size: 24px;
      letter-spacing: 0;
    }}
    .hint {{
      margin: 4px 0 0;
      color: var(--muted);
      font-size: 14px;
    }}
    .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
    }}
    .prompt-panel {{
      display: grid;
      grid-template-columns: minmax(0, 1.15fr) minmax(260px, 0.85fr);
      overflow: hidden;
    }}
    .prompt-block, .settings-block {{
      padding: 22px;
    }}
    .settings-block {{
      border-left: 1px solid var(--line);
      background: #f8fafb;
    }}
    .prose h3, .prose h4, .prose h5,
    .answer-body h3, .answer-body h4, .answer-body h5 {{
      margin: 20px 0 8px;
      line-height: 1.25;
    }}
    .prose p, .answer-body p {{
      margin: 0 0 14px;
    }}
    .model-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
      gap: 14px;
    }}
    .model-card {{
      padding: 18px;
      background: var(--panel);
      border: 1px solid var(--line);
      border-top: 4px solid var(--accent);
      border-radius: 8px;
      box-shadow: var(--shadow);
    }}
    .judge-card {{
      border-top-color: var(--accent-2);
    }}
    .card-kicker {{
      color: var(--muted);
      font-size: 12px;
      font-weight: 750;
      text-transform: uppercase;
    }}
    .model-card h3 {{
      margin: 6px 0 14px;
      overflow-wrap: anywhere;
      font-size: 20px;
    }}
    dl {{
      display: grid;
      gap: 10px;
      margin: 0;
    }}
    dl div {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      border-bottom: 1px solid #edf1f4;
      padding-bottom: 8px;
    }}
    dt {{
      color: var(--muted);
      font-size: 13px;
      font-weight: 650;
    }}
    dd {{
      margin: 0;
      text-align: right;
      overflow-wrap: anywhere;
      font-size: 13px;
      font-weight: 700;
    }}
    .answers {{
      display: grid;
      gap: 16px;
    }}
    .answer-card {{
      overflow: hidden;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
    }}
    .answer-card header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 16px 20px;
      background: #f8fafb;
      border-bottom: 1px solid var(--line);
    }}
    .answer-card header span {{
      color: var(--accent);
      font-size: 12px;
      font-weight: 800;
      text-transform: uppercase;
    }}
    .answer-card header h3 {{
      margin: 0;
      overflow-wrap: anywhere;
      font-size: 18px;
    }}
    .answer-body {{
      padding: 22px;
    }}
    .score-panel {{
      padding: 24px;
      border-top: 4px solid var(--accent-2);
    }}
    .muted {{
      color: var(--muted);
    }}
    code {{
      padding: 2px 6px;
      background: #eef2f5;
      border-radius: 5px;
      font-size: 0.92em;
    }}
    pre {{
      overflow: auto;
      padding: 14px;
      background: #111827;
      color: #f8fafc;
      border-radius: 8px;
    }}
    pre code {{
      padding: 0;
      background: transparent;
      color: inherit;
    }}
    ul {{
      margin: 0 0 16px 20px;
      padding: 0;
    }}
    .table-wrap {{
      overflow-x: auto;
      margin: 16px 0;
      border: 1px solid var(--line);
      border-radius: 8px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      min-width: 620px;
      background: #fff;
    }}
    th, td {{
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
    }}
    th {{
      background: var(--accent-soft);
      color: #12433f;
      font-size: 13px;
    }}
    tr:last-child td {{
      border-bottom: 0;
    }}
    footer {{
      padding: 24px 0 34px;
      color: var(--muted);
      border-top: 1px solid var(--line);
      font-size: 13px;
    }}
    @media (max-width: 780px) {{
      .metrics, .prompt-panel {{
        grid-template-columns: 1fr;
      }}
      .settings-block {{
        border-left: 0;
        border-top: 1px solid var(--line);
      }}
      .answer-card header {{
        align-items: flex-start;
        flex-direction: column;
        gap: 6px;
      }}
    }}
  </style>
</head>
<body>
  <header class="hero">
    <div class="wrap hero-inner">
      <p class="eyebrow">Local Ollama PK Report</p>
      <h1>模型 PK 结果报告</h1>
      <p class="subtitle">面向用户展示的可读报告，包含参赛模型信息、题目信息、各模型答案和裁判模型评分。</p>
      <div class="metrics">
        <div class="metric"><span>生成时间</span><strong>{html.escape(generated_at)}</strong></div>
        <div class="metric"><span>参赛模型</span><strong>{len(results)}</strong></div>
        <div class="metric"><span>裁判模型</span><strong>{html.escape(judge_model_name)}</strong></div>
        <div class="metric"><span>题目文件</span><strong>{html.escape(str(request_file))}</strong></div>
      </div>
    </div>
  </header>

  <main class="wrap">
    <section>
      <div class="section-head">
        <div>
          <h2>模型信息</h2>
          <p class="hint">根据配置中的 Ollama 模型名称生成的基础信息。</p>
        </div>
      </div>
      <div class="model-grid">
        {''.join(model_cards)}
      </div>
    </section>

    <section>
      <div class="section-head">
        <div>
          <h2>题目信息</h2>
          <p class="hint">本次对比使用的完整用户题目。</p>
        </div>
      </div>
      <div class="panel prompt-panel">
        <div class="prompt-block prose">
          {render_markdown(user_request)}
        </div>
        <aside class="settings-block">
          <dl>
            <div><dt>系统提示文件</dt><dd>{html.escape(str(system_file))}</dd></div>
            <div><dt>题目文件</dt><dd>{html.escape(str(request_file))}</dd></div>
            {settings_items}
          </dl>
        </aside>
      </div>
    </section>

    <section>
      <div class="section-head">
        <div>
          <h2>模型答案</h2>
          <p class="hint">每个参赛模型的最终回答。</p>
        </div>
      </div>
      <div class="answers">
        {''.join(answer_cards)}
      </div>
    </section>

    <section>
      <div class="section-head">
        <div>
          <h2>评分结果</h2>
          <p class="hint">裁判模型给出的评价、分数和推荐。</p>
        </div>
      </div>
      <div class="panel score-panel prose">
        {score_section}
      </div>
    </section>
  </main>

  <footer>
    <div class="wrap">由 run_chat.py 根据 {html.escape(str(system_file))} 和 {html.escape(str(request_file))} 生成。</div>
  </footer>
</body>
</html>
"""


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
