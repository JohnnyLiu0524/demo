import json
import time
from urllib import request

from .stats import build_response_stats


def build_payload(settings, messages, model=None):
    return {
        "model": model if model is not None else settings["model"],
        "messages": messages,
        "stream": settings["stream"],
        "think": settings["think"],
    }


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
