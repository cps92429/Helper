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

## Run a local model
- Default model: `bigcode/starcoder2-3b` (compact, Codex-like).
- Example: `python local_ai.py --prompt "Write a Python function that reverses a string."`
- Switch models with `--model`, e.g. `--model codellama/CodeLlama-7b-Instruct-hf` (needs a GPU).
- Control output with `--max-new-tokens`, `--temperature`, and `--top-p`.

## Use your local context
- Paste filenames or snippets into the prompt:  
  `python local_ai.py --prompt "Here is my config: $(cat config.yaml). Improve error handling."`
- No data leaves your machine except when downloading the model on first run.

## Notes
- First run downloads weights to `~/.cache/huggingface/hub`; subsequent runs are offline.
- For strictly offline use, pre-download with `huggingface-cli download <model>`.
