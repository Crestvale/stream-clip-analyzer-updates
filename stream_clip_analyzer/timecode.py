from __future__ import annotations


def format_timecode(seconds: float, milliseconds: bool = True) -> str:
    value = max(0, int(round(float(seconds) * 1000)))
    hours, rem = divmod(value, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    base = f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{base}.{ms:03d}" if milliseconds else base


def parse_timecode(text: str) -> float:
    raw = text.strip().replace(",", ".")
    if not raw:
        raise ValueError("時刻を入力してください")
    parts = raw.split(":")
    try:
        if len(parts) == 1:
            result = float(parts[0])
        elif len(parts) == 2:
            result = int(parts[0]) * 60 + float(parts[1])
        elif len(parts) == 3:
            result = int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        else:
            raise ValueError
    except ValueError as exc:
        raise ValueError(f"時刻の形式が正しくありません: {text}") from exc
    if result < 0:
        raise ValueError("時刻は0以上にしてください")
    return result

