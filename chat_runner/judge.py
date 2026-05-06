from .ollama import build_payload, stream_chat


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
                result["answer"],
                "",
            ]
        )
    prompt_lines.append(
        "Strictly follow the fixed Markdown template above and write the evaluation in English."
    )
    return "\n".join(prompt_lines)


def run_judge(settings, judge_model, user_request, results):
    if judge_model is None:
        return None
    if len(results) < 2:
        raise ValueError("judge_model requires at least two compare_models to evaluate.")

    judge_prompt = build_judge_prompt(user_request, results)
    judge_messages = [
        {
            "role": "system",
            "content": "You are a neutral judge. Compare model outputs in English and score them across multiple dimensions.",
        },
        {"role": "user", "content": judge_prompt},
    ]
    judge_payload = build_payload(settings, judge_messages, model=judge_model)
    judge_thinking, judge_answer, judge_stats = stream_chat(settings, judge_payload)
    return {
        "model": judge_model,
        "thinking": judge_thinking,
        "answer": judge_answer,
        "stats": judge_stats,
    }
