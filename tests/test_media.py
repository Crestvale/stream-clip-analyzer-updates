import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from stream_clip_analyzer.media import (
    PreviewManager, confirmed_candidates, export_individual, safe_filename, video_filter,
)
from stream_clip_analyzer.models import ClipCandidate


class MediaTests(unittest.TestCase):
    def test_confirmed_filter(self):
        items = [ClipCandidate("a", 0, 1, confirmed=True), ClipCandidate("b", 1, 2)]
        self.assertEqual([x.name for x in confirmed_candidates(items)], ["a"])

    def test_export_only_confirmed(self):
        items = [ClipCandidate("yes", 0, 1, confirmed=True), ClipCandidate("no", 1, 2)]
        with tempfile.TemporaryDirectory() as folder, patch("stream_clip_analyzer.media.render_clip") as render:
            outputs = export_individual("source.mp4", items, folder)
            self.assertEqual(len(outputs), 1)
            self.assertEqual(outputs[0].name, "yes.mp4")
            self.assertEqual(render.call_count, 1)

    def test_export_rejects_unconfirmed(self):
        with self.assertRaises(ValueError):
            export_individual("source.mp4", [ClipCandidate("no", 0, 1)], "/tmp/out")

    def test_safe_filename(self):
        self.assertEqual(safe_filename('a/b:c*?"<>|'), "a_b_c______")
        self.assertEqual(safe_filename("..."), "clip")

    def test_vertical_filter(self):
        self.assertIsNone(video_filter(False))
        self.assertIn("1080:1920", video_filter(True))

    def test_preview_cleanup(self):
        manager = PreviewManager()
        folder = manager.directory
        self.assertTrue(folder.exists())
        manager.cleanup()
        self.assertFalse(folder.exists())


if __name__ == "__main__":
    unittest.main()
