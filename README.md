# Local Ollama Model Comparison Runner

A small local tool for comparing multiple Ollama models on the same Markdown prompt. It sends one user request to each participant model, saves every answer, asks an optional judge model to score the results in a fixed format, and generates Markdown, JSON, and polished HTML reports.

This project is designed for people who are interested in local LLMs and want a simple way to compare answer quality, latency, token usage, and generation speed.

## Features

- Compare multiple local Ollama models on the same prompt.
- Keep the system prompt and user request in separate Markdown files.
- Optionally use a judge model to score participant outputs.
- Record wall-clock time, token usage, and generation speed.
- Generate three output formats for every run:
  - `.md` for quick reading and archiving.
  - `.json` for structured data and later analysis.
  - `.html` for a readable visual report.

## Requirements

1. Python 3.9 or newer.
2. Ollama installed and running.
3. At least one local model available in Ollama.
4. Two or more models if you want a real model comparison.
5. One additional judge model if you want automatic scoring.

This project uses only the Python standard library. No extra Python packages are required.

## Install Ollama and Models

Install Ollama first:

- Windows and macOS: download it from [https://ollama.com](https://ollama.com).
- Linux: follow the installation instructions on the Ollama website.

After installation, confirm that Ollama is available:

```powershell
ollama --version
```

Pull one model, for example:

```powershell
ollama pull qwen3:14b
```

Pull another model for comparison:

```powershell
ollama pull qwen3.5:9b
```

If you want to use a judge model, pull that model too:

```powershell
ollama pull qwen3.6:35b-a3b
```

List the models installed on your machine:

```powershell
ollama list
```

Model names in `settings.json` must exactly match the names shown by `ollama list`. If your machine does not have the example models, replace them with models you do have.

## Project Structure

```text
.
|-- run_chat.py
|-- report_html.py
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

- `run_chat.py`: main script for loading prompts, calling Ollama, collecting stats, and saving outputs.
- `report_html.py`: standalone HTML report renderer with layout, styling, and visualizations.
- `settings.json`: model names, Ollama endpoint, streaming, thinking, and terminal display settings.
- `prompts/system.md`: system prompt that controls assistant role, style, and rules.
- `prompts/request.md`: user request that every participant model answers.
- `runs/`: timestamped output files from each run.
- `archive/`: old reference files.

## Configure Models

Edit `settings.json`:

```json
{
  "model": "qwen3:14b",
  "compare_models": [
    "qwen3:14b",
    "qwen3.5:9b"
  ],
  "judge_model": "qwen3.6:35b-a3b",
  "ollama_url": "http://localhost:11434/api/chat",
  "stream": true,
  "think": true,
  "show_thinking_in_terminal": false
}
```

Field reference:

- `model`: default model. Used when `compare_models` is not set.
- `compare_models`: participant model list. Each model receives the same prompt.
- `judge_model`: optional model that reads participant answers and produces a scored evaluation.
- `ollama_url`: Ollama Chat API endpoint. The default is usually `http://localhost:11434/api/chat`.
- `stream`: whether to stream model output.
- `think`: whether to request thinking mode. Support depends on the model.
- `show_thinking_in_terminal`: whether to print thinking content in the terminal.

If you do not want automatic judging, remove `judge_model` or set it to `null`.

## Write a Prompt

Edit `prompts/request.md`:

```md
# User Request

What were the underlying causes of World War II?
```

Edit `prompts/system.md` to control answer style. For example, you can ask models to be concise, structured, practical, or to answer in a specific language.

## Run

From the project directory:

```powershell
python run_chat.py
```

The terminal will show each model's output. When the run finishes, new output files will appear in `runs/`.

## Useful Options

Show thinking in the terminal:

```powershell
python run_chat.py --show-thinking
```

Disable thinking:

```powershell
python run_chat.py --no-think
```

Use another request file from `prompts/`:

```powershell
python run_chat.py --request coding-task.md
```

Use another system prompt file:

```powershell
python run_chat.py --system strict-judge.md
```

## Output Reports

Each run creates files like:

```text
runs/run-20260503-113621.md
runs/run-20260503-113621.json
runs/run-20260503-113621.html
```

The HTML report includes:

- participant model names and judge model name;
- a summary of the user request;
- basic model information;
- visual comparisons for latency, token usage, and generation speed;
- full answers from every participant model;
- judge scoring, per-model comments, final recommendation, and notes.

The judge model is prompted to use a fixed Markdown structure so the report is easier to read consistently.

## Troubleshooting

### Cannot connect to Ollama

If you see `Could not connect to Ollama`, check whether Ollama is running:

```powershell
ollama list
```

If this command fails, the Ollama service may not be running.

### Model not found

Check installed models:

```powershell
ollama list
```

Then update `compare_models` and `judge_model` in `settings.json` to match local model names.

### The run is slow

Local model speed depends on model size, CPU/GPU, memory, and VRAM. You can try:

- using smaller models;
- reducing the number of `compare_models`;
- disabling thinking:

```powershell
python run_chat.py --no-think
```

### Judge output format is not perfectly consistent

The judge prompt asks for a fixed Markdown format, but models may occasionally deviate. For stricter consistency, a future improvement would be to ask the judge for JSON and render the final scorecard from that structured data.

## Verify `system.md`

To check whether `prompts/system.md` is being used, temporarily add an obvious rule:

```md
Always start your final answer with: SYSTEM PROMPT ACTIVE
```

Then run:

```powershell
python run_chat.py
```

If the answer starts with that phrase, the system prompt is active.
