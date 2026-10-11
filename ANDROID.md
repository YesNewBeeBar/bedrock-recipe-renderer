# Android 移植工程（合成表生成器移动端）

把 <https://github.com/YesNewBeeBar/bedrock-recipe-renderer> 从 Windows 桌面端（Tkinter + Pillow）
移植到 Android。**核心渲染逻辑零改动复用**，只重写 GUI 层。

> 完整方案（可行性 / 分层 / 分阶段步骤 / 代码 / 权限 / Pillow / 打包 / 风险）见 **[PORTING.md](PORTING.md)**。

## 结论速览

| 检查项 | 实测 |
| --- | --- |
| 核心模块导入 | 全部相对导入（`from . import …`），整包可直接塞进 APK |
| 核心代码量 | `mcrender/` ≈ 3900 行纯 Python + Pillow |
| 平台相关代码 | 全仓库**只有 1 行**：`fonts.py` 的 Windows 字体路径（运行期替换即可） |
| Tkinter | 只存在于 `mcrender_gui.py` → 只有这一层需要重写 |
| 唯一真风险 | **Pillow 的 Android 轮子**（详见 PORTING.md 第六节） |

## 目录

```
sync_core.py                 桌面核心 → android/src/bedrock_recipe_renderer/mcrender/
android/                     BeeWare + Briefcase 工程（首选）
  pyproject.toml             含 Android/iOS/桌面配置与权限
  src/bedrock_recipe_renderer/
    app.py                   ★ Toga 界面（替代 mcrender_gui.py）
    platform/                ★ 平台适配层：paths / picker / fonts / storage / net
    mcrender/                ★ 核心（sync_core.py 生成，勿手改）
    assets/                  内置 UI 贴图 + 裁剪面板
    resources/icon.png       应用图标
kivy_alt/                    路线 A：Kivy + Buildozer（Pillow recipe 最稳）
experiments/probe_android.py 阶段 0 探针：Pillow / 字体 / 网络 / 目录
```

## 快速开始

```bash
# 1) 同步核心（桌面版是唯一实现，移动端只保留副本）
python sync_core.py
python sync_core.py --check        # 校验没有漂移

# 2) 构建（首次会下 Gradle + Android SDK，10~20 分钟）
pip install briefcase
cd android
briefcase create android
briefcase build android
briefcase run android              # 装到手机上运行
briefcase run android --log        # 看 Python traceback

# 3) 打包签名 APK / AAB
briefcase package android --packagename com.yesnewbeebar.brr --signing-mode release
```

**先跑阶段 0 探针再决定路线**：探针里 Pillow 那项失败，就改用 `kivy_alt/`
（`buildozer -v android debug`），同一份核心代码不用动。

## 三条路线的取舍

| 路线 | Pillow | UI 成本 | 说明 |
| --- | --- | --- | --- |
| **B. BeeWare + Briefcase**（本工程） | 需验证 | 低（Toga 代码最干净） | 需 mobile-forge 的 Android 轮子 |
| **A. Kivy + Buildozer**（`kivy_alt/`） | 官方 recipe，最稳 | 低 | 保底方案 |
| **C. Chaquopy + 原生壳** | 官方轮子 | 高（要 Android Studio） | UI 想用原生时选它 |

## 与桌面版的差异

| 能力 | 桌面 | Android |
| --- | --- | --- |
| 拖放 | ✅ | ➖ 改为文件选择器（SAF） |
| 选 BP/RP 文件夹 | ✅ | ✅ `select_folder` |
| 批量出图 / 压缩包（含双层） | ✅ | ✅ |
| 补全原版资源 / 纯本地模式 | ✅ | ✅（建议先用 SAF 选入原版包 zip → 立即离线） |
| 打开输出文件夹 | ✅ | ➖ 改为「导出 ZIP / 分享」 |
| `--headless` 命令行 | ✅ | ➖ 手机无意义（核心 `cli.py` 保留不动） |

## 注意

- **不要手改** `android/src/bedrock_recipe_renderer/mcrender/`：它是 `sync_core.py` 生成的副本，
  改核心请改仓库根的 `mcrender/`，再同步过来。
- 本工程的 `android/`、`kivy_alt/`、`experiments/`、`sync_core.py`、`PORTING.md`、`ANDROID.md`
  都是新增文件，桌面端源码未做任何修改。
