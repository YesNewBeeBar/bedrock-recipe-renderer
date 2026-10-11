# 环境安装：从零到能跑 `briefcase run android`

> 官方依据：<https://briefcase.beeware.org/en/v0.3.17/reference/platforms/android/gradle.html>
> 关键结论：**Gradle 需要 Android SDK + Java 17 JDK**；两者缺失时
> **Briefcase 会自己下载一份隔离副本**装到它的数据目录，所以"什么都不装"也能跑起来
> （只是首次要下几 GB，国内网络可能很慢）。

## 1. 安装 Briefcase（本机 Python 3.14）

```powershell
# 推荐：单独建一个虚拟环境，不污染系统 Python
cd D:\合成表生成器移动端
C:\Python314\python.exe -m venv .venv-briefcase
.\.venv-briefcase\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install briefcase
briefcase --version
```

> 若 Python 3.14 上 `pip install briefcase` 有依赖装不上（3.14 很新），
> 换个 3.12/3.13 的 venv 即可 —— **宿主 Python 版本不影响 APK 里的运行版本**，
> App 用的是 Briefcase 自带的 Python-Android 支持包。

## 2. Java 17（推荐自己装，别等自动下载）

```powershell
winget install Microsoft.OpenJDK.17
# 装完设置 JAVA_HOME（把路径换成实际安装目录）
setx JAVA_HOME "C:\Program Files\Microsoft\jdk-17.0.13.11-hotspot"
setx PATH "$env:JAVA_HOME\bin;$env:PATH"
# 重开一个终端验证
java -version        # 必须 17 或更高
```

## 3. Android SDK（二选一）

**方式 A：装 Android Studio（国内最省事，可配镜像）**

1. 装 Android Studio → SDK Manager → 勾选：
   - **SDK Platform**（API 34 或更高）
   - **Android SDK Command-line Tools 9.0**（Briefcase **强制要求**这个版本）
   - **NDK**（Side-by-side）
2. 设环境变量（Briefcase 会优先用它）：
   ```powershell
   setx ANDROID_HOME "$env:LOCALAPPDATA\Android\Sdk"
   ```

**方式 B：让 Briefcase 自己下**（什么都不配）

```powershell
briefcase create android     # 首次会提示下载 SDK/JDK/Gradle，几个 GB
```

## 4. 自检（最重要的一步）

```powershell
briefcase doctor
```

它会逐项报告：Java / Android SDK / 设备连接 / 模拟器 —— **缺什么、什么版本不对，一目了然**。

## 5. 建工程并跑起来

```powershell
cd D:\合成表生成器移动端
python sync_core.py                 # 同步核心 + 生成 Android 图标
cd android
briefcase create android            # 生成 Gradle 工程（首次 10~20 分钟）
briefcase build android
briefcase run android               # 手机需开 USB 调试；或按提示建模拟器
briefcase run android --log         # 直接看 Python traceback
```

## 6. 关于 Pillow（唯一的风险点）

Briefcase 用 **Chaquopy 的二级仓库**（`https://chaquo.com/pypi-13.1/`，由 BeeWare 维护）
提供预编译的 Android 轮子。所以 `requires = ["pillow"]` 有可能直接可用。

如果构建时报下面任意一种，就说明这个包（或这个版本）没有 Android 轮子：

- `Chaquopy cannot compile native code`
- 日志里出现下载 `.tar.gz`
- 日志里出现 `Building wheels for collected packages: pillow`

**应对顺序**：① 降 Pillow 版本再试（`requires = ["pillow<11"]`）；
② 换 `kivy_alt/`（python-for-android 自带 Pillow recipe）；
③ 用 Chaquopy 独立工程（Android Studio 里 `install "com.chaquo.python:pypi:pillow"`）。

## 7. 常见坑

| 现象 | 原因 / 处理 |
| --- | --- |
| `briefcase doctor` 说找不到 Java | `JAVA_HOME` 没设或不是 17+ |
| 用了现有 SDK 但报 Command-line Tools | 必须是 **9.0**，在 SDK Manager 里勾 |
| 国内下载 SDK/Gradle 极慢或失败 | 用 Android Studio 装 SDK + 设 `ANDROID_HOME`；Gradle 可配阿里云镜像 |
| WSL 里执行 `briefcase create android` | Android 构建**不支持 WSL**，必须在原生 Windows 里跑 |
| 磁盘告警 | SDK + NDK + 模拟器约 10 GB+ |
| Buildozer（Kivy 路线）在 Windows 上装不上 | Buildozer **只支持 Linux/macOS**，Windows 需 WSL —— 所以本机首选是 Briefcase |

---

## 本机安装实录（2026-10-11，已由我完成的部分）

| 步骤 | 状态 | 位置 / 版本 |
| --- | --- | --- |
| briefcase | ✅ 0.4.5 | `D:\android-toolchain\venv` |
| Temurin JDK 17 | ✅ 17.0.20.1 | `D:\android-toolchain\jdk17` |
| Android SDK 许可 | ✅ 已全部接受 | `D:\android-toolchain\sdk\licenses` |
| platform-tools / android-34 / build-tools 34.0.0 / NDK 26.1 | ✅ | `D:\android-toolchain\sdk` |
| `briefcase create android` | ✅ 成功，Gradle 工程已生成 | `android\build\bedrock_recipe_renderer\android\gradle` |
| `briefcase build android` | ❌ 卡在下载 Gradle 发行包 | `services.gradle.org` 连接超时 |

### 两个已确认的本机环境坑（都已绕过或记录）

1. **curl 不可用**：`schannel: CRYPT_E_NO_REVOCATION_CHECK` → 一律改用
   `android_download.py`（Python + 伪造 UA；注意 Adoptium 无 UA 会直接 403）。
2. **Java 默认信任库缺 CA**：Gradle wrapper 报 `PKIX path building failed`
   → 加 `JAVA_OPTS=-Djavax.net.ssl.trustStoreType=WINDOWS-ROOT` 可解决（已验证：证书错误消失）。
3. **Gradle 发行包下载超时**（当前唯一阻塞点）：`services.gradle.org` 国内不可达。
   解决办法（任选）：
   - 先把 Gradle 包用 Python 下到 wrapper 缓存：
     `gradle-9.5.0-bin.zip` → `%USERPROFILE%\.gradle\wrapper\dists\gradle-9.5.0-bin\<hash>\`
     （`<hash>` = URL 的 MD5 转 base36，可用 `gradle-wrapper.properties` 里的 URL 算出）
   - 或把 `build\bedrock_recipe_renderer\android\gradle\gradle\wrapper\gradle-wrapper.properties`
     里的 `distributionUrl` 改成国内镜像（如 `https://mirrors.cloud.tencent.com/gradle/gradle-9.5.0-bin.zip`），
     然后在 `build\...\gradle` 目录里直接跑 `gradlew.bat assembleDebug`，
     **不经过 briefcase build**（同样能出 APK）。

### 之后的命令（在新终端里）

```powershell
$env:JAVA_HOME='D:\android-toolchain\jdk17'
$env:ANDROID_HOME='D:\android-toolchain\sdk'
$env:JAVA_OPTS='-Djavax.net.ssl.trustStoreType=WINDOWS-ROOT'
$env:PATH="$env:JAVA_HOME\bin;$env:PATH"
cd D:\合成表生成器移动端\android
D:\android-toolchain\venv\Scripts\briefcase.exe build android
```

**Pillow 的判定点**：`build` 阶段 Gradle 会调 Chaquopy 的 pip 去装 `pillow`。
若日志出现 `Chaquopy cannot compile native code` / 下载 `.tar.gz` / `Building wheels for collected packages: pillow`，
就说明没有 Android 轮子 → 按第六节切 `kivy_alt/` 或 Chaquopy 独立工程。
