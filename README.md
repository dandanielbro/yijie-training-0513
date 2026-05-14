# Audio Transcript Pages

這是一個可直接部署到 GitHub Pages 的純靜態頁面骨架，用來承接：

- 錄音檔轉錄結果
- 整理後的逐字稿
- 依講話順序整理的段落標題、Q&A 與段尾重點

## 目前已完成

- `index.html`：主頁面
- `styles.css`：編排與視覺設計
- `app.js`：從 `content/transcript.json` 讀資料並渲染
- `content/transcript.json`：逐字稿內容模板
- `content/terminology-glossary.json`：專有名詞與常見辨識修正候選

## 內容格式

核心資料在 [transcript.json](/Users/dan/Desktop/super-assistant/projects/yijie-home-transcript-site/content/transcript.json)。

每個 `section` 代表一個依時間順序整理出的段落，建議欄位：

- `title`：段落標題
- `focus`：本段一句話摘要
- `kind`：可選，像是 `Q&A`
- `timeRange`：若有時間碼可填
- `highlights`：本段重點列表
- `quote`：保留語氣的一句原話
- `transcript`：整理後逐字稿段落陣列
- `closingSummary`：段尾整理；若缺省，頁面會自動把最後一行 `段落小結：` 拆出來
- `voiceNote`：語氣或情境備註

## 目前採用的整理原則

- 正文優先，不把整段改寫成摘要
- 若原始內容是來回問答，保留在正文結構裡
- 段尾整理與本段重點放在正文之後
- 若講者無法高信心辨識，寧可用保守標示，不硬配姓名
- 專有名詞先看 `content/terminology-glossary.json`，再做上下文修正

## 本機預覽

若要用本機瀏覽器預覽，可在這個資料夾啟動靜態伺服器：

```bash
python3 -m http.server 8123
```

然後打開：

- `http://127.0.0.1:8125/projects/yijie-home-transcript-site/`

## 轉錄現況

建站腳本在 [build_transcript_site.py](/Users/dan/Desktop/super-assistant/projects/yijie-home-transcript-site/scripts/build_transcript_site.py)，目前會：

1. 切音訊 chunk
2. 轉出逐字稿
3. 讀取 `content/terminology-glossary.json`
4. 產出偏逐字稿導向的 `content/transcript.json`

## GitHub Pages

目前這個專案本身已經是獨立 repo，可直接部署到 GitHub Pages。
