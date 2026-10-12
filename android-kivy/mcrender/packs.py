"""识别附加包：哪块是行为包(BP)、哪块是资源包(RP)，以及给 BP 配对上 RP。

这段逻辑原先只写在桌面端 GUI 里，移动端另写了一套"看 textures/ 目录"的启发式，
两边行为不一致（多面方块、自定义模型在手机上读不到）。现在下沉到核心，
**两端共用同一份**，避免再次分叉。
"""
from __future__ import annotations

import json
import os

def pack_kinds(root: str) -> set:
    """Which pack types a folder is, from its manifest.json modules."""
    manifest = os.path.join(root, "manifest.json")
    if not os.path.isfile(manifest):
        return set()
    try:
        with open(manifest, encoding="utf-8-sig") as fh:
            data = json.load(fh)
    except Exception:
        return set()
    kinds = set()
    for module in data.get("modules", []) or []:
        kind = str(module.get("type", "")).lower()
        if kind == "data":
            kinds.add("bp")
        elif kind in ("resources", "client_data"):
            kinds.add("rp")
    return kinds


def manifest_info(root: str) -> dict:
    path = os.path.join(root, "manifest.json")
    try:
        with open(path, encoding="utf-8-sig") as fh:
            data = json.load(fh)
    except Exception:
        return {}
    return data or {}


def find_matching_rp(bp_path: str) -> str | None:
    """找一个行为包配套的资源包：先按 com.mojang 目录约定，再按 manifest 依赖 uuid。"""
    bp_path = os.path.abspath(bp_path.rstrip("\\/"))
    base = os.path.basename(bp_path)
    parent = os.path.dirname(bp_path)

    names = []
    for old, new in (("(BP)", "(RP)"), ("(bp)", "(rp)"), ("_BP", "_RP"), ("_bp", "_rp"),
                     ("-BP", "-RP"), ("-bp", "-rp"), ("BP", "RP"), ("bp", "rp")):
        if old in base:
            names.append(base.replace(old, new))
    names.append(base)

    roots = []
    if "development_behavior_packs" in parent:
        roots.append(parent.replace("development_behavior_packs", "development_resource_packs"))
    roots.append(parent)
    roots.append(os.path.join(os.path.dirname(parent), "development_resource_packs"))

    for root in roots:
        for name in names:
            cand = os.path.join(root, name)
            if os.path.isdir(cand) and "rp" in pack_kinds(cand):
                return cand

    # fall back to the uuid link: an RP that depends on this BP's header uuid
    uuid = (manifest_info(bp_path).get("header") or {}).get("uuid")
    if uuid:
        for root in roots:
            if not os.path.isdir(root):
                continue
            try:
                entries = os.listdir(root)
            except OSError:
                continue
            for name in entries:
                cand = os.path.join(root, name)
                if not os.path.isdir(cand) or cand == bp_path:
                    continue
                for dep in (manifest_info(cand).get("dependencies") or []):
                    if isinstance(dep, dict) and dep.get("uuid") == uuid:
                        return cand
    return None


def scan_packs(root: str) -> tuple:
    """遍历解包后的目录，按 manifest 的模块类型分出 BP / RP，并给每个 BP 配对 RP。

    与桌面端完全同一套判定（pack_kinds + find_matching_rp），
    不再使用"看有没有 textures/ 目录"的启发式。
    """
    bps, rps = [], []
    for base, dirs, files in os.walk(root):
        if "manifest.json" not in files:
            continue
        kinds = pack_kinds(base)
        if "bp" in kinds:
            bps.append(base)
        elif "rp" in kinds:
            rps.append(base)
        dirs[:] = []            # 包内不再往下找
    pairs = []
    for bp in bps:
        rp = find_matching_rp(bp)
        if rp is None and len(rps) == 1:
            rp = rps[0]         # 单 RP 的常见情形
        pairs.append((bp, rp))
    if not bps and rps:
        pairs.append((None, rps[0]))
    return pairs, bps, rps
