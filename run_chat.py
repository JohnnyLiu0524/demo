from urllib import error

from chat_runner.config import (
    apply_overrides,
    get_compare_models,
    get_judge_model,
    load_settings,
    parse_args,
)
from chat_runner.judge import run_judge
from chat_runner.ollama import build_payload, stream_chat
from chat_runner.paths import BASE_DIR
from chat_runner.prompts import build_messages, load_prompt_pair
from chat_runner.reports import save_run


def run_participants(settings, messages, model_list):
    results = []
    for idx, model in enumerate(model_list, start=1):
        if len(model_list) > 1:
            print(f"=== Model {idx}/{len(model_list)}: {model} ===\n")

        payload = build_payload(settings, messages, model=model)
        thinking, answer, stats = stream_chat(settings, payload)
        results.append(
            {
                "model": model,
                "thinking": thinking,
                "answer": answer,
                "stats": stats,
            }
        )
    return results


def main():
    args = parse_args()
    try:
        settings = apply_overrides(load_settings(), args)
        system_path, request_path, system_prompt, user_request = load_prompt_pair(
            args.system,
            args.request,
        )

        messages = build_messages(system_prompt, user_request)
        model_list = get_compare_models(settings)
        judge_model = get_judge_model(settings)

        results = run_participants(settings, messages, model_list)
        judge_result = run_judge(settings, judge_model, user_request, results)
    except (FileNotFoundError, ValueError) as exc:
        print(exc)
        return
    except error.URLError as exc:
        print(f"Could not connect to Ollama: {exc}")
        print("Make sure Ollama is running, then try again.")
        return

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
