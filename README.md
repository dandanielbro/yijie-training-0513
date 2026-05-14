# Audio Transcript Pages

這是一個可直接部署到 GitHub Pages 的純靜態頁面骨架，用來承接：

- 錄音檔轉錄結果
- 整理後的逐字稿
- 依講話順序整理的段落標題與重點

## 目前已完成

- `index.html`：主頁面
- `styles.css`：編排與視覺設計
- `app.js`：從 `content/transcript.json` 讀資料並渲染
- `content/transcript.json`：逐字稿內容模板

## 內容格式

核心資料在 [content/transcript.json](/Users/dan/Desktop/super-assistant/projects/audio-transcript-pages/content/transcript.json)。

每個 `section` 代表一個依時間順序整理出的段落，建議欄位：

- `title`：段落標題
- `focus`：本段一句話摘要
- `timeRange`：若有時間碼可填
- `highlights`：本段重點列表
- `quote`：保留語氣的一句原話
- `transcript`：整理後逐字稿段落陣列
- `voiceNote`：語氣或情境備註

## 本機預覽

若要用本機瀏覽器預覽，可在這個資料夾啟動靜態伺服器：

```bash
python3 -m http.server 8123
```

然後打開：

- `http://localhost:8123/projects/audio-transcript-pages/`

## 轉錄現況

這個 workspace 目前尚未具備直接轉錄所需條件：

- `OPENAI_API_KEY` 尚未在目前 shell 環境中設定
- `~/.codex/skills/transcribe/scripts/transcribe_diarize.py` 目前不存在
- 本機也尚未安裝 `whisper` 或 `ffmpeg`

因此下一步有兩種路徑：

1. 使用 OpenAI 轉錄流程：先把環境補齊，再對上傳的音檔做轉錄。
2. 若你已有初步逐字稿：可直接整理後填入 `content/transcript.json`，立即產出頁面。

## GitHub Pages

因為這個 workspace 目前不是一個已連到 GitHub 的 repo，所以我先把「可部署的靜態站內容」建好。等你要正式發布時，可以：

1. 把 `projects/audio-transcript-pages/` 放進目標 repo。
2. 在 GitHub Pages 設定中指定這個資料夾對應的 branch / root。
3. 或者我之後再幫你補成獨立 repo 與自動部署流程。
