"""Vanilla resources: local sample packs first, official repo on demand.

The tool needs vanilla textures, the texture indexes, the GUI sprites, the
colormaps and the bitmap font pages.  Three sources, in order:

1. every local pack folder configured for the job (``vanilla`` in config.json,
   plus any dropped resource pack),
2. the local cache ``<tool>/vanilla_cache``,
3. **the official sample pack** — ``Mojang/bedrock-samples`` on GitHub — which is
   downloaded per file on demand and then cached.

So a fresh install works with nothing but an internet connection, and once a file
has been fetched it keeps working offline.  ``sync()`` pre-fetches the pieces the
renderer always needs (indexes, GUI sprites, colormaps, font pages) so a later
run needs no network at all.
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import urllib.error
import urllib.request

RAW = "https://raw.githubusercontent.com/Mojang/bedrock-samples/main/resource_pack/"
UA = "mc-craft-render/1.0 (bedrock recipe image generator)"
TIMEOUT = 30               # the big index files are ~200 KB and can be slow
MAX_CONSECUTIVE_FAILURES = 4
COOLDOWN = 25              # after a burst of failures, skip this many attempts, then retry
socket.setdefaulttimeout(TIMEOUT)

# files the renderer needs no matter which recipe is drawn
CORE_FILES = [
    "textures/item_texture.json",
    "textures/terrain_texture.json",
    "blocks.json",
    "textures/ui/arrow_large.png",
    "textures/ui/arrow_left.png",
    "textures/ui/arrow_right.png",
    "textures/ui/brewing_arrow_empty.png",
    "textures/ui/brewing_fuel_bar_empty.png",
    "textures/ui/brewing_fuel_pipes.png",
    "textures/ui/brewing_fuel_empty.png",
    "textures/ui/bottle_empty.png",
    "textures/ui/flame_empty_image.png",
    "textures/ui/flame_full_image.png",
    "textures/colormap/grass.png",
    "textures/colormap/foliage.png",
]

# entries the official sample pack simply does not ship: the bulk download must not
# count them as failures, or "补全原版资源" could never switch to local-only mode.
# "textures/blocks/cake" is the block form of the cake - the item form
# (textures/items/cake) is what a recipe card needs, so the block form is skipped.
KNOWN_MISSING = {
    "textures/items/camera",                      # education edition only
    "textures/blocks/cake",                       # only the item form is used
    "textures/blocks/hanging_pale_moss_middle",
    "textures/blocks/hanging_pale_moss_tip",
}


def _texture_tokens(value) -> list:
    """Every texture path inside one ``texture_data`` entry (str / list / dict)."""
    out = []
    if isinstance(value, str):
        out.append(value)
    elif isinstance(value, list):
        for item in value:
            out += _texture_tokens(item)
    elif isinstance(value, dict):
        for key in ("textures", "texture", "path"):
            if key in value:
                out += _texture_tokens(value[key])
    return out


class VanillaSource:
    """Looks up a vanilla file across local folders, local zips, the cache and GitHub."""

    def __init__(self, local_dirs=None, cache_dir: str | None = None,
                 allow_download: bool = True, log=print, zip_files=None):
        self.local_dirs = [d for d in (local_dirs or []) if d and os.path.isdir(d)]
        # a resource pack may be handed over as a .zip / .mcpack / .mcaddon: its members
        # are read straight out of the archive, so no unpacking step is needed
        self.zip_files = [z for z in (zip_files or []) if z and os.path.isfile(z)]
        self.cache_dir = cache_dir
        self.allow_download = allow_download
        self.log = log
        self._index: dict = {}
        self.downloaded = 0
        self.from_zip = 0
        self.failed: set = set()
        self.streak = 0
        self.cooldown = 0
        self.offline = False

    # ------------------------------------------------------------- locals
    def _local(self, rel: str) -> str | None:
        rel_os = rel.replace("/", os.sep)
        for root in self.local_dirs:
            path = os.path.join(root, rel_os)
            if os.path.isfile(path):
                return path
        return None

    def _from_archive(self, rel: str) -> str | None:
        """Extract one member out of a local pack zip into the cache."""
        if not self.zip_files or not self.cache_dir:
            return None
        import zipfile
        dest = os.path.join(self.cache_dir, rel.replace("/", os.sep))
        for archive in self.zip_files:
            try:
                with zipfile.ZipFile(archive) as zf:
                    names = zf.namelist()
                    # a pack zip may keep everything under one top folder
                    member = rel if rel in names else None
                    if member is None:
                        for name in names:
                            if name.endswith("/" + rel) or name == rel:
                                member = name
                                break
                    if member is None:
                        continue
                    data = zf.read(member)
            except Exception:
                continue
            if not data:
                continue
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "wb") as fh:
                fh.write(data)
            self.from_zip += 1
            return dest
        return None

    def has_pack(self) -> bool:
        """True when a local pack (folder or zip) can serve the texture indexes."""
        for cand in ("textures/item_texture.json", "textures/terrain_texture.json"):
            if self._local(cand):
                return True
            if self._from_archive(cand):
                return True
        return False

    def find(self, rel: str | None, extensions=(".png", ".tga", ".json")) -> str | None:
        """Absolute path of a vanilla file, from a local pack, zip, cache or download."""
        if not rel:
            return None
        rel = rel.replace("\\", "/").lstrip("/")
        if rel.endswith((".png", ".tga", ".json")):
            candidates = [rel]
        else:
            candidates = [rel + ext for ext in extensions]

        for cand in candidates:
            hit = self._local(cand)
            if hit:
                return hit
            if self.cache_dir:
                cached = os.path.join(self.cache_dir, cand.replace("/", os.sep))
                if os.path.isfile(cached):
                    return cached
        for cand in candidates:
            hit = self._from_archive(cand)
            if hit:
                return hit
        if not self.allow_download or self.offline:
            return None
        if self.cooldown > 0:                 # backing off after a burst of failures
            self.cooldown -= 1
            return None
        for cand in candidates:
            if cand in self.failed:
                continue
            if self._download(cand):
                return os.path.join(self.cache_dir, cand.replace("/", os.sep))
            self.failed.add(cand)
        return None

    def _download(self, rel: str) -> bool:
        if not self.cache_dir or rel in self.failed or self.offline:
            return False
        rel = rel.replace("\\", "/").lstrip("/")
        if not rel or ":" in rel.split("/")[0] or ".." in rel:
            return False
        dest = os.path.join(self.cache_dir, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        # the index files are ~60-200 KB, images are a few KB
        timeout = 90 if rel.endswith(".json") else TIMEOUT
        try:
            req = urllib.request.Request(RAW + rel, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read()
            if len(data) < 16:
                return False
            with open(dest, "wb") as fh:
                fh.write(data)
            self.downloaded += 1
            self.streak = 0
            return True
        except urllib.error.HTTPError:
            self.streak = 0           # 404: the network is fine, the file just is not there
            return False
        except (urllib.error.URLError, OSError):
            self.streak += 1
            if self.streak >= MAX_CONSECUTIVE_FAILURES:
                self.streak = 0
                self.cooldown = COOLDOWN
                self.log("联网下载连续失败，先放慢下载（稍后自动重试）；已用本地包 + 缓存的结果")
            return False

    def read_json(self, rel: str):
        path = self.find(rel, extensions=(".json",))
        if not path:
            return None
        try:
            from . import jsonc                  # tolerant: vanilla files carry comments
            return jsonc.load(path)
        except Exception:
            try:
                with open(path, encoding="utf-8-sig") as fh:
                    return json.load(fh)
            except Exception:
                return None

    # --------------------------------------------------------------- sync
    def sync_all(self, log=print, workers: int = 8) -> dict:
        """Download **every** vanilla item and block texture into the cache.

        Meant for the "补全原版资源" button: afterwards the renderer never has to
        touch the network again.  Files are only added here - nothing is deleted
        (that is what ``clear_cache`` is for).
        """
        import concurrent.futures

        core = self.sync()
        wanted, seen = [], set()
        for rel in ("textures/item_texture.json", "textures/terrain_texture.json"):
            data = self.read_json(rel) or {}
            for entry in (data.get("texture_data") or {}).values():
                for token in _texture_tokens(entry):
                    token = token.replace("\\", "/").lstrip("/")
                    for ext in (".png", ".tga"):
                        if token.lower().endswith(ext):
                            token = token[: -len(ext)]
                            break
                    if not token or token in seen:
                        continue
                    seen.add(token)
                    wanted.append(token)

        todo = []
        skipped = []
        for token in wanted:
            if self._local(token + ".png") or self._local(token + ".tga"):
                continue
            if self.cache_dir and (os.path.isfile(os.path.join(self.cache_dir, token + ".png"))
                                   or os.path.isfile(os.path.join(self.cache_dir,
                                                                  token + ".tga"))):
                continue
            # a local pack zip can supply it: pull that one member into the cache
            if self._from_archive(token + ".png") or self._from_archive(token + ".tga"):
                continue
            if token in KNOWN_MISSING:
                skipped.append(token)
                continue
            todo.append(token)

        report = {"core": core, "listed": len(wanted), "fetched": 0, "failed": 0,
                  "skipped": skipped}
        if self.from_zip:
            log(f"原版包压缩文件已提供 {self.from_zip} 个文件")
        if not todo or not self.cache_dir or not self.allow_download:
            log(f"原版纹理：清单 {len(wanted)} 个，本地包/缓存已齐，无需下载")
            return report
        log(f"原版纹理：清单 {len(wanted)} 个，需要下载 {len(todo)} 个")
        self.offline = False
        self.streak = 0

        def fetch(token):
            for ext in (".png", ".tga"):
                if self._download(token + ext):
                    return True
            return False

        done = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            for ok, token in pool.map(lambda t: (fetch(t), t), todo):
                done += 1
                if ok:
                    report["fetched"] += 1
                else:
                    report["failed"] += 1
                    report.setdefault("failed_list", []).append(token)
                if done % 200 == 0:
                    log(f"  {done}/{len(todo)}（成功 {report['fetched']}，失败 {report['failed']}）")

        # one sequential retry: mirrors fail in bursts on a flaky route
        retry = list(report.get("failed_list", []))
        if retry:
            log(f"重试 {len(retry)} 个失败项")
            still = []
            for token in retry:
                ok = False
                for ext in (".png", ".tga"):
                    self.failed.discard(token + ext)
                    if self._download(token + ext):
                        ok = True
                        break
                if ok:
                    report["failed"] -= 1
                    report["fetched"] += 1
                else:
                    still.append(token)
            report["failed_list"] = still
        log(f"原版纹理下载完成：成功 {report['fetched']}，失败 {report['failed']}，"
            f"缓存 {self.cache_size_mb()} MB → {self.cache_dir}")
        return report

    def sync(self, extra=()) -> dict:
        """Pre-download the core files (and any extras) into the cache."""
        report = {"ok": [], "failed": []}
        for rel in list(CORE_FILES) + list(extra):
            if self._local(rel):
                report["ok"].append(rel)
                continue
            if self.cache_dir and os.path.isfile(os.path.join(self.cache_dir,
                                                              rel.replace("/", os.sep))):
                report["ok"].append(rel + " (cached)")
                continue
            if self._download(rel):
                report["ok"].append(rel)
            else:
                report["failed"].append(rel)
        return report

    def status(self) -> str:
        bits = [f"本地包 {len(self.local_dirs)} 个"]
        if self.cache_dir and os.path.isdir(self.cache_dir):
            cached = sum(len(files) for _r, _d, files in os.walk(self.cache_dir))
            bits.append(f"缓存 {cached} 个文件")
        bits.append("联网下载开" if self.allow_download else "联网下载关")
        return "，".join(bits)

    def cache_size_mb(self) -> float:
        if not self.cache_dir or not os.path.isdir(self.cache_dir):
            return 0.0
        total = 0
        for root, _dirs, files in os.walk(self.cache_dir):
            for name in files:
                try:
                    total += os.path.getsize(os.path.join(root, name))
                except OSError:
                    pass
        return round(total / 1048576, 1)

    def clear_cache(self) -> None:
        if self.cache_dir and os.path.isdir(self.cache_dir):
            shutil.rmtree(self.cache_dir, ignore_errors=True)
