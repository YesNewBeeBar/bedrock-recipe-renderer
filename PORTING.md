# 从桌面端移植到 Android —— 完整方案

> 目标仓库：`YesNewBeeBar/bedrock-recipe-renderer`
> 本目录 `android/` 是移植工程；核心逻辑从本仓库的 `mcrender/` 同步（`sync_core.py`），**不改桌面版源码**。

---

## 一、可行性总结

**结论：可行，而且比预期容易。** 关键依据（都是在本仓库实测的）：

| 检查项 | 实测结果 |
| --- | --- |
| 核心模块导入方式 | **全部是相对导入**（`from . import xxx`），没有任何 `import mcrender` 绝对导入 → 整包可以直接塞进 APK ✓ |
| 核心代码量 | `mcrender/` 约 3900 行，**纯 Python + Pillow**，无 C 扩展、无平台 API |
| 平台相关代码 | 全仓库**只有 1 行**：`fonts.py` 的 `_SYSTEM_FONTS`（Windows 字体路径） |
| Tkinter 依赖 | 仅存在于 `mcrender_gui.py`（888 行）→ 只重写这一层 |
| 网络 | 标准库 `urllib` → Android 只需 `INTERNET` 权限 |
| 第三方依赖 | 只有 **Pillow**（+ 可选 certifi） |
| 临时目录 / 缓存 | 核心已通过 `tool_root`、`cache_dir` 参数注入 → 平台层给什么用什么 ✓ |

**真正的风险只有一个：Pillow 的 Android 轮子。** 其余全是纯 Python。
因此建议按下面顺序落地（这也是对你「有没有更好的方式」的回答）：

| 路线 | Pillow 可用性 | UI 成本 | 推荐度 |
| --- | --- | --- | --- |
| **A. Kivy + Buildozer** | `python-for-android` 有**官方维护的 Pillow recipe**，最稳 | 重写 ~300 行 | ★★★★★ |
| **B. BeeWare + Briefcase（你指定）** | 需要 Android 轮子；Briefcase 走 mobile-forge，**要先验证** Pillow 能否解析到 | 重写 ~300 行（Toga 代码最干净） | ★★★★（Pillow 通过后等同 A） |
| **C. Chaquopy + 原生壳/WebView** | Chaquopy 仓库**直接提供 Pillow 轮子** | 需要 Android Studio 工程 | ★★★★（UI 成本最高） |
| D. 服务端渲染 + APP 只做上传下载 | 无 | 最省 | ★★（要服务器，隐私差） |

> **建议**：按 B 写界面代码（本目录已经写好），**先花 10 分钟做第六节的 Pillow 探针**；
> 探针失败就把同一份 `app.py` 里的 Toga 换成 Kivy（`kivy_alt/` 已给出等价实现），核心代码一行不用动。

---

## 二、架构分层方案

```
┌──────────────────────────── UI 层（平台相关，每个平台一份） ────────────────────────────┐
│  Desktop: mcrender_gui.py (Tkinter)     Android: android/src/…/app.py (Toga)            │
│  Kivy 备选: kivy_alt/main.py            iOS: 同一份 Toga 代码可直接用                     │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │ 只调用 3 个入口
┌───────────────────────────────────────────▼────────────────────────────────────────────┐
│  Platform 层（android/src/bedrock_recipe_renderer/platform/）                            │
│  paths.py    目录：data / cache / exports / work（app.paths → Android 私有目录）          │
│  picker.py   文件选择：Toga 对话框 → Android SAF；content:// 落本地                       │
│  fonts.py    系统 CJK 字体探测（/system/fonts/*），注入核心的 _SYSTEM_FONTS               │
│  storage.py  导出：打包 ZIP / 逐张另存 / 系统分享（Intent）                                │
│  net.py      TLS 证书（certifi）、联网探测、离线开关                                       │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │ Assets / Renderer / parse —— 参数注入
┌───────────────────────────────────────────▼────────────────────────────────────────────┐
│  Core 层（mcrender/：桌面与移动端**完全同一份代码**）                                      │
│  recipes.py  render.py  panel.py  icon.py  geometry.py  shapes.py                        │
│  assets.py   vanilla.py  wiki.py   fonts.py  jsonc.py  cli.py                            │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

**分层原则**（移植时严格遵守，就不会出现"改一处坏两处"）：

1. **Core 不 import 任何平台 API**：不碰 `tkinter` / `os.startfile` / `C:\` 路径。
   已有代码基本满足；唯一例外 `_SYSTEM_FONTS` 用平台层**运行期替换**，不动源码。
2. **所有路径由平台层注入**：`Assets(tool_root=…, cache_dir=…)`、`Renderer` 找 `assets/panels` 时会
   依次看 `tool_root/assets/` 与模块同级目录 —— 打包后模块同级目录 = APK 内只读资源 ✓
3. **UI 层只做四件事**：选输入 → 调核心 → 报进度 → 导出。不写渲染逻辑。

---

## 三、详细移植步骤（分阶段）

### 阶段 0：探针（0.5 天）—— 决定路线 A/B
1. 在目标手机上跑 `experiments/probe_android.py`（或用 Briefcase 直接 `briefcase run android` 一个空壳）。
2. 检查三件事：`import PIL` 成功、`/system/fonts` 能找到 CJK 字体、`urllib` 能连 GitHub raw。
3. **Pillow 失败就切路线 A（Kivy）或 C（Chaquopy）**，不要在这里硬啃交叉编译。

### 阶段 1：工程骨架（0.5 天）
1. `pip install briefcase` → `briefcase create android`（首次会下 Gradle/SDK，约 10–20 分钟）。
2. 放进 `pyproject.toml` + `src/bedrock_recipe_renderer/`（本目录已备好）。
3. `python sync_core.py` 把 `mcrender/` 同步进 app 包，`briefcase run android` 看到空界面。

### 阶段 2：打通"选文件 → 出图"（1–2 天）
1. 接 `platform/paths.py`（data/cache/exports）。
2. 接 `picker.pick_files()`（JSON/压缩包）与 `pick_folder()`（BP/RP）。
3. 后台线程跑 `RenderJob`（本目录已实现），进度条 + 日志回 UI。
4. **验收**：手机选一个 `.mcaddon`，输出目录里出现和桌面端一致的 PNG。

### 阶段 3：字体与资源（0.5 天）
1. `platform_fonts.install()` 在首次渲染前调用（替换 `_SYSTEM_FONTS`）。
2. 若某些 ROM 找不到 CJK 字体，往 app 包里塞一个（`resources/fonts/NotoSansSC-Regular.otf`，约 8 MB）并加进候选列表。

### 阶段 4：导出与分享（0.5 天）
1. 「导出 ZIP」+「分享」（`storage.py`）。
2. 需要相册可见时，用 Toga `save_file`（SAF 的 `ACTION_CREATE_DOCUMENT`）；不要强行申请 `MANAGE_EXTERNAL_STORAGE`（会被商店下架）。

### 阶段 5：离线与性能（1 天）
1. 离线路线同桌面：给一个原版包 zip（SAF 选入）→ 立刻 `local_only=True`，全程不联网。
2. 批量渲染时用 `concurrent.futures` 分片 + 每张图回调进度；低端机限制并发为 1。
3. 退出时清理 `cache/work`（解包残留）。

### 阶段 6：打包发布（0.5 天）
1. `briefcase package android --packagename com.yesnewbeebar.brr` 出签名 APK/AAB。
2. GitHub Actions 配 `briefcase build android` + `upload-release-asset`，tag 触发。

**合计约 4–5 个工作日。**

---

## 四、BeeWare 项目骨架与核心代码片段

本目录已生成可直接运行的骨架：

```
合成表生成器移动端/
├─ sync_core.py                     # 桌面核心 → android/src/.../mcrender/
├─ android/
│  ├─ pyproject.toml                # Briefcase 配置（Android/iOS/桌面）
│  └─ src/bedrock_recipe_renderer/
│     ├─ __main__.py                # 入口
│     ├─ app.py                     # ★ Toga 界面（替代 mcrender_gui.py）
│     ├─ platform/{paths,picker,fonts,storage,net}.py   # ★ 平台适配层
│     ├─ mcrender/                  # ★ 桌面核心的只读副本（sync_core.py 生成）
│     ├─ assets/{ui,panels}/        # 内置 UI 贴图与裁剪面板
│     └─ resources/icon.png         # 应用图标
├─ kivy_alt/                        # 路线 A：Kivy + Buildozer 等价实现
└─ experiments/probe_android.py     # 阶段 0 探针
```

**核心调用片段**（`app.py` 里，与桌面版一致的部分）：

```python
assets = Assets(
    bp_dir=bp or None, rp_dir=rp or None, vanilla_dir=vanilla or None,
    wiki_root=paths.tool_root(), wiki_icons=wiki_icons, wiki_language="en",
    vanilla_download=not local_only, local_only=local_only,
    tool_root=paths.tool_root(), bundle_root=paths.tool_root(),
)
renderer = Renderer(assets, scale=scale, layout=layout, background=None)
img, _lay = renderer.render(parse(recipe_path))
img.save(dest_png)
```

**后台线程 + 进度**（Toga 是 asyncio 的，所以用 `asyncio.to_thread`）：

```python
job = RenderJob(self._ui_log, self._ui_progress)
result = await asyncio.to_thread(job.run, bp=..., files=...)
self.progress.value = 1
```

---

## 五、Android 权限、文件路径、网络适配

### 5.1 权限（`pyproject.toml` 已配）

```toml
[tool.briefcase.app.bedrock_recipe_renderer.android]
permission.INTERNET = "按需下载官方原版贴图（可关闭）"
permission.ACCESS_NETWORK_STATE = "判断是否联网，避免移动网络下误下载"
permission.WRITE_EXTERNAL_STORAGE = "旧系统（Android 10 以下）导出图片"
```

**不要**申请 `MANAGE_EXTERNAL_STORAGE`：商店会拒审，而且用 SAF 完全能实现导出。

### 5.2 目录（`platform/paths.py`）

| 用途 | Android 实际位置 | 说明 |
| --- | --- | --- |
| 数据 | `/data/data/com.yesnewbeebar.brr/files/` | 免权限、随卸载清除；放导出与输出 |
| 缓存 | `…/cache/` | 系统可清理；放 `vanilla_cache`、`wiki_cache`、解包残留 |
| 内置资源 | APK 内只读 | `assets/ui`、`assets/panels` |
| 用户文件 | SAF `content://` | 通过选择器/另存对话框读写，不猜路径 |

桌面开发时全部落到 `.devdata/`，与手机行为隔离。

### 5.3 网络

```python
from bedrock_recipe_renderer.platform import net
net.prepare_tls()          # 注入 certifi 的 CA bundle（Android 系统根证书通常也够）
ok, msg = net.probe()      # UI 上可以显示「在线 / 离线」
```

离线优先策略（与桌面版一致）：**给一个原版包 zip → 立刻 `local_only=True`**，之后一次请求都不发。

### 5.4 拖放 → 选择器

桌面版的 `WM_DROPFILES` 拖放在 Android 上不存在，替换为：
- 选配方：`dialog.open_file(multiple=True, file_types=["json","zip","mcaddon",…])`
- 选文件夹（BP/RP）：`dialog.select_folder()`
- 输出：默认写私有 `exports/`，再用「导出 ZIP / 分享」交出去（比让用户选目录更省事）

---

## 六、Pillow 在 Android 上的兼容性处理

**先探针，再决定，不要盲目交叉编译。**

```bash
# 1) 用 Briefcase 建一个只 import PIL 的空壳
briefcase create android && briefcase build android && briefcase run android
# 2) 看日志里有没有 "No matching distribution" / "pillow" 解析失败
```

三条处理路径，按成本从低到高：

1. **让 Briefcase 解析现成轮子**（首选）
   Briefcase 支持从 PyPI 拉 `*-android_*` 轮子；Pillow 官方**不发布** Android 轮子，
   但 BeeWare 生态（mobile-forge）维护了一批常用包，先试 `requires = ["pillow"]`。
2. **自建轮子**（可行但重）
   用 BeeWare 的 `mobile-forge` 交叉编译 Pillow：需要 Android NDK + 依赖
   （`zlib`、`libjpeg-turbo`、`freetype`、`libpng`），约 1–2 小时机器时间。
   产物丢进 `wheels/` 并在 `pyproject.toml` 用 `--add-binary`/`sources` 引入。
3. **换路线**（最省时间）
   - **Kivy + Buildozer**：`requirements = python3,kivy,pillow`，`python-for-android` 内置 Pillow recipe，几乎必成。
   - **Chaquopy**：Gradle 里 `install "com.chaquo.python:pypi:pillow"`，官方有轮子。

**代码层面的兼容注意点**（本工程已规避）：

| 风险 | 处理 |
| --- | --- |
| `Image.Resampling` 新旧 API 差异 | 核心只用 `Image.NEAREST` 等常量，兼容 |
| `ImageFont.truetype` 需要真实字体文件 | `platform/fonts.py` 探测 `/system/fonts`，找不到就退回内置位图字形 |
| `ImageDraw.text` 缺 CJK 字形 | 核心 `system_glyph()` 会二值化渲染，Android 上字体必须存在（阶段 3 处理） |
| 大图内存（批量 704×416 输出） | 单张即时 `save()` 后释放；低端机并发设为 1 |
| `ImageFile.LOAD_TRUNCATED_IMAGES` | 某些 wiki 下载图不完整，可在 `net.py` 里统一打开该开关 |

---

## 七、打包 APK 的完整命令

```bash
# ---------- 一次性准备 ----------
python -m pip install --user briefcase
# 需要 JDK 17 + Android SDK/NDK（Briefcase 会自动下载，或设 ANDROID_HOME 复用本机的）

# ---------- 同步核心 ----------
cd 合成表生成器移动端
python sync_core.py            # 桌面核心 → android/src/bedrock_recipe_renderer/mcrender/
python sync_core.py --check    # 提交前确认没有漂移

# ---------- 构建 ----------
cd android
briefcase create android                     # 生成 Gradle 工程（首次 10~20 分钟）
briefcase build android                      # 编译 APK
briefcase run android                        # 装到已连接设备/模拟器并运行
briefcase run android -d "Pixel_7_API_34"    # 指定模拟器

# ---------- 打包发布 ----------
keytool -genkey -v -keystore brr.keystore -alias brr \
        -keyalg RSA -keysize 2048 -validity 10000
briefcase package android \
    --packagename com.yesnewbeebar.brr \
    --keystore brr.keystore --keystore-alias brr \
    --signing-mode release
# 产物：android/build/bedrock_recipe_renderer/release/bedrock_recipe_renderer-1.0.0.aab
#       （如需 APK 侧载，加 --packaging-format apk）

# ---------- 日志排查 ----------
briefcase run android --log                  # 直接看 Python traceback
adb logcat | grep -i python
```

**CI（GitHub Actions）要点**：`actions/setup-java@v4 (temurin 17)` →
`briefcase build android` → `actions/upload-artifact` 上传 APK；
tag 触发时用 `softprops/action-gh-release` 发到 Releases。

---

## 八、风险清单与优化建议

| # | 风险 | 影响 | 应对 |
| --- | --- | --- | --- |
| 1 | **Pillow 无 Android 轮子** | 卡在构建 | 先用探针判定；失败切 Kivy/Chaquopy（本目录已备 Kivy 版） |
| 2 | **ROM 无 CJK 字体** | 中文标题变方框 | `platform/fonts.py` 多路径探测；仍失败则随包内置 8 MB 字体 |
| 3 | **SAF 拿到 `content://`** | 核心读不到文件 | `picker.ensure_local()` 先复制进私有目录（本工程已实现） |
| 4 | **大包解压占内存/存储** | 低端机 OOM | 流式解压、限制嵌套层数、退出清理 `cache/work` |
| 5 | **批量渲染阻塞 UI** | 界面卡死/被系统杀 | `asyncio.to_thread` + 每张图回调进度（已实现） |
| 6 | **移动网络下误下载** | 用户流量损失 | 默认「只用本地」可开；`ACCESS_NETWORK_STATE` 判断后询问 |
| 7 | **Android 10+ 分区存储** | 写公共目录失败 | 一律写私有目录 + SAF 导出/分享，不猜路径 |
| 8 | **APK 体积**（Pillow + Python ≈ 25–40 MB） | 下载门槛 | 剥离 `matplotlib/numpy` 等无关模块（已在 `build_exe.bat` 做过，Android 同理 `--exclude`） |
| 9 | **后台进程被杀死**（渲染到一半） | 输出不完整 | 已渲染的 PNG 直接落盘；重跑时跳过已存在文件 |
| 10 | **未来核心改动与移动端漂移** | 两边行为不一致 | `sync_core.py --check` 放进 CI，或改成 git submodule |

### 优化建议（按性价比排序）

1. **先做「离线 zip」路径**：让用户用 SAF 选一个原版包 zip，立刻 `local_only=True`。
   移动端网络不可靠，这一步能消掉 80% 的"卡住/缺图"投诉。
2. **输出默认写私有目录 + 一键分享 ZIP**，比让用户选目录省事得多，也绕开所有存储权限问题。
3. **进度用「已出图数 / 总数」**，而不是百分比假动画 —— 移动端用户对卡顿极敏感。
4. **低端机自动降 scale 到 2 或 3**（输出体积与内存都减半），提供设置项覆盖。
5. 若日后要出 iOS：本工程的 Toga 代码**可直接复用**（`pyproject.toml` 已留 iOS 段），
   唯一新增风险是 Pillow 的 iOS 轮子（BeeWare 同样维护）。

---

## 附：桌面版与移动端能力对照

| 能力 | 桌面 | Android | 备注 |
| --- | --- | --- | --- |
| 拖放文件 | ✅ | ➖ | 改为文件选择器 |
| 选 BP / RP 文件夹 | ✅ | ✅ | Toga `select_folder` → SAF |
| 整包批量出图 | ✅ | ✅ | 同一份 `RenderJob` 逻辑 |
| 压缩包（含双层） | ✅ | ✅ | 解到私有 `cache/work` |
| 补全原版资源 | ✅ | ✅ | `urllib` + INTERNET 权限 |
| 纯本地模式 | ✅ | ✅ | 选入原版包 zip 即自动开启 |
| 命令行 `--headless` | ✅ | ➖ | 手机上无意义，保留核心 `cli.py` 不动 |
| 打开输出文件夹 | ✅ | ➖ | 改为「分享」/「另存」 |

---

## 实测结论：Briefcase 路线在 Pillow 上走不通（2026-10-11 已实跑验证）

一路修到 Gradle 之后，构建在 `:app:installDebugPythonRequirements` 失败，日志：

```
Chaquopy: Installing for arm64-v8a
Looking in indexes: https://pypi.org/simple, https://chaquo.com/pypi-13.1
ERROR: Could not find a version that satisfies the requirement pillow (from versions: none)
```

进一步查 Chaquopy 的 Android 轮子仓库（BeeWare 维护的那份）：

```
https://chaquo.com/pypi-13.1/pillow/
  → 只有 Pillow-7.0.0-1-cp38-cp38-android_16_arm64_v8a.whl 等
```

即：**该仓库里的 Pillow 只有 Python 3.8 时代的 7.0.0**，而 Briefcase 0.4.5 的 Android 支持包用的是 3.13+，
版本对不上 → 无可用轮子。Pillow 7.0（2020）也不满足核心代码的 API（`ImageDraw.textbbox` 需要 ≥ 8.0）。

**因此 Briefcase + Toga 这条路的唯一阻塞点是 Pillow，且短期无法绕过**（自建 Android 轮子需要交叉编译
zlib/libjpeg/freetype/libpng，属于另一个量级的工程）。

### 修正后的推荐顺序

| 方案 | 可行性 | 说明 |
| --- | --- | --- |
| **A. Termux 直接跑桌面版核心** | ★★★★★（零改动） | Termux 里有现成的 `python-pillow`（Android 原生构建）；把仓库拷进 Termux，装 pillow，跑 `mcrender/cli.py` 或给 Toga/Tk 之外的最小脚本即可出图。**不是 APK，但今天就能用。** |
| **B. Kivy + Buildozer（Linux/WSL）** | ★★★★ | `python-for-android` 有官方 Pillow recipe；Windows 需 WSL。UI 用 `kivy_alt/main.py`。 |
| **C. Chaquopy 独立工程 + Python 3.8** | ★★ | 只有 cp38 的 Pillow 7.0，核心代码要降级适配（`textbbox` 等），不划算。 |
| **D. 自建 Pillow Android 轮子** | ★★ | 用 mobile-forge/Chaquopy 工具链交叉编译，1~2 小时机器时间 + 大量踩坑。 |
| **E. 去掉 Pillow（纯 Python PNG 编码）** | ★ | 核心有大量 Pillow 调用（缩放、alpha 合成、字体渲染），属于重写级别。 |

本工程里 `android/`、`kivy_alt/`、`platform/` 的代码**全部保留可用**：
换到方案 B 时 `platform/*` 与核心复用逻辑照旧，只把 `app.py` 的 Toga 部分换成 Kivy；换到方案 A 则一行都不用改。
