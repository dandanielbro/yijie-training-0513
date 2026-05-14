#!/usr/bin/env python3
"""Build a GitHub Pages-ready transcript site from a long audio file.

Uses:
- macOS `afconvert` to convert source audio to WAV
- Python stdlib `wave` to split into chunk files
- Gemini API (inline audio) to transcribe each chunk
- Gemini API (text-only) to structure the final transcript.json
"""

from __future__ import annotations

import argparse
import base64
import contextlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import textwrap
import urllib.error
import urllib.parse
import urllib.request
import wave


DEFAULT_MODEL = "gemini-2.0-flash"
DEFAULT_CHUNK_SECONDS = 420
TRANSCRIBE_TEMPERATURE = 0.2
STRUCTURE_TEMPERATURE = 0.4
GLOSSARY_RELATIVE_PATH = Path("content/terminology-glossary.json")


def die(message: str, code: int = 1) -> None:
    print(f"Error: {message}", file=sys.stderr)
    raise SystemExit(code)


def log(message: str) -> None:
    print(message, file=sys.stderr)


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def slugify(value: str) -> str:
    text = re.sub(r"[^\w\s-]", "", value, flags=re.UNICODE)
    text = re.sub(r"[\s_]+", "-", text.strip(), flags=re.UNICODE)
    return text.lower() or "audio-transcript"


def ensure_api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        die("GEMINI_API_KEY is not set.")
    return key


def load_glossary(site_dir: Path) -> dict:
    glossary_path = site_dir / GLOSSARY_RELATIVE_PATH
    if not glossary_path.exists():
        return {}
    try:
        return json.loads(glossary_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        die(f"Invalid glossary JSON: {glossary_path} ({error})")


def render_glossary_prompt(glossary: dict) -> str:
    preferred_terms = glossary.get("preferred_terms") or []
    notes = glossary.get("notes") or []
    if not preferred_terms and not notes:
        return "目前沒有提供額外專有名詞庫。"

    lines = ["本次整理請優先參考以下專有名詞與寫法："]

    for item in preferred_terms:
        canonical = item.get("canonical", "").strip()
        aliases = [alias.strip() for alias in item.get("aliases", []) if alias.strip()]
        if not canonical:
            continue
        alias_text = f"（常見誤寫：{', '.join(aliases)}）" if aliases else ""
        lines.append(f"- {canonical}{alias_text}")

    for note in notes:
        lines.append(f"- 備註：{note}")

    return "\n".join(lines)


def ensure_wav(audio_path: Path, wav_path: Path) -> None:
    if wav_path.exists():
      return
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    log(f"Converting to WAV: {wav_path.name}")
    run([
        "afconvert",
        "-f",
        "WAVE",
        "-d",
        "LEI16@16000",
        str(audio_path),
        str(wav_path),
    ])


def split_wav(wav_path: Path, output_dir: Path, chunk_seconds: int) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    with contextlib.closing(wave.open(str(wav_path), "rb")) as reader:
        params = reader.getparams()
        framerate = reader.getframerate()
        frames_per_chunk = framerate * chunk_seconds
        total_frames = reader.getnframes()
        total_chunks = math.ceil(total_frames / frames_per_chunk)
        chunk_paths: list[Path] = []

        for index in range(total_chunks):
            start_frame = index * frames_per_chunk
            chunk_frame_count = min(frames_per_chunk, total_frames - start_frame)
            start_seconds = start_frame / framerate
            end_seconds = (start_frame + chunk_frame_count) / framerate
            chunk_name = (
                f"chunk_{index + 1:03d}_"
                f"{format_seconds_as_id(start_seconds)}_"
                f"{format_seconds_as_id(end_seconds)}.wav"
            )
            chunk_path = output_dir / chunk_name
            chunk_paths.append(chunk_path)
            if chunk_path.exists():
                continue

            reader.setpos(start_frame)
            frames = reader.readframes(chunk_frame_count)
            with contextlib.closing(wave.open(str(chunk_path), "wb")) as writer:
                writer.setparams(params)
                writer.writeframes(frames)

    return chunk_paths


def audio_duration_seconds(wav_path: Path) -> float:
    with contextlib.closing(wave.open(str(wav_path), "rb")) as reader:
        return reader.getnframes() / float(reader.getframerate())


def format_seconds(seconds: float) -> str:
    total = int(round(seconds))
    hours = total // 3600
    minutes = (total % 3600) // 60
    secs = total % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_seconds_as_id(seconds: float) -> str:
    total = int(round(seconds))
    hours = total // 3600
    minutes = (total % 3600) // 60
    secs = total % 60
    return f"{hours:02d}{minutes:02d}{secs:02d}"


def gemini_generate(api_key: str, model: str, parts: list[dict], temperature: float) -> str:
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        + urllib.parse.quote(model, safe="")
        + ":generateContent?key="
        + urllib.parse.quote(api_key, safe="")
    )
    payload = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "temperature": temperature,
        },
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=600) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        die(f"Gemini API failed: HTTP {error.code} {body[:1000]}")

    data = json.loads(raw)
    candidates = data.get("candidates") or []
    if not candidates:
        die(f"Gemini returned no candidates: {raw[:1000]}")

    content = candidates[0].get("content") or {}
    output_parts = content.get("parts") or []
    texts = [part.get("text", "") for part in output_parts if part.get("text")]
    if not texts:
        die(f"Gemini returned no text parts: {raw[:1000]}")
    return "\n".join(texts).strip()


def transcribe_chunk(
    api_key: str,
    model: str,
    chunk_path: Path,
    chunk_index: int,
    total_chunks: int,
    start_seconds: float,
    end_seconds: float,
    glossary_prompt: str,
) -> str:
    audio_data = base64.b64encode(chunk_path.read_bytes()).decode("ascii")
    prompt = textwrap.dedent(
        f"""
        你是一位逐字稿整理助理。請針對這段中文口語錄音做純轉錄。

        要求：
        1. 只輸出逐字稿內容，不要加說明、不要加摘要、不要加 Markdown。
        2. 使用繁體中文。
        3. 保留原本說話順序與語氣，避免自己重組論點。
        4. 刪除明顯贅字、重複口頭禪與無意義停頓，但不要過度潤稿。
        5. 若有聽不清楚的地方，可用最合理的詞推定，但不要胡亂補內容。
        6. 這是整段錄音的第 {chunk_index} / {total_chunks} 段，時間範圍約 {format_seconds(start_seconds)} - {format_seconds(end_seconds)}。
        7. 優先遵守以下專有名詞庫與寫法：
        {glossary_prompt}
        """
    ).strip()
    return gemini_generate(
        api_key,
        model,
        [
            {"text": prompt},
            {
                "inline_data": {
                    "mime_type": "audio/wav",
                    "data": audio_data,
                }
            },
        ],
        TRANSCRIBE_TEMPERATURE,
    )


def extract_json_object(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in model output.")
    return json.loads(cleaned[start : end + 1])


def parse_timestamp_from_name(audio_path: Path) -> str:
    match = re.match(r"(\d{4})-(\d{2})-(\d{2})_(\d{2})_(\d{2})_(\d{2})", audio_path.stem)
    if not match:
        return audio_path.stem
    return (
        f"{match.group(1)}/{match.group(2)}/{match.group(3)} "
        f"{match.group(4)}:{match.group(5)}:{match.group(6)}"
    )


def fallback_transcript_json(title: str, recorded_at: str, duration: str, transcript_text: str) -> dict:
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", transcript_text) if p.strip()]
    return {
        "title": title,
        "subtitle": "依照錄音原始順序整理的逐字稿，保留語氣並去掉多餘贅字。",
        "contentNote": "目前為自動整理初稿；後續可再依需要修正文句、補標題與加註重點。",
        "audio": {
            "url": "./media/original.mp3",
            "label": "原始音檔"
        },
        "meta": {
            "speaker": "待補",
            "recordedAt": recorded_at,
            "duration": duration,
            "status": "已完成初稿"
        },
        "editorialRules": [
            "維持原始談話順序，不任意重組觀點。",
            "保留口語節奏與說話溫度，但刪除明顯贅字與重複詞。",
            "遇到不合理辨識詞時，以最符合上下文的版本修正。",
            "後續若要公開發布，建議再做一次人工校稿。"
        ],
        "summaryHighlights": [
            "這份頁面已完成自動轉錄與初步整理。",
            "若要提高可讀性，可再補段落標題與摘要。",
            "若內容涉及隱私，發布前建議先人工檢查。"
        ],
        "sections": [
            {
                "id": "full-transcript",
                "kicker": "Full Transcript",
                "title": "完整逐字稿初稿",
                "focus": "這一版先保留全文內容，後續可再進一步切段整理。",
                "timeRange": f"00:00 - {duration}",
                "tag": "auto-draft",
                "highlights": [
                    "已完成語音轉文字。",
                    "已保留原始談話順序。",
                    "仍建議人工校稿後再公開分享。"
                ],
                "quote": "",
                "transcript": paragraphs or [transcript_text.strip()],
                "voiceNote": "目前為自動轉錄與自動整理的初稿版本。"
            }
        ]
    }


def structure_transcript(
    api_key: str,
    model: str,
    title: str,
    recorded_at: str,
    duration: str,
    transcript_text: str,
    glossary_prompt: str,
) -> dict:
    prompt = textwrap.dedent(
        f"""
        請把下面這份長錄音逐字稿，整理成一個可以直接給靜態網站使用的 JSON 物件。

        你只能輸出 JSON，不能輸出 markdown、不能輸出額外說明。

        JSON schema:
        {{
          "title": string,
          "subtitle": string,
          "contentNote": string,
          "audio": {{
            "url": "./media/original.mp3",
            "label": string
          }},
          "meta": {{
            "speaker": string,
            "recordedAt": "{recorded_at}",
            "duration": "{duration}",
            "status": string
          }},
          "editorialRules": string[],
          "summaryHighlights": string[],
          "sections": [
            {{
              "id": string,
              "kicker": string,
              "title": string,
              "focus": string,
              "kind": string,
              "timeRange": string,
              "tag": string,
              "highlights": string[],
              "quote": string,
              "transcript": string[],
              "closingSummary": string,
              "voiceNote": string
            }}
          ]
        }}

        規則：
        1. 使用繁體中文。
        2. 保留原始談話順序，不重排論點。
        3. sections 請切成 8 到 16 段左右，依主題自然分段。
        4. 每段 transcript 請整理成 1 到 4 個段落。
        5. 可修正明顯不合理辨識詞，但不要擅自新增沒說過的內容。
        6. `title` 請基於內容與檔名 `{title}` 命名，不要保留模板字樣。
        7. `meta.recordedAt` 固定填 `{recorded_at}`，`meta.duration` 固定填 `{duration}`，`audio.url` 固定填 `./media/original.mp3`。
        8. 如果講者身份不明，逐句不要硬配姓名；可用「學員」等保守標示。
        9. `status` 請填「已完成自動整理初稿」。
        10. 正文優先，不要把整段寫成摘要。
        11. 若該段有來回問答，請保留 Q&A 在 transcript 正文裡，並可將 `kind` 填成 `Q&A`。
        12. 段尾整理請放進 `closingSummary`，不要把「段落小結：」混進 transcript 陣列。
        13. 優先遵守以下專有名詞庫與寫法：
        {glossary_prompt}

        逐字稿如下：
        {transcript_text}
        """
    ).strip()
    text = gemini_generate(api_key, model, [{"text": prompt}], STRUCTURE_TEMPERATURE)
    return extract_json_object(text)


def write_chunk_transcripts(
    api_key: str,
    model: str,
    chunk_paths: list[Path],
    output_dir: Path,
    chunk_seconds: int,
    max_chunks: int | None,
    glossary_prompt: str,
) -> tuple[list[str], list[Path]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    transcripts: list[str] = []
    transcript_paths: list[Path] = []

    selected_chunk_paths = chunk_paths[:max_chunks] if max_chunks else chunk_paths

    for index, chunk_path in enumerate(selected_chunk_paths, start=1):
        start_seconds = (index - 1) * chunk_seconds
        end_seconds = start_seconds + chunk_seconds
        transcript_path = output_dir / (chunk_path.stem + ".txt")
        transcript_paths.append(transcript_path)
        if transcript_path.exists():
            text = transcript_path.read_text(encoding="utf-8").strip()
            transcripts.append(text)
            log(f"Reuse transcript: {transcript_path.name}")
            continue

        log(f"Transcribing chunk {index}/{len(chunk_paths)}: {chunk_path.name}")
        text = transcribe_chunk(
            api_key,
            model,
            chunk_path,
            index,
            len(selected_chunk_paths),
            start_seconds,
            end_seconds,
            glossary_prompt,
        )
        transcript_path.write_text(text.strip() + "\n", encoding="utf-8")
        transcripts.append(text.strip())

    return transcripts, transcript_paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Build transcript site content from audio.")
    parser.add_argument("audio", help="Path to source audio file")
    parser.add_argument("--site-dir", default=".", help="Transcript site directory")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Gemini model to use")
    parser.add_argument("--chunk-seconds", type=int, default=DEFAULT_CHUNK_SECONDS, help="Chunk length in seconds")
    parser.add_argument("--max-chunks", type=int, default=0, help="Only process the first N chunks for testing")
    args = parser.parse_args()

    api_key = ensure_api_key()
    audio_path = Path(args.audio).expanduser().resolve()
    if not audio_path.exists():
        die(f"Audio file not found: {audio_path}")

    site_dir = Path(args.site_dir).expanduser().resolve()
    content_dir = site_dir / "content"
    media_dir = site_dir / "media"
    output_dir = site_dir / "output" / "transcribe" / slugify(audio_path.stem)
    wav_path = output_dir / "source.wav"
    chunk_dir = output_dir / "chunks"
    transcript_dir = output_dir / "chunk-transcripts"
    combined_transcript_path = output_dir / "combined-transcript.txt"
    transcript_json_path = content_dir / "transcript.json"
    glossary = load_glossary(site_dir)
    glossary_prompt = render_glossary_prompt(glossary)

    ensure_wav(audio_path, wav_path)
    duration_seconds = audio_duration_seconds(wav_path)
    duration_text = format_seconds(duration_seconds)

    chunk_paths = split_wav(wav_path, chunk_dir, args.chunk_seconds)
    log(f"Prepared {len(chunk_paths)} chunk files.")

    chunk_texts, _ = write_chunk_transcripts(
        api_key,
        args.model,
        chunk_paths,
        transcript_dir,
        args.chunk_seconds,
        args.max_chunks or None,
        glossary_prompt,
    )

    combined_transcript = "\n\n".join(
        [
            f"[{format_seconds((index - 1) * args.chunk_seconds)} - {format_seconds(min(index * args.chunk_seconds, duration_seconds))}]\n{text}"
            for index, text in enumerate(chunk_texts, start=1)
        ]
    ).strip()
    combined_transcript_path.write_text(combined_transcript + "\n", encoding="utf-8")
    log(f"Wrote combined transcript: {combined_transcript_path}")

    page_title = audio_path.stem
    recorded_at = parse_timestamp_from_name(audio_path)

    try:
        transcript_json = structure_transcript(
            api_key,
            args.model,
            page_title,
            recorded_at,
            duration_text,
            combined_transcript,
            glossary_prompt,
        )
    except Exception as error:
        log(f"Structured JSON generation failed, using fallback: {error}")
        transcript_json = fallback_transcript_json(
            page_title,
            recorded_at,
            duration_text,
            combined_transcript,
        )

    transcript_json.setdefault("audio", {})
    transcript_json["audio"]["url"] = "./media/original.mp3"
    transcript_json["audio"]["label"] = transcript_json["audio"].get("label") or "原始音檔"

    media_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(audio_path, media_dir / "original.mp3")
    transcript_json_path.write_text(
        json.dumps(transcript_json, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    log(f"Wrote transcript JSON: {transcript_json_path}")
    log(f"Copied original audio to: {media_dir / 'original.mp3'}")


if __name__ == "__main__":
    main()
