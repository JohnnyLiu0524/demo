# Local Ollama Model Comparison Runner

A small local project for comparing the same Markdown prompt across multiple Ollama models and saving readable comparison runs.

## Structure

```text
.
|-- run_chat.py
|-- settings.json
|-- prompts/
|   |-- system.md
|   `-- request.md
|-- runs/
|   |-- run-YYYYMMDD-HHMMSS.md
|   |-- run-YYYYMMDD-HHMMSS.json
|   `-- run-YYYYMMDD-HHMMSS.html
`-- archive/
    `-- legacy-prompt.md
```

## Files

- `run_chat.py`: main script.
- `settings.json`: model name, Ollama endpoint, streaming, thinking, and terminal display settings.
- `prompts/system.md`: assistant role, behavior, and rules.
- `prompts/request.md`: the current user request.
- `runs/`: timestamped Markdown, JSON, and HTML outputs from each run.
- `archive/`: old files kept only for reference.

## Basic Run

```powershell
python run_chat.py
```

## Useful Options

Show thinking live in the terminal:

```powershell
python run_chat.py --show-thinking
```

Disable thinking for a faster answer:

```powershell
python run_chat.py --no-think
```

Use a different request file from `prompts/`:

```powershell
python run_chat.py --request coding-task.md
```

Configure the models to compare in `settings.json` under `compare_models`. Optionally add `judge_model` to have a third model evaluate the participant outputs and produce a summary report in the same Markdown run file.

Each run also creates a polished HTML report in `runs/`. The report includes:

- basic information for each participant model and the judge model;
- the exact question/prompt used for the comparison;
- each model's final answer;
- the judge model's scoring result and recommendation.

Example `settings.json`:

```json
{
  "model": "qwen3:14b",
  "compare_models": [
    "qwen3:14b",
    "qwen3.6:35b-a3b"
  ],
  "judge_model": "qwen3.6:35b-a3b",
  "ollama_url": "http://localhost:11434/api/chat",
  "stream": true,
  "think": true,
  "show_thinking_in_terminal": false
}
```

## Check Whether `system.md` Is Working

Edit `prompts/system.md` with an obvious rule, for example:

```md
Always start your final answer with: SYSTEM PROMPT ACTIVE
```

Then run:

```powershell
python run_chat.py
```

If the answer starts with that phrase, the system prompt is being used. Each file in `runs/` also saves the exact system prompt used for that run.
