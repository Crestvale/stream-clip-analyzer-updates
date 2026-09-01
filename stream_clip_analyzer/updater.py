from __future__ import annotations

import hashlib
import json
import os
import shutil
import shlex
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_update_manifest(url: str, timeout: int = 10) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "StreamClipAnalyzer/1.3"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = json.load(response)
    if not isinstance(data, dict) or not data.get("version") or not data.get("download_url"):
        raise ValueError("更新情報の形式が正しくありません")
    return data


def download_update(manifest: dict, timeout: int = 60) -> Path:
    download_url = str(manifest.get("download_url", ""))
    if not download_url:
        raise ValueError("更新ファイルのURLがありません")
    descriptor, name = tempfile.mkstemp(prefix="stream-clip-analyzer-download-", suffix=".zip")
    os.close(descriptor)
    output = Path(name)
    try:
        request = urllib.request.Request(download_url, headers={"User-Agent": "StreamClipAnalyzer/1.3"})
        with urllib.request.urlopen(request, timeout=timeout) as response, output.open("wb") as handle:
            shutil.copyfileobj(response, handle)
        expected = str(manifest.get("sha256", "")).strip().lower()
        if expected and sha256_file(output).lower() != expected:
            raise ValueError("更新ZIPのSHA-256が一致しません")
        return output
    except Exception:
        output.unlink(missing_ok=True)
        raise


def version_tuple(version: str) -> tuple[int, ...]:
    try:
        return tuple(int(part) for part in version.strip().lstrip("v").split("."))
    except ValueError as exc:
        raise ValueError(f"不正なバージョン番号: {version}") from exc


def extract_update(zip_path: str | Path) -> Path:
    root = Path(tempfile.mkdtemp(prefix="stream-clip-analyzer-update-"))
    with zipfile.ZipFile(zip_path) as archive:
        for info in archive.infolist():
            target = (root / info.filename).resolve()
            if root.resolve() not in target.parents and target != root.resolve():
                shutil.rmtree(root, ignore_errors=True)
                raise ValueError("更新ZIPに不正なパスが含まれています")
        if sys.platform == "darwin" and shutil.which("ditto"):
            subprocess.run(["ditto", "-x", "-k", str(zip_path), str(root)], check=True)
        else:
            archive.extractall(root)
        for info in archive.infolist():
            mode = (info.external_attr >> 16) & 0o777
            target = root / info.filename
            if mode and target.exists():
                os.chmod(target, mode)
    apps = [path for path in root.rglob("*.app") if path.is_dir()]
    if len(apps) != 1 or apps[0].name != "Stream Clip Analyzer.app":
        shutil.rmtree(root, ignore_errors=True)
        raise ValueError("更新ZIPに Stream Clip Analyzer.app が1つ必要です")
    return apps[0]


def schedule_app_replacement(new_app: str | Path, current_app: str | Path) -> None:
    new_app, current_app = Path(new_app).resolve(), Path(current_app).resolve()
    if current_app.suffix != ".app" or current_app.name != "Stream Clip Analyzer.app":
        raise ValueError(".app版を起動している場合のみ自動更新できます")
    script_dir = Path(tempfile.mkdtemp(prefix="stream-clip-analyzer-installer-"))
    script = script_dir / "install.sh"
    backup = current_app.with_name(current_app.name + ".backup")
    script.write_text(
        "#!/bin/sh\nset -eu\n"
        "sleep 2\n"
        f"rm -rf {shlex.quote(str(backup))}\n"
        f"mv {shlex.quote(str(current_app))} {shlex.quote(str(backup))}\n"
        f"if cp -R {shlex.quote(str(new_app))} {shlex.quote(str(current_app))}; then\n"
        f"  open {shlex.quote(str(current_app))}\n"
        f"  rm -rf {shlex.quote(str(backup))}\n"
        "else\n"
        f"  rm -rf {shlex.quote(str(current_app))}\n"
        f"  mv {shlex.quote(str(backup))} {shlex.quote(str(current_app))}\n"
        "  exit 1\n"
        "fi\n",
        encoding="utf-8",
    )
    os.chmod(script, 0o700)
    log = Path.home() / "Library" / "Logs" / "StreamClipAnalyzer-update.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    handle = log.open("a", encoding="utf-8")
    subprocess.Popen(["/bin/sh", str(script)], stdout=handle, stderr=handle, start_new_session=True)
