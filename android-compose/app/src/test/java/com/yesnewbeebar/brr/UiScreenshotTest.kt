package com.yesnewbeebar.brr

import android.graphics.Bitmap
import android.graphics.Canvas
import androidx.activity.ComponentActivity
import androidx.compose.ui.platform.ComposeView
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import org.robolectric.shadows.ShadowLooper
import java.io.File

/**
 * 界面截图：**不走 compose-test 的等待机制**（Robolectric 下它会一直等"空闲"而超时），
 * 而是手动创建 ComposeView、挂到 Activity 上，然后把 View 直接画进 Bitmap 存成 PNG。
 *
 * 输出：app/build/ui-light.png / ui-dark.png（Windows 侧可直接打开）
 */
@RunWith(AndroidJUnit4::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [33], qualifiers = "w411dp-h891dp-xhdpi")
class UiScreenshotTest {

    private fun capture(dark: Boolean, name: String) {
        val activity = Robolectric.buildActivity(ComponentActivity::class.java).setup().get()
        val prefs = Prefs(activity.applicationContext)
        val view = ComposeView(activity).apply {
            setContent { BrrTheme(dark) { MainScreen(prefs, dark) { } } }
        }
        activity.setContentView(view)

        // 量一遍、布局一遍、把主线程消息跑干净，再绘制
        val w = if (view.width > 0) view.width else 1080
        val h = if (view.height > 0) view.height else 2000
        view.measure(
            android.view.View.MeasureSpec.makeMeasureSpec(w, android.view.View.MeasureSpec.EXACTLY),
            android.view.View.MeasureSpec.makeMeasureSpec(h, android.view.View.MeasureSpec.EXACTLY))
        view.layout(0, 0, w, h)
        ShadowLooper.idleMainLooper()

        val bmp = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888)
        bmp.eraseColor(if (dark) 0xFF14161A.toInt() else 0xFFFFFFFF.toInt())
        view.draw(Canvas(bmp))

        val f = File("build", name)
        f.parentFile?.mkdirs()
        f.outputStream().use { bmp.compress(Bitmap.CompressFormat.PNG, 100, it) }
        println("SHOT ${f.absolutePath} ${w}x${h}")
    }

    @Test
    fun light_screenshot() = capture(false, "ui-light.png")

    @Test
    fun dark_screenshot() = capture(true, "ui-dark.png")
}
