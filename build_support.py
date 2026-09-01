"""Helpers shared by the PyInstaller spec and build tests."""

from importlib.util import find_spec
from pathlib import Path


VAD_ASSET = Path("assets") / "silero_vad_v6.onnx"
VAD_BUNDLE_PATH = Path("Contents/Frameworks/faster_whisper") / VAD_ASSET


def faster_whisper_asset_datas(package_dir=None):
    """Return a PyInstaller data entry for all faster-whisper assets."""
    if package_dir is None:
        package_spec = find_spec("faster_whisper")
        if package_spec is None or package_spec.origin is None:
            raise RuntimeError("faster-whisper is not installed in the build environment")
        package_dir = Path(package_spec.origin).resolve().parent
    else:
        package_dir = Path(package_dir).resolve()

    assets_dir = package_dir / "assets"
    required_asset = package_dir / VAD_ASSET
    if not required_asset.is_file():
        raise RuntimeError(f"Required faster-whisper asset is missing: {required_asset}")
    return [(str(assets_dir), "faster_whisper/assets")]
