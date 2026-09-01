from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(slots=True)
class TranscriptSegment:
    start: float
    end: float
    text: str


@dataclass(slots=True)
class ClipCandidate:
    name: str
    start: float
    end: float
    vertical: bool = False
    confirmed: bool = False
    preview_path: str | None = None

    def __post_init__(self) -> None:
        self.start = max(0.0, float(self.start))
        self.end = float(self.end)
        if self.end <= self.start:
            raise ValueError("終了時刻は開始時刻より後にしてください")

    @property
    def duration(self) -> float:
        return self.end - self.start

    def adjust(self, edge: str, delta: float, media_duration: float | None = None) -> None:
        if edge == "start":
            value = max(0.0, self.start + delta)
            if value >= self.end:
                raise ValueError("開始時刻は終了時刻より前にしてください")
            self.start = value
        elif edge == "end":
            value = self.end + delta
            if media_duration is not None:
                value = min(value, media_duration)
            if value <= self.start:
                raise ValueError("終了時刻は開始時刻より後にしてください")
            self.end = value
        else:
            raise ValueError(f"不明な調整対象: {edge}")
        self.confirmed = False
        self.preview_path = None

    def set_range(self, start: float, end: float, media_duration: float | None = None) -> None:
        start = max(0.0, float(start))
        end = float(end)
        if media_duration is not None:
            end = min(end, media_duration)
        if end <= start:
            raise ValueError("終了時刻は開始時刻より後にしてください")
        self.start, self.end = start, end
        self.confirmed = False
        self.preview_path = None

    def confirm(self) -> None:
        if not self.preview_path or not Path(self.preview_path).is_file():
            raise ValueError("先にプレビューを作成して確認してください")
        self.confirmed = True

    def to_dict(self) -> dict:
        return asdict(self)

