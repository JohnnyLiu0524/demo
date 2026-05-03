import html
import re
from datetime import datetime


def get_model_info(model_name, role="Participant"):
    family, _, tag = model_name.partition(":")
    display_role = "Judge" if role == "Judge" else "Participant"
    return {
        "name": model_name,
        "family": family or model_name,
        "tag": tag or "default",
        "role": display_role,
        "runtime": "Ollama",
    }



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



def ratio_percent(value, max_value):
    if not isinstance(value, (int, float)) or not isinstance(max_value, (int, float)):
        return 0
    if max_value <= 0:
        return 0
    return max(2, min(100, round((value / max_value) * 100)))



def get_stats(result):
    return result.get("stats") or {}



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


def summarize_prompt(text, max_chars=120):
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        lines.append(stripped)
    summary = " ".join(lines) or text.strip()
    if len(summary) > max_chars:
        return summary[: max_chars - 1].rstrip() + "..."
    return summary


# Render the polished user-facing HTML report. Keep presentation details out of run_chat.py.
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
    participant_names = [result["model"] for result in results]
    participant_summary = " vs ".join(participant_names)
    question_summary = summarize_prompt(user_request)
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
              <div class="card-kicker">Participant Model {idx}</div>
              <h3>{html.escape(info["name"])}</h3>
              <dl>
                <div><dt>Runtime</dt><dd>{html.escape(info["runtime"])}</dd></div>
                <div><dt>Family</dt><dd>{html.escape(info["family"])}</dd></div>
                <div><dt>Tag</dt><dd>{html.escape(info["tag"])}</dd></div>
                <div><dt>Role</dt><dd>{html.escape(info["role"])}</dd></div>
              </dl>
            </article>
            """
        )
    if judge_info is not None:
        model_cards.append(
            f"""
            <article class="model-card judge-card">
              <div class="card-kicker">Judge Model</div>
              <h3>{html.escape(judge_info["name"])}</h3>
              <dl>
                <div><dt>Runtime</dt><dd>{html.escape(judge_info["runtime"])}</dd></div>
                <div><dt>Family</dt><dd>{html.escape(judge_info["family"])}</dd></div>
                <div><dt>Tag</dt><dd>{html.escape(judge_info["tag"])}</dd></div>
                <div><dt>Role</dt><dd>{html.escape(judge_info["role"])}</dd></div>
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
                <span>Answer {idx}</span>
                <h3>{html.escape(result["model"])}</h3>
              </header>
              <div class="answer-body">
                {render_markdown(result["answer"])}
              </div>
            </article>
            """
        )

    settings_summary = [
        ("Streaming", str(settings.get("stream", "unknown"))),
        ("Thinking", str(settings.get("think", "unknown"))),
        ("Show thinking in terminal", str(settings.get("show_thinking_in_terminal", "unknown"))),
        ("Ollama endpoint", str(settings.get("ollama_url", "unknown"))),
    ]
    settings_items = "".join(
        f"<div><dt>{html.escape(label)}</dt><dd>{html.escape(value)}</dd></div>"
        for label, value in settings_summary
    )
    performance_entries = [
        ("Participant", result["model"], get_stats(result)) for result in results
    ]
    if judge_result is not None:
        performance_entries.append(("Judge", judge_result["model"], get_stats(judge_result)))
    max_wall_time = max(
        [
            stats.get("wall_time_seconds")
            for _, _, stats in performance_entries
            if isinstance(stats.get("wall_time_seconds"), (int, float))
        ]
        or [0]
    )
    max_total_tokens = max(
        [
            stats.get("total_tokens")
            for _, _, stats in performance_entries
            if isinstance(stats.get("total_tokens"), (int, float))
        ]
        or [0]
    )
    max_output_speed = max(
        [
            stats.get("output_tokens_per_second")
            for _, _, stats in performance_entries
            if isinstance(stats.get("output_tokens_per_second"), (int, float))
        ]
        or [0]
    )
    performance_rows = []
    efficiency_bars = []
    for role, model_name, stats in performance_entries:
        bar_class = "judge-bar" if role == "Judge" else "participant-bar"
        wall_time_width = ratio_percent(stats.get("wall_time_seconds"), max_wall_time)
        token_width = ratio_percent(stats.get("total_tokens"), max_total_tokens)
        speed_width = ratio_percent(stats.get("output_tokens_per_second"), max_output_speed)
        performance_rows.append(
            f"""
            <tr>
              <td><strong>{html.escape(model_name)}</strong><span>{html.escape(role)}</span></td>
              <td>{format_seconds(stats.get("wall_time_seconds"))}</td>
              <td>{format_seconds(stats.get("total_duration_seconds"))}</td>
              <td>{format_number(stats.get("prompt_tokens"))}</td>
              <td>{format_number(stats.get("output_tokens"))}</td>
              <td>{format_number(stats.get("total_tokens"))}</td>
              <td>{format_rate(stats.get("output_tokens_per_second"))}</td>
              <td>{format_rate(stats.get("overall_tokens_per_second"))}</td>
            </tr>
            """
        )
        efficiency_bars.append(
            f"""
            <article class="efficiency-card">
              <header>
                <div>
                  <span>{html.escape(role)}</span>
                  <h3>{html.escape(model_name)}</h3>
                </div>
              </header>
              <div class="bar-list">
                <div class="bar-row">
                  <div class="bar-label"><span>Wall-clock time</span><strong>{format_seconds(stats.get("wall_time_seconds"))}</strong></div>
                  <div class="bar-track"><div class="bar-fill time-bar {bar_class}" style="width: {wall_time_width}%"></div></div>
                </div>
                <div class="bar-row">
                  <div class="bar-label"><span>Total token usage</span><strong>{format_number(stats.get("total_tokens"))}</strong></div>
                  <div class="bar-track"><div class="bar-fill token-bar {bar_class}" style="width: {token_width}%"></div></div>
                </div>
                <div class="bar-row">
                  <div class="bar-label"><span>Output speed</span><strong>{format_rate(stats.get("output_tokens_per_second"))}</strong></div>
                  <div class="bar-track"><div class="bar-fill speed-bar {bar_class}" style="width: {speed_width}%"></div></div>
                </div>
              </div>
            </article>
            """
        )

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Model Comparison Report</title>
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
      grid-template-columns: minmax(320px, 1.35fr) minmax(220px, 0.8fr) minmax(220px, 0.8fr);
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
    .metric-primary strong {{
      font-size: 20px;
      line-height: 1.35;
    }}
    .metric-wide {{
      grid-column: 1 / -1;
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
    .performance-panel {{
      overflow: hidden;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
    }}
    .efficiency-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(270px, 1fr));
      gap: 14px;
      margin-bottom: 14px;
    }}
    .efficiency-card {{
      padding: 18px;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
    }}
    .efficiency-card header span {{
      color: var(--muted);
      font-size: 12px;
      font-weight: 750;
    }}
    .efficiency-card h3 {{
      margin: 4px 0 0;
      overflow-wrap: anywhere;
      font-size: 18px;
    }}
    .bar-list {{
      display: grid;
      gap: 14px;
      margin-top: 16px;
    }}
    .bar-label {{
      display: flex;
      justify-content: space-between;
      gap: 14px;
      margin-bottom: 6px;
      font-size: 13px;
    }}
    .bar-label span {{
      color: var(--muted);
      font-weight: 650;
    }}
    .bar-label strong {{
      overflow-wrap: anywhere;
      text-align: right;
    }}
    .bar-track {{
      width: 100%;
      height: 10px;
      overflow: hidden;
      background: #edf2f5;
      border-radius: 999px;
    }}
    .bar-fill {{
      height: 100%;
      min-width: 2%;
      border-radius: inherit;
    }}
    .time-bar.participant-bar {{ background: #0f766e; }}
    .time-bar.judge-bar {{ background: #b45309; }}
    .token-bar.participant-bar {{ background: #2563eb; }}
    .token-bar.judge-bar {{ background: #9333ea; }}
    .speed-bar.participant-bar {{ background: #16a34a; }}
    .speed-bar.judge-bar {{ background: #ea580c; }}
    .performance-panel .table-wrap {{
      margin: 0;
      border: 0;
      border-radius: 0;
    }}
    .performance-panel td:first-child span {{
      display: block;
      margin-top: 2px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 650;
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
      .metric-wide {{
        grid-column: auto;
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
      <h1>Model Comparison Report</h1>
      <p class="subtitle">A reader-friendly report with participant model details, prompt information, model answers, efficiency metrics, and judge scoring.</p>
      <div class="metrics">
        <div class="metric metric-primary">
          <span>Participant Models</span>
          <strong>{html.escape(participant_summary)}</strong>
        </div>
        <div class="metric"><span>Judge Model</span><strong>{html.escape(judge_model_name)}</strong></div>
        <div class="metric"><span>Generated At</span><strong>{html.escape(generated_at)}</strong></div>
        <div class="metric metric-wide"><span>User Request</span><strong>{html.escape(question_summary)}</strong></div>
      </div>
    </div>
  </header>

  <main class="wrap">
    <section>
      <div class="section-head">
        <div>
          <h2>Prompt Information</h2>
          <p class="hint">The full user request used for this comparison.</p>
        </div>
      </div>
      <div class="panel prompt-panel">
        <div class="prompt-block prose">
          {render_markdown(user_request)}
        </div>
        <aside class="settings-block">
          <dl>
            <div><dt>System prompt file</dt><dd>{html.escape(str(system_file))}</dd></div>
            <div><dt>Request file</dt><dd>{html.escape(str(request_file))}</dd></div>
            {settings_items}
          </dl>
        </aside>
      </div>
    </section>

    <section>
      <div class="section-head">
        <div>
          <h2>Model Information</h2>
          <p class="hint">Basic information for participant and judge models.</p>
        </div>
      </div>
      <div class="model-grid">
        {''.join(model_cards)}
      </div>
    </section>

    <section>
      <div class="section-head">
        <div>
          <h2>Efficiency Metrics</h2>
          <p class="hint">Latency, token usage, and generation speed. The bars show quick comparisons; the table keeps exact values.</p>
        </div>
      </div>
      <div class="efficiency-grid">
        {''.join(efficiency_bars)}
      </div>
      <div class="performance-panel">
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Model</th>
                <th>Wall-clock time</th>
                <th>Ollama total time</th>
                <th>Prompt tokens</th>
                <th>Output tokens</th>
                <th>Total tokens</th>
                <th>Output speed</th>
                <th>Overall speed</th>
              </tr>
            </thead>
            <tbody>
              {''.join(performance_rows)}
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <section>
      <div class="section-head">
        <div>
          <h2>Model Answers</h2>
          <p class="hint">The final answer from each participant model.</p>
        </div>
      </div>
      <div class="answers">
        {''.join(answer_cards)}
      </div>
    </section>

    <section>
      <div class="section-head">
        <div>
          <h2>Judge Evaluation</h2>
          <p class="hint">Scores, comments, and recommendation from the judge model.</p>
        </div>
      </div>
      <div class="panel score-panel prose">
        {score_section}
      </div>
    </section>
  </main>

  <footer>
    <div class="wrap">Generated by run_chat.py from {html.escape(str(system_file))} and {html.escape(str(request_file))}.</div>
  </footer>
</body>
</html>
"""


