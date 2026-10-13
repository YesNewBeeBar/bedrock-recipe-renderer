package com.yesnewbeebar.brr

import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

/**
 * 无真机验收：JVM 上真实渲染 Compose 界面并断言关键控件存在。
 * （截图落盘需要处理 Robolectric 下的空闲同步，另行补；此测试用于确认界面不崩且控件齐全。）
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

    @Test
    fun light_ui_renders() {
        render(false)
        compose.onNodeWithText("合成表生成器").assertIsDisplayed()
        compose.onNodeWithText("选择文件").assertIsDisplayed()
        compose.onNodeWithText("行为包 BP").assertIsDisplayed()
        compose.onNodeWithText("资源包 RP").assertIsDisplayed()
        compose.onNodeWithText("出图目录").assertIsDisplayed()
        compose.onNodeWithText("缩放").assertIsDisplayed()
        compose.onNodeWithText("只用本地（不联网）").assertIsDisplayed()
        compose.onNodeWithText("开始出图（当前 BP 的全部配方）").assertIsDisplayed()
    }
}
