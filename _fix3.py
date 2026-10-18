"""修三处：标题字形、oxidized_copper 误判、原版物品模糊。

① 标题：内置手绘字形（仅 7 个汉字）优先级高于原版字形页，导致"合成/熔炉"一直
   用粗糙手绘字。原版 CJK 字形页 (texts/ja_JP/font, 831KB/120 张) 之前没随包提供。
   → 补进 vanilla/texts/ja_JP/font/，并把 glyph() 的查找顺序改成"原版页 → 内置 → 系统"。

② 模糊匹配：oxidized_copper 被 _fuzzy_item_key 匹配到 oxidized_copper_door
   （键词元 = 目标词元 + 一个 door），因为阈值只看重合度不看多余词元。
   → 词元数超过目标的一律不采纳（door 是 3 > 2）。

③ 模糊图标：16x16 像素画被 LANCZOS 放大到 64x64 → 变糊。
   → 放大一律 NEAREST（像素画保持硬边），只有缩小大图时才用 LANCZOS。
"""
import io
import os
import shutil

ROOT = r"D:\合成表生成器"
changed = []

# ---------------- ② 模糊匹配：拒绝词元过多的候选 ----------------
p = os.path.join(ROOT, "mcrender", "assets.py")
s = io.open(p, encoding="utf-8").read()
old = """            hits = len(want & have)
            if hits < 2:                      # 只重合一个词太容易误判
                continue
            score = hits / max(1, min(len(want), len(have)))"""
new = """            hits = len(want & have)
            if hits < 2:                      # 只重合一个词太容易误判
                continue
            # 候选词元比目标还多，说明它是个"更长的近亲"：
            # oxidized_copper → oxidized_copper_door、copper → copper_door。
            # 这类只能是误判，直接排除（issue：铜块被认成铜门）。
            if len(have) > len(want):
                continue
            score = hits / max(1, min(len(want), len(have)))"""
assert old in s, "② 锚点未找到"
s = s.replace(old, new, 1)
io.open(p, "w", encoding="utf-8").write(s)
changed.append("② assets.py 模糊匹配已收紧")

# ---------------- ③ 平面图标：放大用 NEAREST ----------------
p = os.path.join(ROOT, "mcrender", "icon.py")
s = io.open(p, encoding="utf-8").read()
old = """    if img.size != (size, size):
        img = img.resize((size, size), Image.LANCZOS if smooth else Image.NEAREST)
    return img"""
new = """    if img.size != (size, size):
        # 放大：像素画必须 NEAREST，否则 16x16 的钻石/铁锭放大后发糊。
        # 缩小：wiki 的大尺寸渲染图才用 LANCZOS 平滑。
        upscaling = size > img.width
        resample = Image.NEAREST if (upscaling or not smooth) else Image.LANCZOS
        img = img.resize((size, size), resample)
    return img"""
assert old in s, "③ 锚点未找到"
s = s.replace(old, new, 1)
io.open(p, "w", encoding="utf-8").write(s)
changed.append("③ icon.py 放大改用 NEAREST")

# ---------------- ① 字形：原版页优先 ----------------
p = os.path.join(ROOT, "mcrender", "fonts.py")
s = io.open(p, encoding="utf-8").read()
old = """        builtin = builtin_glyphs().get(ch)
        if builtin is not None:
            return builtin if size == 16 else builtin.resize((size, size), Image.BOX)
        cp = ord(ch)
        page = self._page(cp >> 8)
        if page is not None:"""
new = """        # 原版字形页优先：那是游戏自己的汉字，比内置手绘字准确得多。
        # 内置字只作为回退（原版包里没有该页时才用）。
        cp = ord(ch)
        page = self._page(cp >> 8)
        if page is None and ch in builtin_glyphs():
            builtin = builtin_glyphs()[ch]
            return builtin if size == 16 else builtin.resize((size, size), Image.BOX)
        if page is not None:"""
assert old in s, "① 锚点未找到"
s = s.replace(old, new, 1)
io.open(p, "w", encoding="utf-8").write(s)
changed.append("① fonts.py 字形查找顺序已改为原版页优先")

for c in changed:
    print(" ", c)
