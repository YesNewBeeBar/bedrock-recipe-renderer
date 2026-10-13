package com.yesnewbeebar.brr

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File

class MainActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val prefs = Prefs(this)

        // 与旧版一致：启动即申请「所有文件访问」权限（拿不到也能用 SAF 选择器）
        FileAccess.allFilesIntent(this)?.let { runCatching { startActivity(it) } }

        setContent {
            var dark by remember { mutableStateOf(prefs.resolveDark(this)) }
            BrrTheme(dark) { MainScreen(prefs, dark) { dark = it } }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MainScreen(prefs: Prefs, dark: Boolean, onDark: (Boolean) -> Unit) {
    val ctx = LocalContext.current
    val scope = rememberCoroutineScope()

    var bp by remember { mutableStateOf(prefs.bp) }
    var rp by remember { mutableStateOf(prefs.rp) }
    var out by remember { mutableStateOf(prefs.out) }
    var vanilla by remember { mutableStateOf(prefs.vanilla) }
    var scale by remember { mutableStateOf(prefs.scale.toString()) }
    var layout by remember { mutableStateOf(prefs.layout) }
    var shade by remember { mutableStateOf(prefs.shade) }
    var wiki by remember { mutableStateOf(prefs.wikiIcons) }
    var localOnly by remember { mutableStateOf(prefs.localOnly) }

    var log by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    var progress by remember { mutableStateOf(0f) }

    fun say(line: String) { log = (log + "\n" + line).trim() }
    fun persist() {
        prefs.bp = bp; prefs.rp = rp; prefs.out = out; prefs.vanilla = vanilla
        prefs.scale = scale.toIntOrNull() ?: 4; prefs.layout = layout
        prefs.shade = shade; prefs.wikiIcons = wiki; prefs.localOnly = localOnly
    }

    var pendingSlot by remember { mutableStateOf("out") }

    // ---- SAF 选择器（与旧版同一套官方接口）
    val pickDir = rememberLauncherForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { res ->
        val uri: Uri? = res.data?.data
        if (res.resultCode == android.app.Activity.RESULT_OK && uri != null) {
            runCatching {
                ctx.contentResolver.takePersistableUriPermission(
                    uri, Intent.FLAG_GRANT_READ_URI_PERMISSION or
                            Intent.FLAG_GRANT_WRITE_URI_PERMISSION)
            }
            val path = FileAccess.treeToPath(uri)
            if (path.isNotEmpty()) {
                when (pendingSlot) {
                    "bp" -> bp = path
                    "rp" -> rp = path
                    else -> out = path
                }
                persist()
                say("已选目录：$path")
            } else {
                say("这个目录解析不出真实路径，换一个试试")
            }
        }
    }

    val pickFiles = rememberLauncherForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { res ->
        if (res.resultCode != android.app.Activity.RESULT_OK) return@rememberLauncherForActivityResult
        val data = res.data ?: return@rememberLauncherForActivityResult
        val uris = mutableListOf<Uri>()
        data.clipData?.let { c -> for (i in 0 until c.itemCount) uris += c.getItemAt(i).uri }
        if (uris.isEmpty()) data.data?.let { uris += it }
        val paths = uris.mapNotNull { u ->
            runCatching {
                ctx.contentResolver.takePersistableUriPermission(
                    u, Intent.FLAG_GRANT_READ_URI_PERMISSION)
            }
            runCatching { FileAccess.copyToPrivate(ctx, u) }.getOrNull()
        }
        if (paths.isNotEmpty()) {
            say("已选 ${paths.size} 个文件")
            startRenderFiles(ctx, prefs, paths, out, scale, layout, shade, wiki, localOnly,
                { l -> say(l) }, { p -> progress = p }, { b -> busy = b }, ::persist)
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("合成表生成器", fontWeight = FontWeight.SemiBold) },
                actions = {
                    Text(if (dark) "深色" else "浅色", fontSize = 13.sp)
                    Spacer(Modifier.width(6.dp))
                    Switch(checked = dark, onCheckedChange = {
                        onDark(it); prefs.themeDark = it
                    })
                    Spacer(Modifier.width(12.dp))
                }
            )
        }
    ) { pad ->
        Column(
            Modifier.padding(pad).fillMaxSize().padding(14.dp).verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            // 拖放/选择卡
            Card(shape = RoundedCornerShape(14.dp), modifier = Modifier.fillMaxWidth()) {
                Column(Modifier.padding(18.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                    Text("点这里选配方 / 压缩包", fontWeight = FontWeight.Medium)
                    Text("支持 .json / .mcaddon / .mcpack / .zip",
                        fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Spacer(Modifier.height(10.dp))
                    Button(onClick = { pickFiles.launch(FileAccess.filePickIntent()) }) {
                        Icon(Icons.Default.Add, null); Spacer(Modifier.width(6.dp))
                        Text("选择文件")
                    }
                }
            }

            // 路径卡
            Card(shape = RoundedCornerShape(14.dp), modifier = Modifier.fillMaxWidth()) {
                Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    PathRow("行为包 BP", bp) { pendingSlot = "bp"; pickDir.launch(FileAccess.dirPickIntent()) }
                    PathRow("资源包 RP", rp) { pendingSlot = "rp"; pickDir.launch(FileAccess.dirPickIntent()) }
                    PathRow("出图目录", out) { pendingSlot = "out"; pickDir.launch(FileAccess.dirPickIntent()) }
                    Text(
                        if (out.isBlank()) "图片会放在所选目录下的「合成表」里"
                        else "图片会放在：$out/合成表",
                        fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }

            // 参数卡
            Card(shape = RoundedCornerShape(14.dp), modifier = Modifier.fillMaxWidth()) {
                Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text("缩放", fontSize = 13.sp); Spacer(Modifier.width(8.dp))
                        Dropdown(listOf("2", "3", "4", "6", "8"), scale) { scale = it; persist() }
                        Spacer(Modifier.width(14.dp))
                        Text("版式", fontSize = 13.sp); Spacer(Modifier.width(8.dp))
                        Dropdown(listOf("modern", "classic"), layout) { layout = it; persist() }
                    }
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text("方块阴影", fontSize = 13.sp); Spacer(Modifier.width(8.dp))
                        Dropdown(listOf("vanilla", "reference"), shade) { shade = it; persist() }
                        Spacer(Modifier.width(14.dp))
                        Text("wiki 图标", fontSize = 13.sp); Spacer(Modifier.width(8.dp))
                        Dropdown(listOf("auto", "always", "never"), wiki) { wiki = it; persist() }
                    }
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text("只用本地（不联网）", fontSize = 13.sp)
                        Spacer(Modifier.weight(1f))
                        Switch(checked = localOnly, onCheckedChange = { localOnly = it; persist() })
                    }
                }
            }

            Button(
                onClick = {
                    if (bp.isBlank()) { say("请先选「行为包 BP」"); return@Button }
                    if (out.isBlank()) { say("请先选「出图目录」"); return@Button }
                    startRender(ctx, prefs, listOf(bp), out, scale, layout, shade, wiki,
                        localOnly, { l -> say(l) }, { p -> progress = p },
                        { b -> busy = b }, ::persist)
                },
                enabled = !busy,
                modifier = Modifier.fillMaxWidth().height(50.dp),
                shape = RoundedCornerShape(12.dp)
            ) {
                Icon(Icons.Default.PlayArrow, null); Spacer(Modifier.width(6.dp))
                Text(if (busy) "正在出图…" else "开始出图（当前 BP 的全部配方）")
            }

            if (busy || progress > 0f) {
                LinearProgressIndicator(progress = { progress }, modifier = Modifier.fillMaxWidth())
            }

            OutlinedButton(onClick = {
                val dir = File(out, "合成表")
                if (dir.isDirectory) say("输出目录：${dir.absolutePath}") else say("还没有出图结果")
            }, modifier = Modifier.fillMaxWidth()) { Text("查看输出位置") }

            Card(shape = RoundedCornerShape(14.dp), modifier = Modifier.fillMaxWidth()) {
                Text(
                    log.ifBlank { "日志会显示在这里" },
                    Modifier.padding(12.dp).heightIn(min = 160.dp),
                    fontSize = 12.sp
                )
            }
        }
    }
}

@Composable
private fun PathRow(label: String, value: String, onPick: () -> Unit) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Text(label, fontSize = 13.sp, modifier = Modifier.width(72.dp))
        Text(
            value.ifBlank { "（未选择）" },
            fontSize = 12.sp, maxLines = 1,
            color = if (value.isBlank()) MaterialTheme.colorScheme.onSurfaceVariant
            else MaterialTheme.colorScheme.onSurface,
            modifier = Modifier.weight(1f)
        )
        TextButton(onClick = onPick) { Text("选择…") }
    }
}

@Composable
private fun Dropdown(items: List<String>, value: String, onChange: (String) -> Unit) {
    var open by remember { mutableStateOf(false) }
    Box {
        OutlinedButton(onClick = { open = true }, shape = RoundedCornerShape(10.dp)) {
            Text(value, fontSize = 13.sp)
            Icon(Icons.Default.ArrowDropDown, null)
        }
        DropdownMenu(expanded = open, onDismissRequest = { open = false }) {
            items.forEach { item ->
                DropdownMenuItem(text = { Text(item) }, onClick = { onChange(item); open = false })
            }
        }
    }
}

/** 在后台线程调用 Python 核心出图（生图逻辑全在 Python 侧）。 */
private fun startRender(
    ctx: android.content.Context, prefs: Prefs, bpDirs: List<String>, out: String,
    scale: String, layout: String, shade: String, wiki: String, localOnly: Boolean,
    log: (String) -> Unit, progress: (Float) -> Unit, busy: (Boolean) -> Unit,
    persist: () -> Unit,
) {
    persist()
    busy(true)
    Thread {
        try {
            val bp = bpDirs.firstOrNull() ?: prefs.bp
            val total = { d: Int, t: Int -> progress(if (t > 0) d.toFloat() / t else 0f) }
            val n = Py.render(
                ctx, bp, prefs.rp, prefs.vanilla, bpDirs, out,
                scale.toIntOrNull() ?: 4, layout, shade, wiki, localOnly,
                PyLogger { line -> log(line) },
                { d, t -> total(d, t) }
            )
            log("本次共生成 $n 张")
        } catch (e: Throwable) {
            log("!! 出图异常：${e.message}")
        } finally {
            busy(false)
        }
    }.start()
}


/** 以「文件（压缩包/配方 json）」出图：解包交给 Python 侧，与旧版行为一致。 */
private fun startRenderFiles(
    ctx: android.content.Context, prefs: Prefs, files: List<String>, out: String,
    scale: String, layout: String, shade: String, wiki: String, localOnly: Boolean,
    log: (String) -> Unit, progress: (Float) -> Unit, busy: (Boolean) -> Unit,
    persist: () -> Unit,
) {
    persist(); busy(true)
    Thread {
        try {
            val n = Py.renderFiles(
                ctx, prefs.bp, prefs.rp, prefs.vanilla, files, out,
                scale.toIntOrNull() ?: 4, layout, shade, wiki, localOnly,
                PyLogger { log(it) }, { d, t -> progress(if (t > 0) d.toFloat() / t else 0f) })
            log("本次共生成 $n 张")
        } catch (e: Throwable) {
            log("!! 出图异常：${e.message}")
        } finally { busy(false) }
    }.start()
}
