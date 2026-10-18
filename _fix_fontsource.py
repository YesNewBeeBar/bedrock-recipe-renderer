"""让 GlyphSheets 在"用户原版包里没有 font/ 时"仍能用随包提供的字形页。

现状：__init__ 里 root 是字符串时，self.lang 不会被设置；_page_path 又要求 self.lang
才去问 source，于是随包打包的 vanilla_cache/texts/ja_JP/font 永远用不上。
修法：初始化时无论 root 是否可用，都去 source 里探测一次语言目录。
"""
import io
import os
import shutil

P = r"D:\合成表生成器\mcrender\fonts.py"
s = io.open(P, encoding="utf-8").read()

old = """        self.font_dir = None
        self.lang = None
        if self.root:
            texts = os.path.join(self.root, "texts")
            for lang in self.LANGS + ("*",):
                cand = os.path.join(texts, lang, "font")
                if glob.glob(os.path.join(glob.escape(cand), "glyph_*.png")):
                    self.font_dir = cand
                    break
        elif self.source is not None:
            for lang in self.LANGS:
                path = self.source.find(f"texts/{lang}/font/glyph_00.png", extensions=(".png",))
                if path:
                    self.font_dir = os.path.dirname(path)
                    self.lang = lang
                    break"""
new = """        self.font_dir = None
        self.lang = None
        if self.root:
            texts = os.path.join(self.root, "texts")
            for lang in self.LANGS + ("*",):
                cand = os.path.join(texts, lang, "font")
                if glob.glob(os.path.join(glob.escape(cand), "glyph_*.png")):
                    self.font_dir = cand
                    break
        # 用户的原版包里可能没有 font/（只挑了贴图的精简包），
        # 这时仍要去 source（Vanilla 缓存）里找随包提供的字形页。
        if self.font_dir is None and self.source is not None:
            for lang in self.LANGS:
                path = self.source.find(f"texts/{lang}/font/glyph_00.png", extensions=(".png",))
                if path:
                    self.font_dir = os.path.dirname(path)
                    self.lang = lang
                    break"""
assert old in s, "锚点未找到"
s = s.replace(old, new, 1)

# _page_path：lang 未定也要能按语言目录探一遍
old2 = """    def _page_path(self, key: str):
        if self.source is not None and self.lang:
            hit = self.source.find(f"texts/{self.lang}/font/glyph_{key}.png", extensions=(".png",))
            if hit:
                return hit"""
new2 = """    def _page_path(self, key: str):
        if self.source is not None and self.lang:
            hit = self.source.find(f"texts/{self.lang}/font/glyph_{key}.png", extensions=(".png",))
            if hit:
                return hit
        if self.source is not None and self.font_dir is None:
            for lang in self.LANGS:            # 语言目录未知时逐个探
                hit = self.source.find(f"texts/{lang}/font/glyph_{key}.png",
                                       extensions=(".png",))
                if hit:
                    return hit"""
assert old2 in s, "_page_path 锚点未找到"
s = s.replace(old2, new2, 1)
io.open(P, "w", encoding="utf-8").write(s)
print("fonts.py 已补 source 回退 ✓")

# 桌面端：字体页放进 vanilla_cache（build_exe.ps1 会 --add-data 打进 exe）
SRC = r"D:\A_only_for_Baka_Bee\Minecraft\Minecraft_samples\resource_pack\texts\ja_JP\font"
for dst in (r"D:\合成表生成器\vanilla_cache\texts\ja_JP\font",):
    os.makedirs(dst, exist_ok=True)
    n = 0
    for f in os.listdir(SRC):
        if f.startswith("glyph_") and f.endswith(".png"):
            shutil.copyfile(os.path.join(SRC, f), os.path.join(dst, f))
            n += 1
    print(f"  {dst}: {n} 张")

# Kivy 端把字体目录单独补进 assets（Kivy 版 vanilla 通过 resource_roots 走 vanilla_cachedir，这里冗余无害）
KIVY = r"D:\合成表生成器移动端\android-kivy"
if os.path.isdir(os.path.join(KIVY, "vanilla_cache")):
    dst = os.path.join(KIVY, "vanilla_cache", "texts", "ja_JP", "font")
    os.makedirs(dst, exist_ok=True)
    for f in os.listdir(SRC):
        if f.startswith("glyph_") and f.endswith(".png"):
            shutil.copyfile(os.path.join(SRC, f), os.path.join(dst, f))
    print(f"  {dst}: 已同步")
