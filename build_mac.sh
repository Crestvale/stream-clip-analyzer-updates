#!/bin/sh
set -eu

VERSION="1.3.3"
APP_NAME="Stream Clip Analyzer"
VAD_RELATIVE_PATH="Contents/Frameworks/faster_whisper/assets/silero_vad_v6.onnx"
FFMPEG_RELATIVE_PATH="Contents/Frameworks/bin/ffmpeg"
FFPROBE_RELATIVE_PATH="Contents/Frameworks/bin/ffprobe"
ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

cd "$ROOT_DIR"
export PYINSTALLER_CONFIG_DIR="$ROOT_DIR/work/pyinstaller"
mkdir -p "$PYINSTALLER_CONFIG_DIR"
if [ -x "$ROOT_DIR/.venv/bin/python" ]; then
  PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN=$(command -v python3)
else
  echo "Pythonが見つかりません。READMEの手順で環境を準備してください。" >&2
  exit 1
fi

"$PYTHON_BIN" -m PyInstaller --noconfirm --clean StreamClipAnalyzer.spec

BUILT_APP="dist/$APP_NAME.app"
if [ ! -f "$BUILT_APP/$VAD_RELATIVE_PATH" ]; then
  echo "ビルド失敗: faster-whisperのVADモデルが.appに同梱されていません。" >&2
  echo "不足ファイル: $BUILT_APP/$VAD_RELATIVE_PATH" >&2
  exit 1
fi
echo "Verified: $BUILT_APP/$VAD_RELATIVE_PATH"
for tool_path in "$FFMPEG_RELATIVE_PATH" "$FFPROBE_RELATIVE_PATH"; do
  if [ ! -x "$BUILT_APP/$tool_path" ]; then
    echo "ビルド失敗: 動画処理ツールが実行可能な状態で同梱されていません。" >&2
    echo "不足または実行不可: $BUILT_APP/$tool_path" >&2
    exit 1
  fi
done
"$BUILT_APP/$FFMPEG_RELATIVE_PATH" -version >/dev/null
"$BUILT_APP/$FFPROBE_RELATIVE_PATH" -version >/dev/null
echo "Verified bundled ffmpeg and ffprobe executables"

mkdir -p outputs
BUILD_STAGE=$(mktemp -d "${TMPDIR:-/tmp}/stream-clip-analyzer-build.XXXXXX")
cleanup_stage() {
  case "$BUILD_STAGE" in
    */stream-clip-analyzer-build.*) rm -rf -- "$BUILD_STAGE" ;;
  esac
}
trap cleanup_stage EXIT INT TERM

cp -R "$BUILT_APP" "$BUILD_STAGE/$APP_NAME.app"
xattr -cr "$BUILD_STAGE/$APP_NAME.app"
if command -v codesign >/dev/null 2>&1; then
  codesign --force --deep --sign - "$BUILD_STAGE/$APP_NAME.app"
  codesign --verify --deep --strict "$BUILD_STAGE/$APP_NAME.app"
fi

if [ ! -f "$BUILD_STAGE/$APP_NAME.app/$VAD_RELATIVE_PATH" ]; then
  echo "配布準備失敗: 署名前のコピーでVADモデルが失われました。" >&2
  exit 1
fi
for tool_path in "$FFMPEG_RELATIVE_PATH" "$FFPROBE_RELATIVE_PATH"; do
  if [ ! -x "$BUILD_STAGE/$APP_NAME.app/$tool_path" ]; then
    echo "配布準備失敗: $tool_path が実行できません。" >&2
    exit 1
  fi
done

ditto -c -k --sequesterRsrc --keepParent "$BUILD_STAGE/$APP_NAME.app" "outputs/Stream-Clip-Analyzer-v$VERSION-mac.zip"
echo "Created: outputs/Stream-Clip-Analyzer-v$VERSION-mac.zip"
