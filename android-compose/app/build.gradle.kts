plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("com.chaquo.python")
}

android {
    namespace = "com.yesnewbeebar.brr"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.yesnewbeebar.brr"
        minSdk = 24
        targetSdk = 34
        versionCode = 1
        versionName = "1.0.0"

        // Chaquopy：只打 arm64，包小一半；Python 核心通过它运行
        ndk { abiFilters += listOf("arm64-v8a") }
    }

    signingConfigs {
        create("release") {
            storeFile = file("../brr-release.jks")
            storePassword = "brr-release"
            keyAlias = "brr"
            keyPassword = "brr-release"
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.getByName("release")
        }
        debug {
            isMinifyEnabled = false
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }

    buildFeatures { compose = true }
    testOptions {
        unitTests {
            isIncludeAndroidResources = true
            all { it.systemProperty("robolectric.graphicsMode", "NATIVE") }
        }
    }
    composeOptions { kotlinCompilerExtensionVersion = "1.5.14" }

    // Python 源码目录：brr_core.py + 原样复制过来的 mcrender/ 核心
    sourceSets {
        getByName("main") {
            java.srcDirs("src/main/java")
        }
    }

    packaging {
        resources.excludes += setOf(
            "META-INF/DEPENDENCIES", "META-INF/LICENSE*", "META-INF/NOTICE*"
        )
    }
}

chaquopy {
    defaultConfig {
        version = "3.8"              // Chaquopy 对 3.8 的预编译轮子覆盖最全（Pillow 等）
        pip {
            // 核心只依赖 Pillow（渲染用）与 requests（可选联网取图标）
            install("Pillow")            // 不钉版本：让 Chaquopy 选它自带轮子的版本
            install("requests")            // 纯 Python，联网补齐纹理用
        }
    }
    sourceSets {
        getByName("main") {
            srcDir("src/main/python")
        }
    }
}

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2024.06.00")
    implementation(composeBom)
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.activity:activity-compose:1.9.0")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    implementation("androidx.documentfile:documentfile:1.0.1")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.8.0")
    debugImplementation("androidx.compose.ui:ui-tooling")

    // JVM 上真实渲染 Compose 并截图（无需设备）—— 用来做界面验收
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.robolectric:robolectric:4.12.2")
    testImplementation("androidx.compose.ui:ui-test-junit4")
    testImplementation("androidx.test.ext:junit:1.1.5")
    debugImplementation("androidx.compose.ui:ui-test-manifest")
}
