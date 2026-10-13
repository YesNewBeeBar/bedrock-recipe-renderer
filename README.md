# 合成表生成器（Bedrock Recipe Renderer）

把 Minecraft 基岩版的合成配方 JSON 渲染成**游戏内界面风格的 PNG**（含同标签物品轮播 GIF）。

## 界面

桌面端使用 **PySide6 + PySide6-Fluent-Widgets**（WinUI 3 / Fluent Design 风格）：
真实抗锯齿圆角、原生拖放、明暗主题一次切换（首次启动跟随系统，之后记住用户选择）。

- 入口：`mcrender_fluent.py`
- 打包：`build_exe.ps1`（PyInstaller onedir，启动约 1 秒）

## 结构

| 路径 | 作用 |
|---|---|
| `mcrender/` | **渲染核心**（配方解析、贴图解析、绘制、GIF、输出目录）—— 三端共用 |
| `mcrender_app.py` | 业务逻辑：配置读写、解包、包识别、`Generator` 出图流水线 |
| `mcrender_fluent.py` | 桌面端界面（Fluent） |
| `gui_theme.py` | 小工具：读取系统深浅色（首次启动跟随设备用） |
| `vanilla_cache/` `wiki_cache/` `wiki_pinned/` | 贴图与图标资源（`wiki_pinned` 为人工钉死的图标，优先级最高） |
| `tags_be.json` `vanilla_kinds.json` | 基岩版标签库、物品/方块判定表 |

## 其他端

- **移动端**：`D:\合成表生成器移动端\`（Android，共用同一份 `mcrender/`）
- 旧版 tkinter 界面已归档：`_backup_tkinter/`，git tag `v1.0-tkinter-ui`
