"""阶段 0 探针：在目标 Android 设备上确认三件事。

打包进 app 跑（或临时塞进 app.py 的 startup 里调一次），把输出贴回来：
    python -c "import experiments.probe_android as p; p.report()"

检查项：
    1. Pillow 是否可导入、能否生成/保存 PNG（C 扩展是否真的编进来了）
    2. 系统 CJK 字体是否找得到（中文标题依赖）
    3. 能否连上官方样本包（联网补全资源依赖）
    4. 目录读写是否正常（私有目录、缓存目录）
"""
from __future__ import annotations


def probe_pillow() -> str:
    try:
        from PIL import Image, ImageDraw, ImageFont, features
    except Exception as exc:
        return f"Pillow 不可用: {exc}"
    try:
        import io
        img = Image.new("RGBA", (64, 64), (198, 198, 198, 255))
        ImageDraw.Draw(img).rectangle((8, 8, 56, 56), fill=(139, 139, 139, 255))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        size = len(buf.getvalue())
        libs = ",".join(k for k in ("zlib", "jpeg", "freetype2")
                        if features.check(k)) or "none"
        return f"Pillow OK, PNG={size}B, 特性: {libs}"
    except Exception as exc:
        return f"Pillow 可导入但渲染失败: {exc}"


def probe_fonts() -> str:
    try:
        from bedrock_recipe_renderer.platform import fonts as pf
    except Exception:
        import glob

        def find():
            pats = ("/system/fonts/*CJK*", "/system/fonts/*Fallback*",
                    "/system/fonts/*SC*")
            out = []
            for p in pats:
                out += glob.glob(p)
            return out
        found = find()
        return f"找到 CJK 字体 {len(found)} 个: {found[:3]}"
    found = pf.find_fonts()
    return f"找到字体 {len(found)} 个: {list(found[:4])}"


def probe_net() -> str:
    try:
        from bedrock_recipe_renderer.platform import net
        net.prepare_tls()
        ok, msg = net.probe(timeout=8)
        return f"联网: {ok} — {msg}"
    except Exception as exc:
        return f"联网探测异常: {exc}"


def probe_paths() -> str:
    try:
        from bedrock_recipe_renderer.platform import paths
        info = paths.describe()
        probe = paths.cache_dir()
        with open(paths.data_dir() + "/probe.txt", "w", encoding="utf-8") as fh:
            fh.write("ok")
        return f"{info}（写入正常，cache={probe}）"
    except Exception as exc:
        return f"目录异常: {exc}"


def report() -> str:
    lines = [
        "=== Android 移植探针 ===",
        "[1] " + probe_pillow(),
        "[2] " + probe_fonts(),
        "[3] " + probe_net(),
        "[4] " + probe_paths(),
        "=== 结语：1 通过 → 方案 B(A/B) 可行；1 失败 → 换 Kivy(路线 A) 或 Chaquopy(路线 C) ===",
    ]
    text = "\n".join(lines)
    print(text)
    return text


if __name__ == "__main__":
    report()
