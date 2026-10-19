"""在线更新：从 GitHub Release 取最新版并与当前版本比较。

设计要点：
- 只依赖标准库（urllib），方便单独测试，不把网络问题带进渲染核心。
- **按平台挑文件**：桌面端只认 `.exe`（安装器），手机端只认 `.apk`。
  同一个 release 里两种文件并存，绝不能下错（e.g. 手机下到 exe）。
- 版本比较用数字元组，并容忍 `v1.1.1` / `1.1.1` 两种标签写法。
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import urllib.request

REPO = "YesNewBeeBar/bedrock-recipe-renderer"
API_LATEST = f"https://api.github.com/repos/{REPO}/releases/latest"
API_RELEASES = f"https://api.github.com/repos/{REPO}/releases"
USER_AGENT = "brr-updater"

#: 各平台认的安装包后缀（桌面 exe / 手机 apk）
ASSET_SUFFIX = {"windows": ".exe", "android": ".apk"}
#: 明确排除的后缀：防止桌面端下到 apk、手机端下到 exe
ASSET_REJECT = {"windows": (".apk", ".zip"), "android": (".exe", ".zip", ".msi")}


class UpdateError(RuntimeError):
    pass


def parse_version(text: str) -> tuple:
    """'v1.1.1' / '1.1.0' / 'v1.0.0-beta' -> 可比较的数字元组。"""
    nums = re.findall(r"\d+", str(text or ""))
    return tuple(int(n) for n in nums[:4]) or (0,)


def is_newer(latest: str, current: str) -> bool:
    return parse_version(latest) > parse_version(current)


def _get_json(url: str, timeout: float = 20.0) -> dict:
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": USER_AGENT,
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def latest_release(timeout: float = 20.0) -> dict:
    """最新 release：{'tag': 'v1.1.0', 'name': …, 'assets': [{name,url,size}], 'page': …}"""
    try:
        data = _get_json(API_LATEST, timeout)
    except Exception as exc:
        raise UpdateError(f"无法访问 GitHub：{exc}") from exc
    assets = []
    for a in data.get("assets") or []:
        assets.append({
            "name": a.get("name") or "",
            "url": a.get("browser_download_url") or "",
            "size": int(a.get("size") or 0),
        })
    return {
        "tag": data.get("tag_name") or "",
        "name": data.get("name") or "",
        "assets": assets,
        "page": data.get("html_url") or "",
    }


def pick_asset(assets: list, platform: str = "windows") -> dict | None:
    """按平台挑安装包：桌面只认 .exe，手机只认 .apk。"""
    suffix = ASSET_SUFFIX.get(platform, ".exe")
    reject = ASSET_REJECT.get(platform, ())
    for a in assets or []:
        name = (a.get("name") or "").lower()
        if name.endswith(suffix) and not any(name.endswith(r) for r in reject):
            return a
    return None


def version_from_name(name: str) -> str:
    """从安装包文件名里取版本号。

    桌面与手机共用一个 release（tag 是桌面版本），但 APK 文件名自带手机版本：
    ``bedrock-recipe-renderer-v1.0.0-Android.apk`` → ``1.0.0``。
    取不到就返回空串，调用方回退到 tag。
    """
    m = re.search(r"-v?(\d+(?:\.\d+)+)-", str(name or ""), re.IGNORECASE)
    return m.group(1) if m else ""


def download(url: str, dest_dir: str | None = None, name: str = "",
             progress=None, timeout: float = 60.0) -> str:
    """下载到临时目录，返回文件路径。progress(done, total) 可为 None。"""
    dest_dir = dest_dir or tempfile.mkdtemp(prefix="brr_update_")
    os.makedirs(dest_dir, exist_ok=True)
    target = os.path.join(dest_dir, name or os.path.basename(url) or "update.bin")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp, open(target, "wb") as fh:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = resp.read(256 * 1024)
            if not chunk:
                break
            fh.write(chunk)
            done += len(chunk)
            if progress:
                try:
                    progress(done, total)
                except Exception:
                    pass
    return target


def check(current: str, platform: str = "windows", timeout: float = 20.0) -> dict:
    """一次完整的检查：返回 {latest, newer, asset, page} 或抛 UpdateError。

    版本基准：桌面用 release 的 tag；手机用 APK 文件名里的版本号
    （一个 release 同时发布 exe 与 apk，tag 只代表桌面版本）。
    """
    rel = latest_release(timeout=timeout)
    asset = pick_asset(rel["assets"], platform)
    base = rel["tag"]
    if platform == "android" and asset:
        base = version_from_name(asset["name"]) or base
    return {
        "latest": rel["tag"],
        "asset_version": base,
        "newer": is_newer(base, current),
        "asset": asset,
        "page": rel["page"],
        "current": current,
        "platform": platform,
    }
