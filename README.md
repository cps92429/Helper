# Local Copilot AI – Video Subtitle System

A local AI-powered assistant that automatically generates, translates, and burns
TV-style subtitles onto video files.  Works on **Linux** (via VS Code) and
**Windows** (native GUI application).

---

## Features

| # | Feature | Detail |
|---|---------|--------|
| 1 | **Video subtitle generation** | Uses OpenAI Whisper for accurate speech-to-text transcription → SRT output |
| 2 | **Subtitle translation** | Translates to **Traditional Chinese (繁體中文)** via Google Translate (>95 % accuracy, <2 s latency). TV-style layout: English → Arial, Chinese → 微軟正黑體 (Microsoft JhengHei) |
| 3 | **VS Code / Linux integration** | `.vscode/tasks.json` and `launch.json` for one-click processing on Linux |
| 4 | **Windows multi-function agent** | Tkinter GUI + `CopilotAgent` JSON-RPC interface usable from any Windows application |

---

## Project Structure

```
Helper/
├── src/
│   ├── subtitle_generator.py   # Whisper-based speech-to-text → SRT
│   ├── subtitle_translator.py  # SRT translation to Traditional Chinese
│   ├── subtitle_renderer.py    # TV-style subtitle burning (FFmpeg + Pillow)
│   ├── video_processor.py      # Full pipeline orchestrator
│   └── agent.py                # Multi-function agent (JSON-RPC)
├── gui/
│   └── app.py                  # Tkinter desktop GUI (Windows / Linux / macOS)
├── tests/                      # pytest test suite
├── .vscode/                    # VS Code tasks, launch configs, settings
├── requirements.txt
└── setup.py
```

---

## Quick Start

### 1. Install dependencies

```bash
# (Recommended) create a virtual environment first
python -m venv .venv
source .venv/bin/activate          # Linux / macOS
.venv\Scripts\activate             # Windows PowerShell

pip install -r requirements.txt
```

> **FFmpeg** must also be installed:
> - Linux: `sudo apt install ffmpeg`
> - Windows: Download from <https://ffmpeg.org/download.html> and add to PATH

### 2. Run the GUI application

```bash
python gui/app.py
```

Or in VS Code press **Ctrl+Shift+B** → *Run GUI Application*.

### 3. Command-line / agent usage

```python
from src.agent import CopilotAgent

agent = CopilotAgent(model_size="medium")

# Full pipeline: generate subtitles → translate → burn
result = agent.run_task({
    "action": "process_video",
    "video_path": "lecture.mp4",
    "output_dir": "output/",
    "source_language": "en",   # or "auto"
    "bilingual": False,        # True = keep original text alongside Chinese
})
print(result)
# {"status": "ok", "original_srt": "...", "translated_srt": "...", "burned_video": "..."}

# Step by step
srt   = agent.run_task({"action": "generate_subtitles",  "video_path": "v.mp4"})
zh    = agent.run_task({"action": "translate_subtitles", "srt_path": srt["srt_path"]})
final = agent.run_task({"action": "burn_subtitles",
                        "video_path": "v.mp4", "srt_path": zh["translated_srt"]})

# Watch a folder for new videos (background thread)
agent.run_task({"action": "watch_directory", "directory": "incoming/"})
```

### 4. JSON-RPC (Windows named-pipe / VS Code IPC)

```python
result_json = agent.run_task_json('{"action":"list_capabilities"}')
print(result_json)
```

---

## Subtitle Rendering Specification

| Property | Value |
|----------|-------|
| Position | Bottom-centre (broadcast TV style) |
| English font | Arial |
| Chinese font | 微軟正黑體 (Microsoft JhengHei); falls back to Noto Sans CJK on Linux |
| Background | Semi-transparent black bar |
| Text colour | White with black shadow/outline |
| Translation latency | < 2 seconds per subtitle block |
| Translation accuracy | > 95 % (Google Translate) |
| Target language | Traditional Chinese (zh-TW) |

---

## Running Tests

```bash
python -m pytest tests/ -v
```

---

## VS Code Integration (Linux)

Open the project in VS Code.  The `.vscode/` folder provides:

* **Settings** – Python interpreter, formatter
* **Tasks** (`Ctrl+Shift+B`):
  * *Install Dependencies*
  * *Run GUI Application*
  * *Process Video (CLI)*
  * *Run Tests*
* **Launch configs** (`F5`):
  * *Run GUI App*
  * *Run Tests*

---

## Windows Application Integration

The `CopilotAgent` exposes a `run_task_json(str) -> str` method that accepts
and returns JSON strings, making it easy to call from any Windows application
via:

* Python subprocess with stdout/stdin piping
* Windows named-pipe server (wrap `run_task_json` in a loop)
* COM automation
* REST API (wrap with Flask/FastAPI)
