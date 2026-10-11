"""网络：核心用的是 urllib + 官方 GitHub raw。Android 上只需要
1) 声明 INTERNET 权限（pyproject.toml 里已配）
2) 保证 TLS 证书链可用（certifi；Android 系统根证书通常够用）
3) 尊重「只用本地」开关，避免移动网络下误下载
"""
from __future__ import annotations

import os
import ssl


def prepare_tls() -> str:
    """返回当前使用的 CA bundle 路径（找不到就返回空串，交给系统默认）。"""
    try:
        import certifi
        bundle = certifi.where()
    except Exception:
        bundle = ""
    if bundle and os.path.isfile(bundle):
        os.environ.setdefault("SSL_CERT_FILE", bundle)
        os.environ.setdefault("REQUESTS_CA_BUNDLE", bundle)
    return bundle


def ssl_context() -> ssl.SSLContext:
    """给 urllib 用的默认上下文（带 SNI，Android 上必须）。"""
    ctx = ssl.create_default_context()
    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED
    return ctx


def probe(timeout: float = 6.0) -> tuple[bool, str]:
    """探测能否连上官方样本包（给「在线/离线」指示灯用）。"""
    import urllib.request
    url = ("https://raw.githubusercontent.com/Mojang/bedrock-samples/main/"
           "resource_pack/manifest.json")
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return True, f"HTTP {resp.status}"
    except Exception as exc:
        return False, str(exc)[:120]
