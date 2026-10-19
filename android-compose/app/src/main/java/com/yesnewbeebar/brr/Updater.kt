package com.yesnewbeebar.brr

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import androidx.core.content.FileProvider
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.util.regex.Pattern

/**
 * 在线更新：读取 GitHub Release 的 latest，比较版本，下载 **.apk** 并调起安装。
 *
 * 与桌面端共用同一个仓库的 release，但**只认 .apk**：
 * 桌面端只认 .exe。两边绝不互下对方的文件（e.g. 手机下到 exe）。
 * 版本基准：桌面用 tag；手机用 APK 文件名里的版本（…-v1.0.1-Android.apk → 1.0.1）。
 */
object Updater {

    private const val REPO = "YesNewBeeBar/bedrock-recipe-renderer"
    private const val API_LATEST = "https://api.github.com/repos/$REPO/releases/latest"
    private const val UA = "brr-updater"

    data class Info(
        val latestTag: String,
        val version: String,
        val newer: Boolean,
        val apkName: String?,
        val apkUrl: String?,
        val size: Long,
    )

    private fun versionTuple(text: String?): List<Int> =
        Pattern.compile("\\d+").matcher(text ?: "").let { m ->
            buildList { while (m.find()) add(m.group().toInt()) }
        }.take(4).ifEmpty { listOf(0) }

    fun isNewer(latest: String?, current: String?): Boolean {
        val a = versionTuple(latest)
        val b = versionTuple(current)
        for (i in 0 until maxOf(a.size, b.size)) {
            val x = a.getOrElse(i) { 0 }
            val y = b.getOrElse(i) { 0 }
            if (x != y) return x > y
        }
        return false
    }

    /** 从 APK 文件名取版本：bedrock-recipe-renderer-v1.0.1-Android.apk → 1.0.1 */
    fun versionFromName(name: String?): String {
        val m = Pattern.compile("-v?(\\d+(?:\\.\\d+)+)-", Pattern.CASE_INSENSITIVE)
            .matcher(name ?: "")
        return if (m.find()) m.group(1) else ""
    }

    private fun getJson(url: String): JSONObject {
        val conn = URL(url).openConnection() as HttpURLConnection
        conn.connectTimeout = 20000
        conn.readTimeout = 20000
        conn.setRequestProperty("Accept", "application/vnd.github+json")
        conn.setRequestProperty("User-Agent", UA)
        return conn.inputStream.bufferedReader().use { JSONObject(it.readText()) }
    }

    /** 阻塞调用，请在 IO 线程执行。 */
    fun check(current: String): Info {
        val data = getJson(API_LATEST)
        val tag = data.optString("tag_name", "")
        val assets = data.optJSONArray("assets")
        var apkName: String? = null
        var apkUrl: String? = null
        var size = 0L
        if (assets != null) {
            for (i in 0 until assets.length()) {
                val a = assets.optJSONObject(i) ?: continue
                val name = a.optString("name", "")
                val lower = name.lowercase()
                // 只认 apk，明确排除 exe / zip
                if (!lower.endsWith(".apk")) continue
                if (lower.endsWith(".exe") || lower.endsWith(".zip")) continue
                apkName = name
                apkUrl = a.optString("browser_download_url", "")
                size = a.optLong("size", 0L)
                break
            }
        }
        // 手机端的"最新版本"优先取 APK 文件名里的版本；取不到才回退 tag
        val version = versionFromName(apkName).ifEmpty { tag }
        return Info(tag, version, isNewer(version, current), apkName, apkUrl, size)
    }

    /** 下载 APK 到私有目录；onProgress(done, total)。 */
    fun download(url: String, dest: File, onProgress: (Long, Long) -> Unit): File {
        dest.parentFile?.mkdirs()
        if (dest.exists()) dest.delete()
        val conn = URL(url).openConnection() as HttpURLConnection
        conn.connectTimeout = 30000
        conn.readTimeout = 30000
        conn.setRequestProperty("User-Agent", UA)
        val total = conn.contentLengthLong
        var done = 0L
        conn.inputStream.use { input ->
            dest.outputStream().use { out ->
                val buf = ByteArray(256 * 1024)
                while (true) {
                    val n = input.read(buf)
                    if (n <= 0) break
                    out.write(buf, 0, n)
                    done += n
                    onProgress(done, total)
                }
            }
        }
        return dest
    }

    /** 调起系统安装界面（需要 REQUEST_INSTALL_PACKAGES + FileProvider）。 */
    fun install(ctx: Context, apk: File): Boolean {
        val uri: Uri = FileProvider.getUriForFile(
            ctx, ctx.packageName + ".fileprovider", apk)
        val intent = Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(uri, "application/vnd.android.package-archive")
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        return try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O &&
                !ctx.packageManager.canRequestPackageInstalls()) {
                // 先让用户允许"安装未知应用"，再让用户重试
                ctx.startActivity(Intent(
                    android.provider.Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                    Uri.parse("package:${ctx.packageName}"))
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
                false
            } else {
                ctx.startActivity(intent)
                true
            }
        } catch (e: Exception) {
            false
        }
    }
}
