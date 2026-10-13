package com.yesnewbeebar.brr

import android.content.Context
import com.chaquo.python.PyObject
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform

/** Python 端的日志/进度回调（Chaquopy 会把 Kotlin 对象直接交给 Python 调用）。 */
class PyLogger(private val onLine: (String) -> Unit) {
    @Suppress("unused")
    fun log(text: String) = onLine(text)
}

/**
 * 渲染核心的桥。**生图逻辑全部在 Python 侧的 mcrender/ 里，这里只做参数传递**
 * （与 Kivy 版调用的是同一批函数：Assets / Renderer / collect / output_dir_for / taggif）。
 */
object Py {

    @Volatile private var started = false

    fun ensure(ctx: Context) {
        if (!started) {
            synchronized(this) {
                if (!started) {
                    if (!Python.isStarted()) Python.start(AndroidPlatform(ctx))
                    started = true
                }
            }
        }
    }

    private fun module(): PyObject {
        val py = Python.getInstance()
        return py.getModule("brr_core")
    }

    /**
     * 出一个包的全部配方。
     * @param bpPath 行为包真实路径；rpPath/vanilla 可为空；files 为已复制到私有目录的配方/压缩包
     * @return 生成的图片数量
     */
    fun render(
        ctx: Context,
        bpPath: String,
        rpPath: String,
        vanilla: String,
        files: List<String>,
        outDir: String,
        scale: Int,
        layout: String,
        shading: String,
        wikiIcons: String,
        localOnly: Boolean,
        logger: PyLogger,
        onProgress: (Int, Int) -> Unit,
    ): Int {
        ensure(ctx)
        val fn = module().get("render")
        val progress = object {
            @Suppress("unused")
            fun onProgress(done: Int, total: Int) = onProgress(done, total)
        }
        val res = fn.call(
            bpPath, rpPath, vanilla, files.toTypedArray(), outDir,
            scale, layout, shading, wikiIcons, localOnly, logger, progress,
            ctx.filesDir.absolutePath, ctx.getExternalFilesDir(null)?.absolutePath ?: ""
        )
        return res?.toJava(Int::class.java) ?: 0
    }

    /** 以「文件列表」（.mcaddon/.zip/配方 json）出图：解包在 Python 侧完成。 */
    fun renderFiles(
        ctx: Context,
        bpPath: String,
        rpPath: String,
        vanilla: String,
        files: List<String>,
        outDir: String,
        scale: Int,
        layout: String,
        shading: String,
        wikiIcons: String,
        localOnly: Boolean,
        logger: PyLogger,
        onProgress: (Int, Int) -> Unit,
    ): Int {
        ensure(ctx)
        val fn = module().get("render_files")
        val progress = object {
            @Suppress("unused")
            fun onProgress(done: Int, total: Int) = onProgress(done, total)
        }
        val res = fn.call(
            bpPath, rpPath, vanilla, files.toTypedArray(), outDir,
            scale, layout, shading, wikiIcons, localOnly, logger, progress,
            ctx.filesDir.absolutePath, ctx.getExternalFilesDir(null)?.absolutePath ?: ""
        )
        return res?.toJava(Int::class.java) ?: 0
    }

    /** 版本号，用于确认手机上跑的是哪一版。 */
    fun version(ctx: Context): String {
        ensure(ctx)
        return module().get("VERSION")?.toString() ?: "?"
    }
}
