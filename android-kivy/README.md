# 路线 B：Kivy + Buildozer → 真正的 Android APK

**选它的唯一理由**：`python-for-android` 有**官方维护的 Pillow recipe**，
而 Briefcase/Chaquopy 的 Android 轮子仓库里只有 Pillow 7.0.0（cp38）→ 走不通（已实跑验证，见 [../PORTING.md](../PORTING.md) 末尾）。

## 为什么需要 WSL

**Buildozer 只支持 Linux/macOS**，Windows 必须经 WSL2。
你这台机器 **WSL 尚未安装**，安装需要管理员权限（我无法代点 UAC），所以要你执行一次：

```powershell
# 管理员 PowerShell，执行一次，然后重启
wsl --install -d Ubuntu
```

装完在 Ubuntu 里设好用户名密码即可（后续脚本会用 `sudo`）。

## 构建（两条命令）

```powershell
cd D:\合成表生成器移动端\android-kivy
pwsh -File build_apk_wsl.ps1            # 首次会自动装依赖并构建，30~60 分钟
pwsh -File build_apk_wsl.ps1 -Clean     # 需要重来时
```

脚本做的事：检查 WSL → 换算路径 → `setup_wsl_buildozer.sh`（装 openjdk-17 / buildozer / 依赖）
→ `buildozer -v android debug` → 把 `bin/*.apk` 列出来。

**产物**：`android-kivy\bin\bedrockreciperenderer-1.0.0-...-debug.apk`
传到手机安装（需允许"未知来源"）。

也可以在 WSL 里手动跑：

```bash
cd /mnt/d/合成表生成器移动端/android-kivy
bash setup_wsl_buildozer.sh
. .venv-buildozer/bin/activate
buildozer -v android debug 2>&1 | tee build.log     # 出问题看这个日志
```

## 工程结构

```
android-kivy/
├─ main.py                     Kivy 界面（替代 Tkinter/Toga）
├─ buildozer.spec              requirements = python3,kivy,pillow,certifi,plyer,android
├─ platform_layer/
│   ├─ paths.py                Android 私有目录 / .devdata（开发时）
│   ├─ fonts.py                探测 /system/fonts 的 CJK 字体 → 注入核心
│   ├─ net.py                  certifi + TLS
│   ├─ picking.py              SAF 选文件（plyer → jnius 逐级回退）+ content:// 落本地
│   └─ storage.py              打包 ZIP（写到 /sdcard/Android/data/<pkg>/files）+ 系统分享
├─ mcrender/                   ← sync_core.py 生成的核心副本（勿手改）
├─ assets/                     内置 UI 贴图 + 裁剪面板
└─ icon.png
```

## 与桌面版的对应关系

| 桌面 | Kivy 版 |
| --- | --- |
| 拖放 | SAF 选择器（`picking.pick_files`） |
| 选 BP/RP 目录 | 选目录里的 `manifest.json`，取其父目录（Android 无通用目录选择） |
| 打开输出文件夹 | 输出到私有目录 → 「导出 ZIP」→ 写到外部私有目录 + 系统分享 |
| `--headless` | 无（手机无意义）；核心 `cli.py` 保留可用 |

## 已知注意点

1. **中文路径**：桌面把工程放在 `D:\合成表生成器移动端\`，但 Buildozer 在 **WSL 内部**构建，
   `source.dir = .` 会把中文路径带给 NDK 工具链；若日志出现路径相关报错，把工程复制到
   `~/brr`（纯 ASCII）再构建即可。
2. **首次构建下载量**：SDK + NDK + Python-Android 轮子 ≈ 2~4 GB。脚本里已把 pip 指向清华源。
3. **`plyer`**：若你的 p4a 版本里 plyer 的 filechooser 不正常，`picking.py` 会自动退回 jnius 的
   `ACTION_OPEN_DOCUMENT`（两条路都实现了）。
4. **Pillow 版本**：p4a 的 recipe 自带一个能编过的版本；若构建报错，在 `buildozer.spec` 里把
   `pillow` 写成具体版本（如 `pillow==10.4.0`）再试。
