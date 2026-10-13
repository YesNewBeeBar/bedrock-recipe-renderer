package com.yesnewbeebar.brr

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.content.res.Configuration
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.provider.OpenableColumns
import androidx.activity.result.ActivityResultLauncher
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import org.json.JSONObject
import java.io.File

// ---------------------------------------------------------------- 记忆（与旧版同一份语义）
/**
 * 记住用户的选择：出图目录、BP/RP、原版包、参数、主题。
 * 主题规则与桌面端一致：**只有第一次**跟随设备，之后一律用用户自己的选择。
 */
class Prefs(ctx: Context) {
    private val sp = ctx.getSharedPreferences("brr", Context.MODE_PRIVATE)

    var out: String
        get() = sp.getString("out", "") ?: ""
        set(v) = sp.edit().putString("out", v).apply()
    var bp: String
        get() = sp.getString("bp", "") ?: ""
        set(v) = sp.edit().putString("bp", v).apply()
    var rp: String
        get() = sp.getString("rp", "") ?: ""
        set(v) = sp.edit().putString("rp", v).apply()
    var vanilla: String
        get() = sp.getString("vanilla", "") ?: ""
        set(v) = sp.edit().putString("vanilla", v).apply()

    var scale: Int
        get() = sp.getInt("scale", 4)
        set(v) = sp.edit().putInt("scale", v).apply()
    var layout: String
        get() = sp.getString("layout", "modern") ?: "modern"
        set(v) = sp.edit().putString("layout", v).apply()
    var shade: String
        get() = sp.getString("shade", "vanilla") ?: "vanilla"
        set(v) = sp.edit().putString("shade", v).apply()
    var wikiIcons: String
        get() = sp.getString("wiki", "auto") ?: "auto"
        set(v) = sp.edit().putString("wiki", v).apply()
    var localOnly: Boolean
        get() = sp.getBoolean("local_only", true)
        set(v) = sp.edit().putBoolean("local_only", v).apply()

    /** 主题：null = 还没选过（首次），此时跟随设备。 */
    var themeDark: Boolean?
        get() = if (sp.contains("theme_dark")) sp.getBoolean("theme_dark", false) else null
        set(v) = sp.edit().putBoolean("theme_dark", v ?: false).apply()

    fun resolveDark(ctx: Context): Boolean {
        themeDark?.let { return it }
        val night = (ctx.resources.configuration.uiMode and
                Configuration.UI_MODE_NIGHT_MASK) == Configuration.UI_MODE_NIGHT_YES
        themeDark = night          // 写回：以后都尊重它
        return night
    }
}

// ---------------------------------------------------------------- 主题
private val LightColors = lightColorScheme(
    primary = Color(0xFF2F7CF6), onPrimary = Color.White,
    surface = Color(0xFFFFFBFE), background = Color(0xFFF7F7FA),
    surfaceVariant = Color(0xFFEDEEF2), onSurface = Color(0xFF111318),
)
private val DarkColors = darkColorScheme(
    primary = Color(0xFF4F8DF7), onPrimary = Color.White,
    surface = Color(0xFF1B1D21), background = Color(0xFF14161A),
    surfaceVariant = Color(0xFF26292F), onSurface = Color(0xFFECEEF2),
)

@Composable
fun BrrTheme(dark: Boolean, content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = if (dark) DarkColors else LightColors, content = content)
}

// ---------------------------------------------------------------- 文件访问（沿用旧版机制）
/**
 * SAF 文件/目录选择：与 Kivy 版用的是同一套官方接口与同一条路径解析逻辑
 * （ACTION_OPEN_DOCUMENT / ACTION_OPEN_DOCUMENT_TREE + 可持久化授权 + tree→真实路径）。
 * 核心只认普通文件路径，所以选中的 URI 会先复制进应用私有目录。
 */
object FileAccess {

    fun filePickIntent(multiple: Boolean = true): Intent {
        val i = Intent(if (multiple) Intent.ACTION_OPEN_DOCUMENT else Intent.ACTION_OPEN_DOCUMENT)
        i.addCategory(Intent.CATEGORY_OPENABLE)
        i.type = "*/*"
        i.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, multiple)
        i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or
                Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION)
        return i
    }

    fun dirPickIntent(): Intent {
        val i = Intent(Intent.ACTION_OPEN_DOCUMENT_TREE)
        i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or
                Intent.FLAG_GRANT_WRITE_URI_PERMISSION or
                Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION)
        return i
    }

    /** tree URI → 真实路径（primary:Download → /storage/emulated/0/Download）。 */
    fun treeToPath(uri: Uri): String {
        val doc = uri.lastPathSegment ?: return ""
        val idx = doc.indexOf(':')
        if (idx < 0) return ""
        val volume = doc.substring(0, idx)
        val rel = doc.substring(idx + 1)
        val base = if (volume.equals("primary", true)) {
            Environment.getExternalStorageDirectory().absolutePath
        } else {
            "/storage/$volume"
        }
        return if (rel.isEmpty()) base else "$base/$rel"
    }

    /** 把 content:// 复制到私有目录，返回真实路径（核心只吃真实路径）。 */
    fun copyToPrivate(ctx: Context, uri: Uri): String {
        val name = displayName(ctx, uri) ?: "picked"
        val dest = File(ctx.filesDir, "picked").apply { mkdirs() }
        val target = File(dest, name)
        ctx.contentResolver.openInputStream(uri)?.use { input ->
            target.outputStream().use { output -> input.copyTo(output) }
        }
        return target.absolutePath
    }

    fun displayName(ctx: Context, uri: Uri): String? {
        ctx.contentResolver.query(uri, null, null, null, null)?.use { c ->
            if (c.moveToFirst()) {
                val i = c.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                if (i >= 0) return c.getString(i)
            }
        }
        return uri.lastPathSegment
    }

    /** 申请「所有文件访问」权限页（与旧版一致：启动时自动弹）。 */
    fun allFilesIntent(ctx: Context): Intent? {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.R) return null
        if (Environment.isExternalStorageManager()) return null
        return Intent(android.provider.Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION,
            Uri.parse("package:${ctx.packageName}"))
    }
}
