package com.yesnewbeebar.brr

import android.graphics.Bitmap
import androidx.compose.ui.graphics.asAndroidBitmap
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.captureToImage
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.onRoot
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import java.io.File

/**
 * 无真机验收：在 JVM 上用 Robolectric 真实渲染 Compose 界面并**截图落盘**。
 *
 * 关键点：先关掉测试时钟的自动推进（mainClock.autoAdvance = false）再手动推进，
 * 否则 captureToImage() 会一直等"合成器空闲"而超时。
 * 截图写到项目内的 build/ui-*.png，Windows 侧可直接打开。
 */
@RunWith(AndroidJUnit4::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [33], qualifiers = "w411dp-h891dp-xhdpi")
class MainScreenRenderTest {

    @get:Rule
    val compose = createComposeRule()

    private fun render(dark: Boolean) {
        compose.setContent {
            val ctx = LocalContext.current
            val prefs = Prefs(ctx.applicationContext)
            BrrTheme(dark) { MainScreen(prefs, dark) { } }
        }
    }

    private fun shoot(name: String) {
        compose.mainClock.autoAdvance = false   // 只在截图这一刻暂停时钟
        val bmp = compose.onRoot().captureToImage().asAndroidBitmap()
        val f = File("build", name)
        f.parentFile?.mkdirs()
        f.outputStream().use { bmp.compress(Bitmap.CompressFormat.PNG, 100, it) }
        println("SHOT ${f.absolutePath} ${bmp.width}x${bmp.height}")
    }

    @Test
    fun light_ui_renders_and_captures() {
        render(false)
        compose.onNodeWithText("合成表生成器").assertIsDisplayed()
        compose.onNodeWithText("选择文件").assertIsDisplayed()
        compose.onNodeWithText("行为包 BP").assertIsDisplayed()
        compose.onNodeWithText("资源包 RP").assertIsDisplayed()
        compose.onNodeWithText("出图目录").assertIsDisplayed()
        compose.onNodeWithText("缩放").assertIsDisplayed()
        compose.onNodeWithText("只用本地（不联网）").assertIsDisplayed()
        compose.onNodeWithText("开始出图（当前 BP 的全部配方）").assertIsDisplayed()
        shoot("ui-light.png")
    }

    @Test
    fun dark_ui_renders_and_captures() {
        render(true)
        compose.onNodeWithText("合成表生成器").assertIsDisplayed()
        compose.onNodeWithText("开始出图（当前 BP 的全部配方）").assertIsDisplayed()
        shoot("ui-dark.png")
    }
}
