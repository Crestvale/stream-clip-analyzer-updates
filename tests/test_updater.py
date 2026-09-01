import tempfile
import unittest
import zipfile
from pathlib import Path

from stream_clip_analyzer.updater import download_update, extract_update, sha256_file, version_tuple


class UpdaterTests(unittest.TestCase):
    def test_version(self):
        self.assertGreater(version_tuple("1.3.0"), version_tuple("v1.2.9"))

    def test_sha(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "x"
            path.write_bytes(b"abc")
            self.assertEqual(sha256_file(path), "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")

    def test_download_and_verify(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "update.zip"
            source.write_bytes(b"zip-data")
            result = download_update({"download_url": source.as_uri(), "sha256": sha256_file(source)})
            try:
                self.assertEqual(result.read_bytes(), b"zip-data")
            finally:
                result.unlink(missing_ok=True)

    def test_download_rejects_bad_hash(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "update.zip"
            source.write_bytes(b"zip-data")
            with self.assertRaises(ValueError):
                download_update({"download_url": source.as_uri(), "sha256": "0" * 64})

    def test_extract_app(self):
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / "update.zip"
            with zipfile.ZipFile(archive, "w") as handle:
                handle.writestr("Stream Clip Analyzer.app/Contents/Info.plist", "plist")
                executable = zipfile.ZipInfo("Stream Clip Analyzer.app/Contents/MacOS/Stream Clip Analyzer")
                executable.external_attr = 0o755 << 16
                handle.writestr(executable, "binary")
            app = extract_update(archive)
            self.assertEqual(app.name, "Stream Clip Analyzer.app")
            self.assertTrue((app / "Contents/MacOS/Stream Clip Analyzer").stat().st_mode & 0o100)

    def test_rejects_traversal(self):
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / "bad.zip"
            with zipfile.ZipFile(archive, "w") as handle:
                handle.writestr("../bad", "bad")
            with self.assertRaises(ValueError):
                extract_update(archive)


if __name__ == "__main__":
    unittest.main()
