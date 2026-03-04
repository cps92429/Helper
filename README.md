# Helper

Local Codex-style code assistant starter that runs entirely on your machine.

## Prerequisites

- Python 3.10+ (virtual env recommended)
- Enough disk/RAM for the model (GPU optional, speeds up large models)
- Optional: git-lfs if you plan to cache larger checkpoints

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Windows Quick Start

Use the one-click bootstrap script in Command Prompt or PowerShell:

```bat
bootstrap.bat
```

Launch the Streamlit task panel (double-click friendly):

```bat
run_ui.bat
```

Manual setup on Windows (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Run a local model

- Default model: `bigcode/starcoder2-3b` (compact, Codex-like).
- Example: `python local_ai.py --prompt "Write a Python function that reverses a string."`
- Switch models with `--model`, e.g. `--model codellama/CodeLlama-7b-Instruct-hf` (needs a GPU).
- If the primary model fails to load, it automatically falls back to `distilgpt2`.
- Set a custom fallback with `--fallback-model <model-id>`.
- Disable fallback with `--fallback-model none`.
- Enable load retries with `--load-retries` (default: `2`).
- Adjust retry interval with `--retry-delay` seconds (default: `1.5`).
- Control output with `--max-new-tokens`, `--temperature`, and `--top-p`.

## Use your local context

- Paste filenames or snippets into the prompt:  
  `python local_ai.py --prompt "Here is my config: $(cat config.yaml). Improve error handling."`
- No data leaves your machine except when downloading the model on first run.

## Notes

- First run downloads weights to `~/.cache/huggingface/hub`; subsequent runs are offline.
- For strictly offline use, pre-download with `huggingface-cli download <model>`.

## Troubleshooting

- **Model load fails intermittently (network/cache hiccups)**
  - Increase retries: `--load-retries 4 --retry-delay 2`
  - Keep fallback enabled so the runner can switch models automatically.

- **CUDA requested but no GPU detected**
  - Use `--device auto` or `--device cpu`.

- **Both primary and fallback models fail**
  - Verify model IDs and internet access for first download.
  - Try a smaller model, e.g. `--model distilgpt2 --fallback-model none`.
  - Ensure dependencies are installed: `pip install -r requirements.txt`.
