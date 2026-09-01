import tempfile
import unittest
from pathlib import Path

from build_support import VAD_BUNDLE_PATH, faster_whisper_asset_datas


class BuildSupportTests(unittest.TestCase):
    def test_includes_complete_faster_whisper_assets_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            package_dir = Path(folder) / "faster_whisper"
            assets_dir = package_dir / "assets"
            assets_dir.mkdir(parents=True)
            (assets_dir / "silero_vad_v6.onnx").write_bytes(b"onnx")
            (assets_dir / "future_asset.bin").write_bytes(b"future")

            self.assertEqual(
                faster_whisper_asset_datas(package_dir),
                [(str(assets_dir.resolve()), "faster_whisper/assets")],
            )

    def test_rejects_missing_vad_asset(self):
        with tempfile.TemporaryDirectory() as folder:
            package_dir = Path(folder) / "faster_whisper"
            (package_dir / "assets").mkdir(parents=True)
            with self.assertRaisesRegex(RuntimeError, "silero_vad_v6.onnx"):
                faster_whisper_asset_datas(package_dir)

    def test_expected_bundle_location(self):
        self.assertEqual(
            VAD_BUNDLE_PATH.as_posix(),
            "Contents/Frameworks/faster_whisper/assets/silero_vad_v6.onnx",
        )


if __name__ == "__main__":
    unittest.main()
