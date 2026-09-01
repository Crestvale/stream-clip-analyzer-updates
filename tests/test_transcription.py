import json
import tempfile
import unittest
from pathlib import Path

from stream_clip_analyzer.models import TranscriptSegment
from stream_clip_analyzer.transcription import save_transcript


class TranscriptTests(unittest.TestCase):
    def test_writes_three_formats(self):
        segments = [TranscriptSegment(1.25, 2.5, "こんにちは")]
        with tempfile.TemporaryDirectory() as folder:
            outputs = save_transcript(segments, folder, "sample")
            self.assertEqual({p.suffix for p in outputs}, {".txt", ".csv", ".json"})
            data = json.loads((Path(folder) / "sample_transcript.json").read_text(encoding="utf-8"))
            self.assertEqual(data[0]["text"], "こんにちは")


if __name__ == "__main__":
    unittest.main()

