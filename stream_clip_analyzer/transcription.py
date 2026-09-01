from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Callable

from .models import TranscriptSegment
from .timecode import format_timecode


class Transcriber:
    _models: dict[str, object] = {}

    def transcribe(
        self,
        source: str | Path,
        model_name: str = "small",
        suppress_hallucination: bool = True,
        status: Callable[[str], None] | None = None,
    ) -> list[TranscriptSegment]:
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError("faster-whisper がインストールされていません") from exc
        if model_name not in self._models:
            if status:
                status(f"Whisper {model_name} モデルを準備中…")
            self._models[model_name] = WhisperModel(model_name, device="auto", compute_type="auto")
        if status:
            status("文字起こし中…")
        options = {
            "language": "ja", "beam_size": 5, "vad_filter": True,
            "condition_on_previous_text": not suppress_hallucination,
        }
        if suppress_hallucination:
            options.update(
                temperature=0.0,
                compression_ratio_threshold=2.2,
                log_prob_threshold=-1.0,
                no_speech_threshold=0.6,
                repetition_penalty=1.15,
                vad_parameters={"min_silence_duration_ms": 500},
            )
        segments, _ = self._models[model_name].transcribe(str(source), **options)
        result: list[TranscriptSegment] = []
        for segment in segments:
            text = segment.text.strip()
            if text:
                result.append(TranscriptSegment(float(segment.start), float(segment.end), text))
        return result


def save_transcript(segments: list[TranscriptSegment], output_dir: str | Path, stem: str) -> list[Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    txt_path = output_dir / f"{stem}_transcript.txt"
    csv_path = output_dir / f"{stem}_transcript.csv"
    json_path = output_dir / f"{stem}_transcript.json"
    txt_path.write_text("\n\n".join(
        f"[{format_timecode(s.start)} - {format_timecode(s.end)}]\n{s.text}" for s in segments
    ) + "\n", encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(["segment_id", "start_seconds", "end_seconds", "start", "end", "text"])
        for i, s in enumerate(segments, 1):
            writer.writerow([i, s.start, s.end, format_timecode(s.start), format_timecode(s.end), s.text])
    json_path.write_text(json.dumps([
        {"segment_id": i, "start_seconds": s.start, "end_seconds": s.end,
         "start": format_timecode(s.start), "end": format_timecode(s.end), "text": s.text}
        for i, s in enumerate(segments, 1)
    ], ensure_ascii=False, indent=2), encoding="utf-8")
    return [txt_path, csv_path, json_path]
