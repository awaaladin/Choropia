package com.choropia.app.ui.screens

import com.choropia.app.ui.components.Chip
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material.icons.outlined.Lock
import androidx.compose.material.icons.outlined.MailOutline
import androidx.compose.material.icons.outlined.MarkEmailRead
import androidx.compose.material.icons.outlined.Person
import androidx.compose.material.icons.outlined.Phone
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
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.choropia.app.R
import com.choropia.app.data.network.ApiException
import com.choropia.app.data.repository.ChoropiaRepository
import com.choropia.app.data.repository.LoginResult
import com.choropia.app.session.Session
import com.choropia.app.ui.LocalRepository
import com.choropia.app.ui.LocalSession
import com.choropia.app.ui.components.BlockingLoader
import com.choropia.app.ui.components.ChoropiaField
import com.choropia.app.ui.components.EmptyState
import com.choropia.app.ui.components.ErrorBanner
import com.choropia.app.ui.components.PrimaryButton
import com.choropia.app.ui.components.QuietButton
import com.choropia.app.ui.rememberVm
import com.choropia.app.ui.theme.LocalIsDark
import kotlinx.coroutines.launch

class AuthViewModel(private val repo: ChoropiaRepository, private val session: Session) : ViewModel() {
    var busy by mutableStateOf(false)
        private set
    var error by mutableStateOf<String?>(null)
        private set
    var fieldErrors by mutableStateOf<Map<String, String>>(emptyMap())
        private set
    var resetSent by mutableStateOf(false)
        private set

    /** Set when the account has 2-step verification: the login is paused until a code is entered. */
    var challenge by mutableStateOf<String?>(null)
        private set

    fun cancelChallenge() {
        challenge = null
        clearError()
    }

    fun verifyCode(code: String, onDone: () -> Unit) {
        val pending = challenge ?: return
        if (code.isBlank()) {
            error = "Enter the code from your authenticator app."
            return
        }
        run {
            session.setUser(repo.verifyTwoFactor(pending, code))
            challenge = null
            onDone()
        }
    }

    fun clearError() {
        error = null
        fieldErrors = emptyMap()
    }

    private fun run(block: suspend () -> Unit) {
        if (busy) return
        busy = true
        error = null
        fieldErrors = emptyMap()
        viewModelScope.launch {
            try {
                block()
            } catch (e: ApiException) {
                error = e.message
                fieldErrors = e.fieldErrors
            } finally {
                busy = false
            }
        }
    }

    fun login(identifier: String, password: String, onDone: () -> Unit) {
        if (identifier.isBlank() || password.isBlank()) {
            error = "Enter your email or phone and your password."
            return
        }
        run {
            when (val result = repo.login(identifier, password)) {
                is LoginResult.Success -> {
                    session.setUser(result.user)
                    onDone()
                }
                is LoginResult.NeedsCode -> challenge = result.challenge
            }
        }
    }

    fun register(
        firstName: String,
        lastName: String,
        email: String,
        phone: String,
        password: String,
        onDone: () -> Unit,
    ) {
        when {
            firstName.isBlank() -> { error = "Tell us your first name."; return }
            !email.contains('@') -> { error = "Enter a valid email address."; return }
            password.length < 8 -> { error = "Use a password with at least 8 characters."; return }
        }
        run {
            session.setUser(repo.register(email, password, phone.ifBlank { null }, firstName, lastName))
            onDone()
        }
    }

    fun requestReset(email: String) {
        if (!email.contains('@')) {
            error = "Enter the email address you signed up with."
            return
        }
        run {
            repo.requestPasswordReset(email)
            resetSent = true
        }
    }
}

@Composable
private fun AuthFrame(
    title: String,
    subtitle: String,
    busy: Boolean,
    onBack: (() -> Unit)?,
    content: @Composable () -> Unit,
) {
    Box(Modifier.fillMaxSize()) {
        Column(
            Modifier
                .fillMaxSize()
                .statusBarsPadding()
                .navigationBarsPadding()
                .imePadding()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 24.dp),
        ) {
            Row(Modifier.height(56.dp), verticalAlignment = Alignment.CenterVertically) {
                if (onBack != null) {
                    IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Outlined.ArrowBack, "Back") }
                }
            }
            Image(
                painter = painterResource(if (LocalIsDark.current) R.drawable.brand_mark_white else R.drawable.brand_mark_navy),
                contentDescription = "Choropia",
                modifier = Modifier.width(64.dp).aspectRatio(452f / 364f),
            )
            Spacer(Modifier.height(24.dp))
            Text(title, style = MaterialTheme.typography.headlineMedium)
            Spacer(Modifier.height(6.dp))
            Text(subtitle, style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Spacer(Modifier.height(28.dp))
            content()
            Spacer(Modifier.height(32.dp))
        }
        BlockingLoader(visible = busy, style = com.choropia.app.ui.components.LoaderStyle.Full)
    }
}

@Composable
fun LoginScreen(onLoggedIn: () -> Unit, onRegister: () -> Unit, onForgot: () -> Unit, onBack: () -> Unit) {
    val repo = LocalRepository.current
    val session = LocalSession.current
    val vm = rememberVm { AuthViewModel(repo, session) }
    var identifier by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    val focus = LocalFocusManager.current
    var code by remember { mutableStateOf("") }

    if (vm.challenge != null) {
        AuthFrame(
            "Two-step verification",
            "Enter the 6-digit code from your authenticator app, or one of your recovery codes.",
            vm.busy,
            onBack = { code = ""; vm.cancelChallenge() },
        ) {
            Column(verticalArrangement = Arrangement.spacedBy(14.dp)) {
                vm.error?.let { ErrorBanner(it) }
                ChoropiaField(
                    code, { code = it; vm.clearError() }, "Code",
                    keyboardType = KeyboardType.Number, imeAction = ImeAction.Done, leadingIcon = Icons.Outlined.Lock,
                    onImeAction = { focus.clearFocus(); vm.verifyCode(code, onLoggedIn) },
                )
                PrimaryButton("Verify", { focus.clearFocus(); vm.verifyCode(code, onLoggedIn) }, enabled = !vm.busy)
            }
        }
        return
    }

    AuthFrame("Welcome back", "Log in to buy, sell and chat on Choropia.", vm.busy, onBack) {
        Column(verticalArrangement = Arrangement.spacedBy(14.dp)) {
            vm.error?.let { ErrorBanner(it) }
            ChoropiaField(
                identifier, { identifier = it; vm.clearError() }, "Email or phone",
                keyboardType = KeyboardType.Email, leadingIcon = Icons.Outlined.MailOutline,
                error = vm.fieldErrors["identifier"],
            )
            ChoropiaField(
                password, { password = it; vm.clearError() }, "Password",
                password = true, imeAction = ImeAction.Done, leadingIcon = Icons.Outlined.Lock,
                onImeAction = { focus.clearFocus(); vm.login(identifier, password, onLoggedIn) },
            )
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                QuietButton("Forgot password?", onForgot)
            }
            PrimaryButton("Log in", { focus.clearFocus(); vm.login(identifier, password, onLoggedIn) }, enabled = !vm.busy)
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.Center, verticalAlignment = Alignment.CenterVertically) {
                Text("New to Choropia?", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                QuietButton("Create an account", onRegister)
            }
        }
    }
}

@Composable
fun RegisterScreen(onRegistered: (wantsStorefront: Boolean) -> Unit, onLogin: () -> Unit, onBack: () -> Unit) {
    val repo = LocalRepository.current
    val session = LocalSession.current
    val vm = rememberVm { AuthViewModel(repo, session) }
    var first by remember { mutableStateOf("") }
    var last by remember { mutableStateOf("") }
    var email by remember { mutableStateOf("") }
    var phone by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var storefront by remember { mutableStateOf(false) }
    var agreed by remember { mutableStateOf(false) }
    val legalContext = androidx.compose.ui.platform.LocalContext.current
    val focus = LocalFocusManager.current

    AuthFrame("Create your account", "Join Uyo's trusted, escrow-protected marketplace.", vm.busy, onBack) {
        Column(verticalArrangement = Arrangement.spacedBy(14.dp)) {
            vm.error?.let { ErrorBanner(it) }
            Text("I want to", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Chip("Buy and sell personally", !storefront, { storefront = false })
                Chip("Open a storefront", storefront, { storefront = true })
            }
            if (storefront) {
                Text(
                    "You'll set up your business details right after creating your account.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                Box(Modifier.weight(1f)) {
                    ChoropiaField(first, { first = it; vm.clearError() }, "First name", error = vm.fieldErrors["first_name"])
                }
                Box(Modifier.weight(1f)) {
                    ChoropiaField(last, { last = it; vm.clearError() }, "Last name", error = vm.fieldErrors["last_name"])
                }
            }
            ChoropiaField(
                email, { email = it; vm.clearError() }, "Email",
                keyboardType = KeyboardType.Email, leadingIcon = Icons.Outlined.MailOutline, error = vm.fieldErrors["email"],
            )
            ChoropiaField(
                phone, { phone = it; vm.clearError() }, "Phone (optional)",
                keyboardType = KeyboardType.Phone, leadingIcon = Icons.Outlined.Phone, error = vm.fieldErrors["phone_number"],
            )
            ChoropiaField(
                password, { password = it; vm.clearError() }, "Password",
                password = true, imeAction = ImeAction.Done, leadingIcon = Icons.Outlined.Lock,
                error = vm.fieldErrors["password"],
                onImeAction = { focus.clearFocus(); vm.register(first, last, email, phone, password) { onRegistered(storefront) } },
            )
            Text(
                "At least 8 characters. Avoid common passwords.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Row(verticalAlignment = Alignment.CenterVertically) {
                androidx.compose.material3.Checkbox(checked = agreed, onCheckedChange = { agreed = it })
                Text("I agree to the Terms and Conditions and the Privacy Policy.", style = MaterialTheme.typography.bodySmall, modifier = Modifier.weight(1f))
            }
            Row {
                QuietButton("Terms", { openWebPage(legalContext, legalUrl("terms")) })
                QuietButton("Privacy Policy", { openWebPage(legalContext, legalUrl("privacy")) })
            }
            PrimaryButton(
                "Create account",
                { focus.clearFocus(); vm.register(first, last, email, phone, password) { onRegistered(storefront) } },
                enabled = !vm.busy && agreed,
            )
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.Center, verticalAlignment = Alignment.CenterVertically) {
                Text("Already have an account?", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                QuietButton("Log in", onLogin)
            }
        }
    }
}

@Composable
fun ForgotPasswordScreen(onBack: () -> Unit) {
    val repo = LocalRepository.current
    val session = LocalSession.current
    val vm = rememberVm { AuthViewModel(repo, session) }
    var email by remember { mutableStateOf("") }
    val focus = LocalFocusManager.current

    AuthFrame("Reset your password", "We'll email you a secure link to choose a new one.", vm.busy, onBack) {
        if (vm.resetSent) {
            EmptyState(
                icon = Icons.Outlined.MarkEmailRead,
                title = "Check your inbox",
                message = "If an account exists for $email, a reset link is on its way. Open it on this phone to set a new password.",
                actionLabel = "Back to log in",
                onAction = onBack,
            )
        } else {
            Column(verticalArrangement = Arrangement.spacedBy(14.dp)) {
                vm.error?.let { ErrorBanner(it) }
                ChoropiaField(
                    email, { email = it; vm.clearError() }, "Email",
                    keyboardType = KeyboardType.Email, imeAction = ImeAction.Done,
                    leadingIcon = Icons.Outlined.Person, error = vm.fieldErrors["email"],
                    onImeAction = { focus.clearFocus(); vm.requestReset(email) },
                )
                PrimaryButton("Send reset link", { focus.clearFocus(); vm.requestReset(email) }, enabled = !vm.busy)
            }
        }
    }
}
