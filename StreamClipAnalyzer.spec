# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import shutil

from build_support import faster_whisper_asset_datas

root = Path(SPECPATH)
binaries = []
datas = faster_whisper_asset_datas()
for name in ("ffmpeg", "ffprobe"):
    path = shutil.which(name)
    if path:
        binaries.append((path, "bin"))

a = Analysis(
    [str(root / "run.py")],
    pathex=[str(root)],
    binaries=binaries,
    # faster-whisper loads this ONNX file at runtime via its package path.
    # PyInstaller does not discover it from Python imports, so include the
    # complete assets directory explicitly.
    datas=datas,
    hiddenimports=[
        "faster_whisper", "ctranslate2", "tokenizers", "huggingface_hub",
        "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True,
    name="Stream Clip Analyzer", debug=False, bootloader_ignore_signals=False,
    strip=False, upx=False, console=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="Stream Clip Analyzer")
app = BUNDLE(
    coll,
    name="Stream Clip Analyzer.app",
    icon=None,
    bundle_identifier="com.crestvale.stream-clip-analyzer",
    version="1.3.3",
    info_plist={
        "CFBundleShortVersionString": "1.3.3",
        "CFBundleVersion": "1.3.3",
        "NSHighResolutionCapable": True,
        "NSRequiresAquaSystemAppearance": False,
    },
)
