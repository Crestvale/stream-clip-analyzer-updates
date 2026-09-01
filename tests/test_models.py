import tempfile
import unittest
from pathlib import Path

from stream_clip_analyzer.models import ClipCandidate


class ClipCandidateTests(unittest.TestCase):
    def test_adjustment_invalidates_confirmation(self):
        with tempfile.TemporaryDirectory() as folder:
            preview = Path(folder) / "preview.mp4"
            preview.write_bytes(b"video")
            item = ClipCandidate("clip", 10, 20, confirmed=True, preview_path=str(preview))
            item.adjust("start", -0.5)
            self.assertEqual(item.start, 9.5)
            self.assertFalse(item.confirmed)
            self.assertIsNone(item.preview_path)

    def test_bounds(self):
        item = ClipCandidate("clip", 1, 2)
        item.adjust("start", -5)
        self.assertEqual(item.start, 0)
        item.adjust("end", 10, media_duration=5)
        self.assertEqual(item.end, 5)

    def test_invalid_range(self):
        with self.assertRaises(ValueError):
            ClipCandidate("clip", 2, 2)

    def test_confirm_requires_preview(self):
        item = ClipCandidate("clip", 1, 2)
        with self.assertRaises(ValueError):
            item.confirm()

    def test_confirm_with_preview(self):
        with tempfile.TemporaryDirectory() as folder:
            preview = Path(folder) / "preview.mp4"
            preview.touch()
            item = ClipCandidate("clip", 1, 2, preview_path=str(preview))
            item.confirm()
            self.assertTrue(item.confirmed)


if __name__ == "__main__":
    unittest.main()

