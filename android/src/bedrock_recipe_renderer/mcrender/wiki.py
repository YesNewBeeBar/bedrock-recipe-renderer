"""Download inventory icons from the Minecraft wiki, with a local cache.

Some blocks cannot be re-created faithfully from an add-on: the game renders them
with special renderers (chests, shulker boxes, beds, banners, signs, bells, heads,
decorated pots, end portals, ...) and plants use grayscale textures that the game
tints per biome.  For those, the wiki's isometric inventory render is the most
accurate icon available.

Icons are downloaded on demand and cached in ``<tool>/wiki_cache/<id>.png`` so the
tool keeps working offline afterwards.
"""
from __future__ import annotations

import json
import os
import socket
import urllib.parse
import urllib.request

from PIL import Image

WIKIS = ("https://minecraft.wiki", "https://zh.minecraft.wiki")
UA = "mc-craft-render/1.0 (addon recipe image generator)"
TIMEOUT = 8
MAX_CONSECUTIVE_FAILURES = 2
socket.setdefaulttimeout(TIMEOUT)

# failures are remembered on disk so a later run does not pay for them again
_FAILS: set = set()
_STREAK = {"n": 0}
_OFFLINE = {"yes": False}
_NET = {"ok": False}          # did any request actually reach the wiki?


def _note_failure(ident: str, root: str, permanent: bool = False) -> None:
    _FAILS.add(ident)
    _STREAK["n"] += 1
    if _STREAK["n"] >= MAX_CONSECUTIVE_FAILURES:
        _OFFLINE["yes"] = True
    if not permanent:
        return                # a network outage must not poison later runs
    try:
        with open(miss_path(ident, root), "w", encoding="utf-8") as fh:
            fh.write("no wiki icon\n")
    except OSError:
        pass


def cache_dir(root: str) -> str:
    path = os.path.join(root, "wiki_cache")
    os.makedirs(path, exist_ok=True)
    return path


def _safe(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in name)


def _note_failure_legacy():
    return None


def _api(wiki: str, params: dict) -> dict:
    params = dict(params, format="json")
    url = f"{wiki}/api.php?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    _NET["ok"] = True
    return data


def _page_image(wiki: str, title: str) -> str | None:
    try:
        data = _api(wiki, {"action": "query", "titles": title, "redirects": 1,
                           "prop": "pageimages", "piprop": "original|thumbnail",
                           "pithumbsize": 300})
    except Exception:
        return None
    pages = (data.get("query") or {}).get("pages") or {}
    for page in pages.values():
        original = (page.get("original") or {}).get("source")
        thumb = (page.get("thumbnail") or {}).get("source")
        if original or thumb:
            return original or thumb
    return None


def _file_url(wiki: str, name: str) -> str | None:
    """Direct URL of a File: page (``name`` without the File: prefix)."""
    try:
        data = _api(wiki, {"action": "query", "titles": "File:" + name, "redirects": 1,
                           "prop": "imageinfo", "iiprop": "url"})
    except Exception:
        return None
    pages = (data.get("query") or {}).get("pages") or {}
    for page in pages.values():
        for info in (page.get("imageinfo") or []):
            if info.get("url"):
                return info["url"]
    return None


def _search_image(wiki: str, query: str) -> str | None:
    try:
        data = _api(wiki, {"action": "query", "generator": "search", "gsrsearch": query,
                           "gsrlimit": 1, "prop": "pageimages", "piprop": "original|thumbnail",
                           "pithumbsize": 300})
    except Exception:
        return None
    pages = (data.get("query") or {}).get("pages") or {}
    best = None
    for page in pages.values():
        if page.get("index") == 1 or best is None:
            best = page
    if not best:
        return None
    return ((best.get("original") or {}).get("source")
            or (best.get("thumbnail") or {}).get("source"))


def _download(url: str, dest: str) -> bool:
    if _OFFLINE["yes"]:
        return False
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = resp.read()
        if len(data) < 64:
            return False
        with open(dest, "wb") as fh:
            fh.write(data)
        _NET["ok"] = True
        _STREAK["n"] = 0
        return True
    except urllib.error.HTTPError:
        _NET["ok"] = True
        _STREAK["n"] = 0
        return False
    except Exception:
        _STREAK["n"] += 1
        if _STREAK["n"] >= MAX_CONSECUTIVE_FAILURES:
            _OFFLINE["yes"] = True
        return False


def _usable(path: str) -> Image.Image | None:
    """Reject wiki images that are collages or page screenshots rather than one icon."""
    try:
        im = Image.open(path)
        im.load()
    except Exception:
        return None
    w, h = im.size
    # an inventory icon is a small, roughly square sprite: article illustrations such as
    # "three hoes side by side" or a 2560x1459 page collage are neither
    if (max(w, h) > 96 or min(w, h) <= 0 or not (0.55 <= w / h <= 1.8)):
        try:
            os.remove(path)
        except OSError:
            pass
        return None
    return im.convert("RGBA")


def icon_path(ident: str, root: str) -> str:
    return os.path.join(cache_dir(root), _safe(ident.replace(":", "__")) + ".png")


def miss_path(ident: str, root: str) -> str:
    return os.path.join(cache_dir(root), _safe(ident.replace(":", "__")) + ".none")


def _note_failure(ident: str, root: str) -> None:
    _FAILS.add(ident)
    _STREAK["n"] += 1
    if _STREAK["n"] >= MAX_CONSECUTIVE_FAILURES:
        _OFFLINE["yes"] = True
    try:
        with open(miss_path(ident, root), "w", encoding="utf-8") as fh:
            fh.write("no wiki icon\n")
    except OSError:
        pass


def fetch_file(name: str, root: str, language: str = "en",
               cache_name: str | None = None) -> Image.Image | None:
    """Download a specific ``File:`` image (the wiki's per-item sprite sheets)."""
    dest = os.path.join(cache_dir(root), _safe(cache_name or name) + ".png")
    if os.path.exists(dest):
        im = _usable(dest)
        if im is not None:
            return im
    if _OFFLINE["yes"]:
        return None
    wikis = tuple(reversed(WIKIS)) if language.startswith("zh") else WIKIS
    for wiki in wikis:
        url = _file_url(wiki, name)
        if url and _download(url, dest):
            im = _usable(dest)
            if im is not None:
                return im
    return None


def fetch_icon(ident: str, root: str, language: str = "en",
               offline: bool = False) -> Image.Image | None:
    """Return the wiki inventory icon for ``ident``, downloading it once.

    With ``offline=True`` only the local cache is consulted and no request is made -
    that is what the "只用本地纹理" mode uses once everything has been fetched.
    """
    dest = icon_path(ident, root)
    if os.path.exists(dest):
        im = _usable(dest)
        if im is not None:
            return im
    if offline or ident in _FAILS or _OFFLINE["yes"] or os.path.exists(miss_path(ident, root)):
        return None

    name = ident.split(":")[-1]
    titles = [" ".join(part.capitalize() for part in name.split("_"))]
    if name.endswith("s"):
        titles.append(titles[0][:-1])
    if language.startswith("zh"):
        wikis = tuple(reversed(WIKIS))
    else:
        wikis = WIKIS

    for wiki in wikis:
        if _OFFLINE["yes"]:
            break
        # the inventory sprite first: "Invicon X.png" is the 16x16/32x32 item icon,
        # while the article's own image is often an illustration of several items
        for title in titles:
            for candidate in (f"Invicon {title}.png", f"{title} JE1 BE1.png",
                              f"{title}.png"):
                url = _file_url(wiki, candidate)
                if url and _download(url, dest):
                    im = _usable(dest)
                    if im is not None:
                        return im
        for title in titles:
            url = _page_image(wiki, title)
            if url and _download(url, dest):
                im = _usable(dest)
                if im is not None:
                    return im
        url = _search_image(wiki, titles[0])
        if url and _download(url, dest):
            im = _usable(dest)
            if im is not None:
                return im
    _note_failure(ident, root, permanent=_NET["ok"])
    return None
