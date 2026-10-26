package com.choropia.app.ui.screens

import android.content.ActivityNotFoundException
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material.icons.outlined.ContentCopy
import androidx.compose.material.icons.outlined.Lock
import androidx.compose.material.icons.outlined.VerifiedUser
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.choropia.app.data.model.TwoFactorSetup
import com.choropia.app.data.network.ApiException
import com.choropia.app.data.repository.ChoropiaRepository
import com.choropia.app.session.Session
import com.choropia.app.ui.LocalRepository
import com.choropia.app.ui.LocalSession
import com.choropia.app.ui.components.BlockingLoader
import com.choropia.app.ui.components.ChoropiaField
import com.choropia.app.ui.components.ErrorBanner
import com.choropia.app.ui.components.PrimaryButton
import com.choropia.app.ui.components.SecondaryButton
import com.choropia.app.ui.components.SurfaceCard
import com.choropia.app.ui.rememberVm
import kotlinx.coroutines.launch

/** Everything the Security screen needs, as plain Compose state. */
class SecurityViewModel(private val repo: ChoropiaRepository, private val session: Session) : ViewModel() {
    var loading by mutableStateOf(true)
        private set
    var busy by mutableStateOf(false)
        private set
    var enabled by mutableStateOf(false)
        private set
    var recoveryRemaining by mutableStateOf(0)
        private set
    var setup by mutableStateOf<TwoFactorSetup?>(null)
        private set
    var newRecoveryCodes by mutableStateOf<List<String>>(emptyList())
        private set
    var error by mutableStateOf<String?>(null)
        private set

    init {
        refresh()
    }

    private fun refresh() {
        viewModelScope.launch {
            try {
                val status = repo.twoFactorStatus()
                enabled = status.enabled
                recoveryRemaining = status.recovery_codes_remaining
            } catch (e: ApiException) {
                error = e.message
            } finally {
                loading = false
            }
        }
    }

    private fun run(block: suspend () -> Unit) {
        if (busy) return
        busy = true
        error = null
        viewModelScope.launch {
            try {
                block()
            } catch (e: ApiException) {
                error = e.message
            } finally {
                busy = false
            }
        }
    }

    fun startSetup() = run { setup = repo.twoFactorSetup() }

    fun cancelSetup() {
        setup = null
        error = null
    }

    fun confirm(code: String) = run {
        val result = repo.twoFactorConfirm(code)
        newRecoveryCodes = result.recovery_codes
        setup = null
        enabled = true
        recoveryRemaining = result.recovery_codes.size
        session.refreshUser()
    }

    fun acknowledgeRecoveryCodes() {
        newRecoveryCodes = emptyList()
    }

    fun disable(password: String, code: String) = run {
        repo.twoFactorDisable(password, code)
        enabled = false
        recoveryRemaining = 0
        session.refreshUser()
    }
}

private fun copyToClipboard(context: Context, label: String, text: String) {
    val cm = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
    cm.setPrimaryClip(ClipData.newPlainText(label, text))
}

@Composable
fun SecurityScreen(onBack: () -> Unit, showMessage: (String) -> Unit) {
    val repo = LocalRepository.current
    val session = LocalSession.current
    val vm = rememberVm { SecurityViewModel(repo, session) }
    val context = LocalContext.current

    var code by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }

    Box(Modifier.fillMaxSize()) {
        Column(Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding().imePadding()) {
            Row(Modifier.height(56.dp).padding(horizontal = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Outlined.ArrowBack, "Back") }
                Text("Security", style = MaterialTheme.typography.titleLarge)
            }
            Column(
                Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(horizontal = 16.dp),
                verticalArrangement = Arrangement.spacedBy(16.dp),
            ) {
                vm.error?.let { ErrorBanner(it) }

                SurfaceCard(Modifier.fillMaxWidth()) {
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(14.dp)) {
                        Icon(
                            if (vm.enabled) Icons.Outlined.VerifiedUser else Icons.Outlined.Lock,
                            null,
                            tint = if (vm.enabled) MaterialTheme.colorScheme.secondary else MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        Column(Modifier.weight(1f)) {
                            Text("2-step verification", style = MaterialTheme.typography.titleSmall)
                            Text(
                                if (vm.enabled) "On. A code from your authenticator app is needed at login." else "Off. Add a second step so a stolen password isn't enough.",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                }

                when {
                    // Recovery codes: shown exactly once, right after turning it on.
                    vm.newRecoveryCodes.isNotEmpty() -> {
                        Text("Save your recovery codes", style = MaterialTheme.typography.titleMedium)
                        Text(
                            "Each code works once if you lose your phone. They won't be shown again.",
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        SurfaceCard(Modifier.fillMaxWidth()) {
                            Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                                vm.newRecoveryCodes.forEach {
                                    Text(it, style = MaterialTheme.typography.titleMedium, fontFamily = FontFamily.Monospace)
                                }
                            }
                        }
                        SecondaryButton(
                            "Copy codes",
                            {
                                copyToClipboard(context, "Choropia recovery codes", vm.newRecoveryCodes.joinToString("\n"))
                                showMessage("Recovery codes copied")
                            },
                            icon = Icons.Outlined.ContentCopy,
                        )
                        PrimaryButton("I've saved them", { vm.acknowledgeRecoveryCodes() })
                    }

                    // Enrolment in progress.
                    vm.setup != null -> {
                        val setup = vm.setup!!
                        Text("1. Add Choropia to your authenticator app", style = MaterialTheme.typography.titleMedium)
                        SecondaryButton(
                            "Open authenticator app",
                            {
                                try {
                                    context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(setup.otpauth_uri)))
                                } catch (e: ActivityNotFoundException) {
                                    showMessage("No authenticator app found. Enter the key manually.")
                                }
                            },
                        )
                        Text(
                            "Or enter this key manually:",
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        SurfaceCard(Modifier.fillMaxWidth()) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Text(
                                    setup.secret.chunked(4).joinToString(" "),
                                    style = MaterialTheme.typography.titleMedium,
                                    fontFamily = FontFamily.Monospace,
                                    modifier = Modifier.weight(1f),
                                )
                                IconButton(onClick = {
                                    copyToClipboard(context, "Choropia 2FA key", setup.secret)
                                    showMessage("Key copied")
                                }) { Icon(Icons.Outlined.ContentCopy, "Copy key") }
                            }
                        }
                        Text("2. Enter the 6-digit code it shows", style = MaterialTheme.typography.titleMedium)
                        ChoropiaField(code, { code = it.filter { c -> c.isDigit() }.take(6) }, "6-digit code", keyboardType = KeyboardType.Number)
                        PrimaryButton("Turn on", { vm.confirm(code); code = "" }, enabled = code.length == 6 && !vm.busy)
                        SecondaryButton("Cancel", { vm.cancelSetup(); code = "" })
                    }

                    vm.enabled -> {
                        Text(
                            "${vm.recoveryRemaining} recovery codes left.",
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        Text("Turn off 2-step verification", style = MaterialTheme.typography.titleMedium)
                        ChoropiaField(password, { password = it }, "Account password", password = true)
                        ChoropiaField(code, { code = it }, "Authenticator or recovery code")
                        SecondaryButton(
                            "Turn off",
                            { vm.disable(password, code); password = ""; code = "" },
                            enabled = password.isNotBlank() && code.isNotBlank() && !vm.busy,
                            destructive = true,
                        )
                    }

                    !vm.loading -> PrimaryButton("Set up 2-step verification", { vm.startSetup() }, enabled = !vm.busy)
                }
            }
        }
        BlockingLoader(visible = vm.busy)
    }
}
