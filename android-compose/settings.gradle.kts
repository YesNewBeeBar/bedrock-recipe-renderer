// 合成表生成器 · Android 原生版（Kotlin + Jetpack Compose + Chaquopy）
// Python 渲染核心 mcrender/ 原样复用，界面与文件访问用原生实现。
pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}
dependencyResolutionManagement {
    repositories {
        google()
        mavenCentral()
    }
}
rootProject.name = "合成表生成器"
include(":app")
