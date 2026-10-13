# 合成表生成器 · Android

把 Minecraft 基岩版附加包的配方渲染成**和游戏内界面一致**的 PNG 图片。

- **界面**：Kotlin + Jetpack Compose（Material 3），明暗主题，首次启动跟随系统、之后记住用户选择
- **渲染核心**：与桌面端**共用同一份** `mcrender/`（Python），经 Chaquopy 在应用内运行
- **文件访问**：系统 Storage Access Framework
  （`ACTION_OPEN_DOCUMENT` / `ACTION_OPEN_DOCUMENT_TREE`），tree URI 还原成真实路径，
  选中的文件先复制到应用私有目录再交给核心

## 构建

```bash
# 需要 Android SDK(platform 34 + build-tools 34)、JDK 17、Gradle 8.7
echo "sdk.dir=/path/to/android-sdk" > local.properties
gradle assembleRelease      # 输出 app/build/outputs/apk/release/
```

签名信息在 `app/build.gradle.kts`（`brr-release.jks`）。

## 目录

| 路径 | 说明 |
|---|---|
| `app/src/main/java/…/MainActivity.kt` | Compose 界面 |
| `app/src/main/java/…/Core.kt` | 主题、偏好记忆、SAF 文件访问 |
| `app/src/main/java/…/Py.kt` | Chaquopy 桥（只做参数传递） |
| `app/src/main/python/brr_core.py` | 核心适配层（不含生图逻辑） |
| `app/src/main/python/mcrender/` | **共用**的渲染核心（由同步脚本复制） |

`python/` 下的核心与素材由 `../sync_to_compose.py` 从 Kivy 版目录同步，保证两端一致。

## JVM 界面测试

```bash
gradle :app:testDebugUnitTest     # Robolectric 渲染 Compose 界面并断言控件
```
