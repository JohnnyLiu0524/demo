# Local Ollama Model Comparison Runner

This project runs the same prompt against one or more local Ollama models, saves each response, and optionally asks a judge model to compare the answers.

It uses only Python's standard library. No package install is required.

## What It Does

- Reads a system prompt from `prompts/system.md`
- Reads a user request from `prompts/request.md`
- Sends both prompts to each model listed in `settings.json`
- Streams the answer in your terminal
- Collects timing and token statistics from Ollama
- Saves Markdown, JSON, and HTML reports in `runs/`
- Optionally runs a judge model to rank the responses

## Requirements

- Python 3.9 or newer
- Ollama installed and running
- At least one local Ollama model pulled on your machine

Example:

```bash
ollama pull qwen3:14b
ollama pull qwen3.5:9b
```

## Quick Start

1. Start Ollama.

2. Edit your prompts:

```text
prompts/system.md
prompts/request.md
```

3. Edit `settings.json`:

```json
{
  "model": "qwen3.6:27b",
  "compare_models": [
    "qwen3.6:27b",
    "qwen3.5:9b"
  ],
  "judge_model": "qwen3.6:35b-a3b",
  "ollama_url": "http://localhost:11434/api/chat",
  "stream": true,
  "think": true,
  "show_thinking_in_terminal": false
}
```

4. Run the script:

```bash
python run_chat.py
```

Reports will be saved in `runs/`.

## Settings

| Field | Description |
| --- | --- |
| `model` | Default model to use when `compare_models` is not set. |
| `compare_models` | List of models to compare. Can also be a comma-separated string. |
| `judge_model` | Optional model that evaluates and ranks multiple responses. Use `null` or remove it to skip judging. |
| `ollama_url` | Ollama chat API endpoint. Usually `http://localhost:11434/api/chat`. |
| `stream` | Whether Ollama streams responses. Keep this as `true` for the current runner. |
| `think` | Enables model thinking output when supported by the model. |
| `show_thinking_in_terminal` | Prints thinking output live in the terminal when `true`. |

## Command Options

Use different prompt files:

```bash
python run_chat.py --system my_system.md --request my_request.md
```

Files are resolved inside the `prompts/` folder. The `.md` extension is optional.

Show thinking output in the terminal:

```bash
python run_chat.py --show-thinking
```

Disable thinking for one run:

```bash
python run_chat.py --no-think
```

## Project Structure

```text
.
|-- chat_runner/
|   |-- config.py      # CLI args and settings
|   |-- files.py       # Shared file helpers
|   |-- judge.py       # Judge prompt and judge run logic
|   |-- ollama.py      # Ollama request and streaming logic
|   |-- paths.py       # Project paths
|   |-- prompts.py     # Prompt loading
|   |-- reports.py     # Markdown, JSON, and HTML report writing
|   `-- stats.py       # Timing and token metrics
|-- prompts/
|   |-- system.md
|   `-- request.md
|-- runs/              # Generated reports
|-- report_html.py     # HTML report renderer
|-- run_chat.py        # Main entry point
|-- settings.json
`-- README.md
```

## Output Files

Each run creates timestamped files:

```text
runs/run-YYYYMMDD-HHMMSS.md
runs/run-YYYYMMDD-HHMMSS.json
runs/run-YYYYMMDD-HHMMSS.html
```

- Markdown is easiest to read in an editor.
- JSON is best for later analysis or scripting.
- HTML is best for sharing or viewing in a browser.

## Notes

- If Ollama is not running, the script will print a connection error.
- If `judge_model` is set, `compare_models` must include at least two models.
- If you only want one model, remove `compare_models` or set it to a single model.
