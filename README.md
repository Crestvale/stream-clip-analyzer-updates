# Stream Clip Analyzer v1.3.2

配信動画・音声をWhisperで文字起こしし、人が選んだ範囲をFFmpegで切り抜くmacOS向けデスクトップアプリです。v1.3では、正式な書き出し前に候補ごとの動画をアプリ内で確認し、確定済みの候補だけを書き出せます。

v1.3.2では、faster-whisperが音声区間検出に使う `assets/silero_vad_v6.onnx` をmacOSアプリへ確実に同梱するようビルドを修正しました。従来機能とv1.3.1のUIスレッド修正は維持されています。

## v1.3の主な追加機能

- 候補ごとの一時MP4プレビュー
- アプリ内で再生、一時停止、シーク
- 開始・終了位置を `±0.5秒` / `±1秒` で微調整
- 調整後の再プレビュー
- 「この範囲で確定」と、候補ごとの確定/未確認表示
- 確定済み候補だけを個別出力または1本に結合
- アプリ終了時と入力動画変更時にプレビュー用一時ファイルを自動削除

時刻、縦9:16設定を変更すると、その候補は未確認へ戻ります。再プレビューしてから確定してください。これにより、確認した内容と異なる動画を誤って出力するのを防ぎます。

## 維持している機能

- `.mp4`、`.mov`、`.m4v`、`.mkv`、`.webm`、`.avi` と主要音声形式の読み込み
- Finderからのドラッグ＆ドロップ
- faster-whisperによる日本語文字起こし
- `base` / `small` / `medium` / `large-v3`
- 反復・幻覚抑制（既定ON）
- 文字起こしのTXT / CSV / JSON保存
- 文字起こしの複数行から切り抜き範囲を作成
- 候補名の変更、削除、並び替え
- 候補ごとの縦9:16出力（映像全体を維持して余白追加）
- 個別MP4出力 / 1本への結合
- 更新URLの起動時確認、SHA-256検証、更新ZIPによるアプリ内アップデート

## 基本操作

1. 動画を選択するか、ウィンドウへドロップします。
2. Whisperモデルを選び、「文字起こし開始」を押します。通常は `small` 推奨です。
3. 文字起こし一覧から連続した行を選び、「選択範囲を切り抜き候補に追加」を押します。
4. 候補を選び、「プレビュー作成 / 再プレビュー」を押します。
5. 再生、一時停止、シークで内容を確認します。
6. 必要なら開始・終了を `±0.5秒` / `±1秒` で調整し、再プレビューします。
7. 問題なければ「この範囲で確定」を押します。
8. 個別または結合を選び、「確定済みを書き出す」を押します。

未確認の候補は書き出されません。結合時も、一覧に並んだ確定済み候補だけが上から順に結合されます。

## 出力先

入力が `/Videos/stream.mp4` の場合、次の場所へ保存されます。

```text
/Videos/stream/
├── transcript/
│   ├── stream_transcript.txt
│   ├── stream_transcript.csv
│   └── stream_transcript.json
└── clips/
    ├── clip_001.mp4
    └── combined_clip.mp4
```

プレビューはOSの一時領域に作られ、正式な出力先には残りません。

## ソースから起動

macOS、Python 3.11〜3.13を推奨します。FFmpegはビルド時にアプリへ同梱されます。ソース起動時は別途FFmpegが必要です。

```bash
brew install python@3.13 ffmpeg
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python run.py
```

初回の文字起こし時はWhisperモデルをダウンロードするため、動画の長さに関係なく時間がかかる場合があります。モデルはMac内にキャッシュされます。

## テスト

外部ライブラリ不要のコアテストは次のコマンドで実行できます。

```bash
python -m unittest discover -v
```

実機では、短い動画で以下も確認してください。

- プレビューの映像と音声
- 再生、一時停止、シーク
- 時刻調整後に未確認へ戻ること
- 個別出力と結合出力
- 横動画と縦9:16
- アプリ終了後に一時プレビューが消えること

## macOS `.app` のビルド

依存関係をインストールした仮想環境で実行します。

```bash
chmod +x build_mac.sh
./build_mac.sh
```

成功すると次が生成されます。

```text
dist/Stream Clip Analyzer.app
outputs/Stream-Clip-Analyzer-v1.3.2-mac.zip
```

`build_mac.sh` は利用中の `ffmpeg` と `ffprobe` に加え、`faster_whisper/assets` ディレクトリ全体をアプリへ同梱します。ビルド後に `.app/Contents/Frameworks/faster_whisper/assets/silero_vad_v6.onnx` の存在を自動確認し、欠落していればZIPを生成せず終了します。その後、身内配布向けのad-hoc署名を行います。Apple Developer ID署名・公証は行いません。別Macで初回起動が止められた場合は、「システム設定 → プライバシーとセキュリティ → このまま開く」から許可してください。

## GitHubからリリース

`.github/workflows/release.yml` を含む状態でGitHubへ反映すると、GitHub Actionsから配布版を作成できます。

1. GitHubの「Actions」を開きます。
2. 「Build and release macOS app」を選びます。
3. 「Run workflow」を実行します。

テスト、macOSアプリのビルド、VADモデルの存在確認、ad-hoc署名、GitHub Releaseの作成、配布ZIPの添付まで自動実行されます。`v1.3.2` のようなバージョンタグをpushした場合も同じ処理が動きます。タグとアプリ内バージョンが一致しない場合は、誤った版を公開しないよう処理を停止します。

## アップデート

`.app` 版で「ヘルプ → 更新ZIPからアップデート…」を選び、新しい `Stream Clip Analyzer.app` を1つ含むZIPを指定します。現在版をバックアップして置換し、失敗した場合は旧版へ戻します。ソースからの起動中は自動置換できません。

更新用の `update.json` を置く場合は「ヘルプ → 更新URLを設定…」でURLを登録できます。以降は起動時に自動確認し、「アップデートを確認」から手動確認もできます。

```json
{
  "version": "1.3.2",
  "download_url": "https://example.com/Stream-Clip-Analyzer-v1.3.2-mac.zip",
  "sha256": "ZIPのSHA-256",
  "notes": ["変更内容"]
}
```

## 注意点

- Whisperの文字起こしは100%正確ではありません。切り抜き位置を探す補助として使ってください。
- プレビューは最終出力と同じ映像変換設定で作りますが、Macやコーデック構成による再生差は実機確認が必要です。
- 一般公開する場合はDeveloper ID署名とAppleの公証を追加してください。
