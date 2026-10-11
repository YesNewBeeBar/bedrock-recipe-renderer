# Android 版（Kivy + Buildozer）

把桌面版的渲染核心 `mcrender/` **原样复用**，只在外层换成 Kivy 界面 + Android 平台层。
当前版本 **v1.0.9**（`android.numeric_version = 11`）。

## 为什么是 Kivy + Buildozer

`python-for-android` 有**官方维护的 Pillow recipe** ✓。
Briefcase/Chaquopy 那条路的 Android 轮子仓库里只有 Pillow 7.0.0（cp38）→ 走不通
（实跑验证见 [../PORTING.md](../PORTING.md) 末尾）。

## 目录结构

```
android-kivy/
├── main.py                  Kivy 界面（唯一入口）
├── buildozer.spec           打包配置（版本号、权限、include_exts）
├── platform_layer/          Android 平台层（核心不依赖它）
│   ├── paths.py             私有目录 / 缓存 / 工作目录
│   ├── fonts.py             中文字体（随包优先 + 系统兜底）
│   ├── browser.py           内置文件浏览器（Kivy 控件）
│   ├── perm.py              「所有文件访问」权限申请与检测
│   ├── picking.py           异步文件/目录选择、压缩包解包
│   ├── storage.py           ZIP 打包与系统分享
│   ├── crashlog.py          崩溃弹窗（App 内显示 + 一键复制）
│   ├── androidfs.py         SAF 目录读写（备用路径）
│   └── net.py               网络相关
├── mcrender/                与桌面版**同一份**渲染核心（由 sync_core.py 同步）
├── assets/                  UI 面板等（smithing.png / stonecutter.png）
├── fonts/                   NotoSansSC-Regular.ttf（界面字体，17 MB）
├── vanilla/                 内置原版素材 2139 个（1.5 MB）
├── wiki_cache/              内置 wiki 图标 342 个（273 png，0.1 MB）
└── build_mobile.sh          WSL 里的构建脚本（同步源码 → buildozer → 拷贝产物）
```

## 构建

本机已装好 WSL2(Ubuntu) + JDK17 + Android SDK/NDK，工程常驻 `/root/brr`（纯 ASCII 路径）。

```powershell
# Windows 侧一条命令：同步源码 → buildozer 出包 → 拷贝到 D:\演示
wsl -d Ubuntu -u root -- bash /root/build_mobile.sh

# 交付（重命名 + 解包核对）
wsl -d Ubuntu -u root -- bash /root/deliver.sh
```

`build_mobile.sh` 会同步这些内容到 `/root/brr`：`main.py`、`buildozer.spec`、
`platform_layer/*.py`、`mcrender/*.py`、`fonts/`、`vanilla/`、`wiki_cache/`，
然后把 `\r\n` 转成 LF（否则 `gradlew` 会因为 `$'bash\r'` 报错）。

产物：`/root/brr/bin/bedrockreciperenderer-<版本>-arm64-v8a-debug.apk`

### 改版本号

```powershell
python set_version.py 1.0.10 12     # 参数：版本名、versionCode（必须递增）
```

`version` 是显示用的版本名，`android.numeric_version` 是 Android 的 `versionCode` ——
**后者不递增，安装时会提示"已安装相同版本"**。

## 内置素材（离线可用）

| 目录 | 内容 | 体积 |
|---|---|---|
| `vanilla/` | 会进入合成表的全部原版贴图（含 `.tga`）+ `item_texture.json` / `terrain_texture.json` / `blocks.json` | 1.5 MB |
| `wiki_cache/` | 头颅、头、床、旗帜、告示牌、潜影盒、花盆、植物、药水、失水恶魂等的库存图标 | 0.1 MB |
| `fonts/` | Noto Sans SC（OFL 许可，可随包分发） | 17 MB |

两者都由脚本从官方源预抓：

```powershell
python fetch_vanilla.py     # → android-kivy/vanilla/
python fetch_wiki.py        # → android-kivy/wiki_cache/
```

> `wiki_cache` 里的 `*.none` 是"维基上确实没有"的标记，**必须一起打包**
> （否则运行时会反复联网重试，出图变慢）。`.tga` 也必须包含在
> `source.include_exts` 里，否则原版有 52 张贴图进不了包。

## 关键实现说明（踩过的坑）

1. **不用 SAF 文件选择器**。部分 ROM（realme/OPPO 等）会黑屏、返回键退出 App、
   只能选单个文件。现在用「所有文件访问权限 + 内置文件浏览器」，全程不跳 Activity。
2. **选择器必须异步**。`startActivityForResult` 在主线程发起后**立刻返回**，
   结果在 `on_activity_result` 回调里处理 —— 早期版本在主线程 `sleep` 死等，直接黑屏。
3. **配方识别交给核心** `mcrender.recipes.collect()`，不要自己按目录名找
   （自己找只认 `recipes/` 根目录，实测同一包 14 条 vs 核心 310 条）。
   `collect()` 返回的是 **Recipe 对象**，不要再喂给 `parse(path)`。
4. **解包逻辑与桌面版一致**：找含 `manifest.json` 的目录判定 BP/RP，
   对 BP 根递归收集；`.mcaddon` 常见双层压缩，要逐层解开。
5. **离线时 `wiki_icons="off"`**，且默认「只用本地」——否则每条缺素材都会联网，
   手机上一次超时就卡住，266 条要等很久。

## 诊断

出图会写 `<出图目录>/合成表/_诊断.log`（放在导出目录内，导出 ZIP 会带上），内容包括：
版本、选择的文件、RP 是否读到、`item_texture` 键数、解包文件数、逐段耗时、
最慢 5 条、缺失纹理 id 列表。

崩溃时会弹窗显示完整 traceback + 「复制日志」按钮（Android 11+ 隐藏了
`Android/data`，文件管理器拿不到日志文件）。

## 已知限制

- **第三方文件管理器无法通过 Intent 调用**：Android 只允许实现了
  `DocumentsProvider` 的管理器出现在系统选择器中，MT 管理器这类不提供该接口 ——
  所以内置浏览器是主路径。
- `/sdcard/Android/data/<其它包>/` 仍不可读（系统限制），但那里不放整合包。
- 仅 `arm64-v8a`（2016 年后的手机）。
- 少数物品（如 `oak_sign`、`flower_pot`）维基无对应条目，仍用内置几何体绘制。

## 与桌面版的关系

- `mcrender/` 由 `sync_core.py` 保持与桌面版一致；核心 bug 修复应**两边同步**。
  移植期间在移动端发现并已同步回桌面端的修复：
  - `assets.py`：`item_texture` 键的**词元模糊匹配**（`lv0stone_boots` → `stonecraft.boots.lv0`）
  - `wiki.py`：删除重复定义的 `_note_failure`（旧签名覆盖了带 `permanent` 的新签名）
  - `vanilla.py`：`CORE_FILES` 补上酿造台面板需要的 4 张贴图
- 桌面端专属文件（`mcrender_gui.py` 等）不参与 Android 构建。
