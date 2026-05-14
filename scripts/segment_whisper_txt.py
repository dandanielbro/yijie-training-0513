#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path


CONSOLE_LINE_RE = re.compile(
    r"^\[(?P<start>\d{2}:\d{2}:\d{2}\.\d{3})\s+-->\s+(?P<end>\d{2}:\d{2}:\d{2}\.\d{3})\]\s+(?P<text>.+?)\s*$"
)
SRT_INDEX_RE = re.compile(r"^\d+$")
SRT_TIME_RE = re.compile(
    r"^(?P<start>\d{2}:\d{2}:\d{2}[,.]\d{3})\s+-->\s+(?P<end>\d{2}:\d{2}:\d{2}[,.]\d{3})$"
)


@dataclass
class Segment:
    start: str
    end: str
    text: str


def parse_timestamp(value: str) -> int:
    value = value.replace(",", ".")
    hours, minutes, seconds = value.split(":")
    secs, millis = seconds.split(".")
    return (
        int(hours) * 3600 * 1000
        + int(minutes) * 60 * 1000
        + int(secs) * 1000
        + int(millis)
    )


def format_timestamp(ms: int) -> str:
    total_seconds = ms // 1000
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def normalize_text(text: str) -> str:
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"([。！？])\1+", r"\1", text)
    return text


def dedupe_consecutive(texts: list[str]) -> list[str]:
    items: list[str] = []
    previous = ""
    for text in texts:
        current = normalize_text(text)
        if not current or current == previous:
            continue
        items.append(current)
        previous = current
    return items


def parse_console_segments(text: str) -> list[Segment]:
    segments: list[Segment] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = CONSOLE_LINE_RE.match(line)
        if not match:
            continue
        segments.append(
            Segment(
                start=match.group("start"),
                end=match.group("end"),
                text=normalize_text(match.group("text")),
            )
        )
    return segments


def parse_srt_segments(text: str) -> list[Segment]:
    segments: list[Segment] = []
    blocks = re.split(r"\n\s*\n", text)
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) < 3 or not SRT_INDEX_RE.match(lines[0]):
            continue
        match = SRT_TIME_RE.match(lines[1])
        if not match:
            continue
        segments.append(
            Segment(
                start=match.group("start"),
                end=match.group("end"),
                text=normalize_text(" ".join(lines[2:])),
            )
        )
    return segments


def parse_segments(path: Path) -> list[Segment]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    segments = parse_console_segments(raw)
    if segments:
        return segments
    return parse_srt_segments(raw)


def group_segments(segments: list[Segment], window_minutes: int) -> list[dict]:
    window_ms = window_minutes * 60 * 1000
    groups: list[dict] = []
    current: dict | None = None

    for segment in segments:
        start_ms = parse_timestamp(segment.start)
        end_ms = parse_timestamp(segment.end)

        if current is None:
            current = {
                "start_ms": start_ms,
                "end_ms": end_ms,
                "texts": [segment.text],
            }
            continue

        if start_ms - current["start_ms"] >= window_ms:
            groups.append(current)
            current = {
                "start_ms": start_ms,
                "end_ms": end_ms,
                "texts": [segment.text],
            }
            continue

        current["end_ms"] = end_ms
        current["texts"].append(segment.text)

    if current is not None:
        groups.append(current)

    results: list[dict] = []
    for index, group in enumerate(groups, start=1):
        texts = dedupe_consecutive(group["texts"])
        results.append(
            {
                "id": f"section-{index:03d}",
                "timeRange": f"{format_timestamp(group['start_ms'])} - {format_timestamp(group['end_ms'])}",
                "rawTranscript": " ".join(texts),
                "lineCount": len(texts),
            }
        )
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Group whisper transcript text into time windows.")
    parser.add_argument("input", help="Path to whisper .txt file")
    parser.add_argument("output", help="Path to output JSON file")
    parser.add_argument("--window-minutes", type=int, default=12, help="Minutes per grouped section")
    args = parser.parse_args()

    input_path = Path(args.input).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()

    segments = parse_segments(input_path)
    grouped = group_segments(segments, args.window_minutes)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(grouped, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Parsed segments: {len(segments)}")
    print(f"Generated groups: {len(grouped)}")
    print(f"Output: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
