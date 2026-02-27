# Helper

這是一個 Windows 腳本工具箱（以 PowerShell 為主），並內建兩個多功能 Agent：
- Agent 1（影片字幕）：翻譯影片、生成字幕、字幕設計、可預覽視窗、一鍵拖曳生成、字幕套用
- Agent 2（文書/Excel）：統整 Excel 表格資料、自動管理 Excel

## 目錄規範
- `agents/`：Agent 實作
- `Output/`：所有輸出產物（避免把生成檔混在 repo root）
- 其他可用輸出資料夾：`source/`、`subtitles/`

## 安裝相依套件（可透過網路下載）
建立本機 venv 並安裝套件：

```powershell
cd C:\Users\cps92\Projects\Helper
.\setup.ps1 -Target All
```

## 學習你提供的 Faster-Whisper 安裝包
你提供的資料夾（已納入 Agent1 自動偵測）：

- `C:\Users\cps92\OneDrive\Videos\Pictures\Desktop\Faster-Whisper-XXL_Pro_r3.256.1_windows__cps92429@gmail.com`

其中 `faster-whisper-xxl.exe` 路徑已寫入：

- `C:\Users\cps92\Projects\Helper\agents\agent1-video-subtitle\agent1.config.json`

Agent1 轉錄時會優先使用該 `faster-whisper-xxl.exe`（找不到才回退用 `C:\Users\cps92\turbo-transcribe.ps1`）。

### 依檔案大小自動選模型（Auto Model）
設定檔：
- `C:\Users\cps92\Projects\Helper\agents\agent1-video-subtitle\agent1.config.json`

欄位：
- `transcription.model_policy.enabled`：是否啟用
- `transcription.model_policy.rules`：依檔案大小（MB）選模型
- `transcription.model_policy.fallback_model`：無法判斷時用的預設模型

預設規則（可自行調整）：
- `<= 200MB` 用 `medium`
- `<= 1500MB` 用 `small`
- 其他用 `base`


## Agent Hub（統一入口）
`agent-hub.ps1` 是單一入口，負責路由到 Agent1 / Agent2。

## 字幕工作室 UI（不卡 UI + 進度條 + 批次）
啟動 UI（背景執行緒處理，不會卡視窗）：

```powershell
.\agent-hub.ps1 -Agent agent1 -Task video.ui
```

### 功能對應（你提出的 1-10）
- 分層架構：`agents\agent1-video-subtitle\studio\`（services/config） + `ui\`
- 多執行緒不卡 UI：UI 以背景執行緒跑轉錄/翻譯/轉檔
- 進度條：每個工作步驟會更新進度
- SRT + ASS：可同時產出 `.srt` 與 `.ass`
- 可擴充批次處理：工作佇列 + runner（可加新任務）
- 雙語上下排版自動最佳化：輸出 `*.bilingual.ass`（Top/Bottom style）
- 智慧斷句：輸出 `*.smart.srt`（比原生輸出更易讀）
- 批次資料夾處理：UI「新增資料夾…」或用 `Batch-Folder.ps1`
- 一鍵燒錄進影片：輸出 `*.burned.mp4`
- 可調整字幕樣式：改 `agents\agent1-video-subtitle\style.json`

### Agent1：生成字幕（呼叫你現有的 turbo-transcribe 工作流程）
```powershell
.\agent-hub.ps1 -Agent agent1 -Task video.subtitles.generate -InputPath "D:\media\clip.mp4"
```

### Agent1：翻譯影片成英文字幕（Whisper translate）
```powershell
.\agent-hub.ps1 -Agent agent1 -Task video.translate -InputPath "D:\media\clip.mp4"
```

### Agent1：字幕設計（SRT -> ASS，預設字型微軟正黑體）
```powershell
.\agent-hub.ps1 -Agent agent1 -Task video.subtitles.design -InputPath "C:\path\to\subtitles.srt"
```

### Agent1：字幕預覽視窗（SRT）
```powershell
.\agent-hub.ps1 -Agent agent1 -Task video.subtitles.preview -InputPath "C:\path\to\subtitles.srt"
```

### Agent1：更像人工的專業繁中翻譯（Copilot 模型，輸出 zh-TW SRT）
先有一份原文字幕（`.srt`）後，執行：

```powershell
.\agents\agent1-video-subtitle\Invoke-Agent1.ps1 -Task subtitles.translate.pro -InputPath "C:\path\to\subtitles.srt"
```

輸出預設在 `Output\`，檔名為 `*.zh-TW.srt`。

若第一次使用遇到驗證失敗，先登入 Copilot CLI（只需做一次）：

```powershell
gh copilot -- login
```

翻譯後會再用 OpenCC（預設 `s2twp`）強制轉為繁體中文，避免殘留簡體字。

### Agent1：字幕套用到影片（燒錄/內嵌）
```powershell
.\agents\agent1-video-subtitle\Apply-Subtitles.ps1 -VideoPath "D:\media\clip.mp4" -SubtitlePath "C:\path\to\subtitles.ass" -Mode burn
.\agents\agent1-video-subtitle\Apply-Subtitles.ps1 -VideoPath "D:\media\clip.mp4" -SubtitlePath "C:\path\to\subtitles.srt" -Mode mux
```

### 一鍵拖曳（Agent1）
把影片檔拖曳到：
- `agents\agent1-video-subtitle\agent1-drag-drop.bat`

這會依序執行：
- 生成字幕（輸出到 `Output/`）
- 字幕設計（SRT -> ASS）
- 開啟字幕預覽視窗（SRT）

### 一鍵拖曳燒錄（Agent1）
把影片檔拖曳到：
- `agents\agent1-video-subtitle\agent1-drag-drop-burn.bat`

預設流程：
- 生成字幕（轉錄）
- 智慧斷句（`*.smart.srt`）
- 專業翻譯繁中（Copilot，產生 `*.zh-TW.srt`）
- 產生雙語上下 `*.bilingual.ass`
- 燒錄成 `*.burned.mp4`

提示：第一次使用「專業翻譯」前請先跑一次 `gh copilot -- login`。

## 批次資料夾處理（CLI）
```powershell
cd C:\Users\cps92\Projects\Helper
.\agents\agent1-video-subtitle\Batch-Folder.ps1 -FolderPath "D:\media" -Recursive -SmartSegment -ProTranslate -BilingualAss -BurnIn
```

## 字幕樣式（style.json）
調整：
- `agents\agent1-video-subtitle\style.json`

常用欄位：
- `fontname`, `fontsize`
- `outline`, `shadow`
- `margin_v_top`, `margin_v_bottom`（雙語上下位置）

## Agent2：Excel 統整 / 自動管理
### 統整 Excel（輸出 summary CSV）
```powershell
.\agent-hub.ps1 -Agent agent2 -Task excel.summarize -InputPath "C:\path\to\data.xlsx"
```

### 自動管理 Excel（輸出 managed xlsx，不會改動原檔）
```powershell
.\agent-hub.ps1 -Agent agent2 -Task excel.automanage -InputPath "C:\path\to\data.xlsx"
```

備註：如果你有安裝桌面版 Excel，會嘗試用 COM 進行 AutoFit 與 Freeze Panes；沒有 Excel 也會輸出一份複製檔（不會失敗）。

## Agent1 委派 Agent2（示例）
你也可以用 Agent1 直接呼叫 Agent2 來做文書：

```powershell
.\agents\agent1-video-subtitle\Invoke-Agent1.ps1 -Task agent2.excel.summarize -InputPath "C:\path\to\data.xlsx"
```

## Copilot（專案規範）
本 repo 內建：
- `AGENTS.md`：Agent/工具的工作規範
- `.github/copilot-instructions.md`：Copilot 專用指引
- `.vscode/`：推薦擴充套件與 workspace 設定
