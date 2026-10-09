# Bedrock Recipe Renderer（合成表生成器）

把 Minecraft **基岩版**附加包的配方渲染成**和游戏内界面一致**的 PNG 图片。

拖进配方 JSON、行为包 / 资源包文件夹，或 `.mcaddon` / `.mcpack` / `.mcworld` / `.zip` 压缩包，
一键输出**合成台 / 熔炉 / 切石机 / 锻造台 / 酿造台**界面图。

![example](docs/example_stone_star.png)

> 逐像素重绘游戏界面：容器面板、库存格内凹高光、数量角标、进度箭头、熔炉火焰、
> 酿造台管路与气泡、无序合成的「乱序」标记、锻造台槽位覆盖图。

---

## 特性

- **7 类机型**：`recipe_shaped` / `recipe_shapeless` / `recipe_furnace` / `recipe_stonecutter` /
  `recipe_smithing_transform` / `recipe_brewing_mix` / `recipe_brewing_container`
- **按 `tags` 判定机器**：切石机、熔炉常被写成普通的 `recipe_shapeless`，只靠标签标明站点，不会画错机器
- **像素级还原**：方块用内置几何体 + z-buffer 光栅化，直接按输出倍率计算像素（不是放大糊图）
- **完全离线**：给一个原版包（**文件夹或 zip 都行**）或补全一次纹理，之后不再发任何网络请求
- **批量与命令行**：整套附加包一次出图，支持 `--headless` 批处理
- **绿色免安装**：Windows 64 位，exe 已内置 Python 运行时，不需要装 Python，也不需要装游戏

---

## 快速开始（使用现成 exe）

1. 到 [Releases](https://github.com/YesNewBeeBar/bedrock-recipe-renderer/releases) 下载 exe
2. 双击运行，先点「**输出目录**」→「选择…」设好输出位置
3. 把 `.mcaddon` / `.zip` / 配方文件夹**拖进窗口** → 自动出图
   （或先选「行为包 BP」「资源包 RP」，再点 **▶ 开始出图**）

**建议先做一次**：把「原版包」指向本机 `bedrock-samples` 的 `resource_pack` 文件夹，
**或任意资源包 zip**（可只打包合成需要的贴图）。只要里面有 `textures/item_texture.json`，
工具会立刻切到**纯本地模式**，全程离线 —— 首次运行也不会卡在下载上。

不想准备原版包，也可以点「**补全原版资源（下载全部纹理）**」联网下齐（约 2100 项），
全部成功后同样会自动进入纯本地模式。

详细说明见 **[使用说明.md](使用说明.md)**；历次修复记录见 **[DEVELOPMENT.md](DEVELOPMENT.md)**。

---

## 从源码运行

需要 Python 3.11+（开发环境为 3.14）与 Pillow：

```bash
pip install -r requirements.txt
python mcrender_gui.py
```

命令行（无窗口批处理）：

```bat
python mcrender_gui.py --headless <文件或目录> [<文件或目录> ...]
python mcrender_gui.py --sync-vanilla
```

打包 exe：双击 `build_exe.bat`（需要 `pyinstaller`），产物在 `dist\`。

---

## 贴图从哪来

按优先级查找每个贴图 / 模型 / JSON：

1. **内置资源** —— `assets/ui`（箭头、火焰、酿造台管路与气泡、锻造台图标与槽位覆盖图等 15 张界面贴图）
2. **本地包** —— 你指定的资源包、行为包、原版包（文件夹或 zip）
3. **本地缓存** —— exe 同目录的 `vanilla_cache/`
4. **官方样本包** —— `Mojang/bedrock-samples` 按需单个下载（可被纯本地模式关闭）

箱子、床、旗帜、头颅等游戏内特殊渲染的方块，以及会被生物群系染色的植物，
会回退到 **Minecraft Wiki** 的物品图标；完全离线时用内置几何体自绘。

---

## 项目结构

| 模块 | 职责 |
| --- | --- |
| `mcrender_gui.py` | 主程序：界面、拖放、解包、BP/RP 配对、配置、命令行入口 |
| `mcrender/recipes.py` | 配方 JSON → 统一的 `Recipe` 结构 |
| `mcrender/render.py` | 组装面板图：版式、槽位、箭头、标题、数量角标 |
| `mcrender/panel.py` | 原版 GUI 图元：容器面板、库存格、管路、GUI 精灵图 |
| `mcrender/icon.py` | 物品 / 方块图标光栅化：平面精灵 + 等距立方体 |
| `mcrender/geometry.py` | 基岩版方块几何（`.geo.json`）+ z-buffer 渲染 |
| `mcrender/shapes.py` | 内置原版方块几何（游戏内部不可读的那批） |
| `mcrender/assets.py` | 跨 BP / RP / 原版包的贴图与标识符解析、染色、wiki 回退 |
| `mcrender/vanilla.py` | 多级资源查找（内置 → 本地包/zip → 缓存 → GitHub 按需下载） |
| `mcrender/wiki.py` | wiki 图标抓取与缓存 |
| `mcrender/fonts.py` | 位图字体：随包 CJK 字形 + 内置 ASCII 5×7 字体 + 系统字体兜底 |
| `mcrender/jsonc.py` | 宽松 JSON 读取（BOM / 注释 / 尾随逗号） |

---

## 说明

- 对附加包**只读**：解包在临时目录，输出只写入你指定的输出目录
- 仅支持**基岩版**配方格式，不支持 Java 版
- 本工具与 Mojang / Microsoft 无关联；Minecraft 是 Mojang Studios 的商标

## License

[MIT](LICENSE)
