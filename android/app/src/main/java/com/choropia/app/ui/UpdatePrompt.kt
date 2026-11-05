package com.choropia.app.ui

import android.content.Intent
import android.net.Uri
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.window.DialogProperties
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import com.choropia.app.BuildConfig
import com.choropia.app.data.network.AppUpdateInfo
import kotlinx.coroutines.launch

private const val RECHECK_MS = 30 * 60 * 1000L

/**
 * Tells people when a newer Choropia build has been published. No push service is involved: the app simply asks the
 * server which build is newest whenever it opens or comes back to the front (at most every 30 minutes). A normal
 * update can be postponed; one published with --required cannot be dismissed.
 */
@Composable
fun UpdatePrompt() {
    val repo = LocalRepository.current
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val lifecycleOwner = LocalLifecycleOwner.current
    var update by remember { mutableStateOf<AppUpdateInfo?>(null) }
    var postponed by remember { mutableStateOf(false) }
    var lastCheck by remember { mutableStateOf(0L) }

    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME && System.currentTimeMillis() - lastCheck > RECHECK_MS) {
                lastCheck = System.currentTimeMillis()
                scope.launch {
                    // A failed check (offline, server asleep) is silent: the next resume simply asks again.
                    val info = runCatching { repo.latestAppVersion() }.getOrNull() ?: return@launch
                    update = info.takeIf { it.version_code > BuildConfig.VERSION_CODE }
                }
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }

    val info = update ?: return
    val required = BuildConfig.VERSION_CODE < info.min_version_code
    if (postponed && !required) return

    AlertDialog(
        onDismissRequest = { if (!required) postponed = true },
        properties = DialogProperties(dismissOnBackPress = !required, dismissOnClickOutside = !required),
        title = { Text(if (required) "Please update Choropia" else "Update available") },
        text = {
            Text(
                buildString {
                    append(if (required) "This version is out of date and needs to be updated to keep working." else "A newer version of Choropia is ready.")
                    if (info.version.isNotBlank()) append("\n\nNew version: ${info.version}")
                    if (info.notes.isNotBlank()) append("\n\n${info.notes}")
                },
            )
        },
        confirmButton = {
            TextButton(onClick = {
                val link = if (info.download_url.startsWith("http")) info.download_url else BuildConfig.API_ORIGIN + info.download_url
                context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(link)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
            }) { Text("Update now") }
        },
        dismissButton = if (required) null else {
            { TextButton(onClick = { postponed = true }) { Text("Later") } }
        },
    )
}
