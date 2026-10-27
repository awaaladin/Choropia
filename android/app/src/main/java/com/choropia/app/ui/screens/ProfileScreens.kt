package com.choropia.app.ui.screens

import androidx.compose.material.icons.outlined.BookmarkBorder
import androidx.compose.material.icons.outlined.Sell
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material.icons.automirrored.outlined.Logout
import androidx.compose.material.icons.outlined.AccountBalance
import androidx.compose.material.icons.outlined.ChevronRight
import androidx.compose.material.icons.outlined.LocalShipping
import androidx.compose.material.icons.outlined.Lock
import androidx.compose.material.icons.outlined.DarkMode
import androidx.compose.material.icons.outlined.Edit
import androidx.compose.material.icons.outlined.LocationOn
import androidx.compose.material.icons.outlined.Phone
import androidx.compose.material.icons.outlined.ReceiptLong
import androidx.compose.material.icons.outlined.Storefront
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.choropia.app.BuildConfig
import com.choropia.app.data.network.ApiException
import com.choropia.app.data.repository.ChoropiaRepository
import com.choropia.app.session.Session
import com.choropia.app.ui.LocalRepository
import com.choropia.app.ui.LocalSession
import com.choropia.app.ui.components.Avatar
import com.choropia.app.ui.components.BlockingLoader
import com.choropia.app.ui.components.Chip
import com.choropia.app.ui.components.ChoropiaField
import com.choropia.app.ui.components.EmptyState
import com.choropia.app.ui.components.ErrorBanner
import com.choropia.app.ui.components.PrimaryButton
import com.choropia.app.ui.components.SecondaryButton
import com.choropia.app.ui.components.SectionTitle
import com.choropia.app.ui.components.SurfaceCard
import com.choropia.app.ui.rememberVm
import kotlinx.coroutines.launch

// --- "Me" tab -------------------------------------------------------------------------------

@Composable
fun ProfileScreen(
    onOrders: () -> Unit,
    onWatchlist: () -> Unit,
    onMyListings: () -> Unit,
    onSecurity: () -> Unit,
    onPayoutAccount: () -> Unit,
    onDriver: () -> Unit,
    onEditProfile: () -> Unit,
    onApplyMerchant: () -> Unit,
    showMessage: (String) -> Unit,
) {
    val repo = LocalRepository.current
    val session = LocalSession.current
    val user by session.user.collectAsState()
    val themeMode by repo.themeModeFlow.collectAsState(initial = "system")
    val scope = rememberCoroutineScope()
    var confirmLogout by remember { mutableStateOf(false) }

    LaunchedEffect(Unit) { session.refreshUser() }

    Column(
        Modifier.fillMaxSize().statusBarsPadding().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        val u = user
        SurfaceCard(Modifier.fillMaxWidth(), padding = PaddingValues(18.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                Avatar(u?.displayName ?: "You", u?.profile?.avatar, size = 68.dp)
                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                    Text(u?.displayName ?: "Your account", style = MaterialTheme.typography.titleLarge)
                    Text(u?.email.orEmpty(), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    u?.profile?.location?.takeIf { it.isNotBlank() }?.let {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                            Icon(Icons.Outlined.LocationOn, null, Modifier.size(14.dp), tint = MaterialTheme.colorScheme.onSurfaceVariant)
                            Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
                IconButton(onClick = onEditProfile) { Icon(Icons.Outlined.Edit, "Edit profile") }
            }
        }
        u?.profile?.bio?.takeIf { it.isNotBlank() }?.let {
            Text(it, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }

        SurfaceCard(Modifier.fillMaxWidth(), padding = PaddingValues(vertical = 4.dp)) {
            Column {
                MenuRow(Icons.Outlined.ReceiptLong, "My orders", "Track purchases and sales", onOrders)
                HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                MenuRow(Icons.Outlined.Sell, "My listings", "Items you're selling or have sold", onMyListings)
                HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                MenuRow(Icons.Outlined.BookmarkBorder, "Watchlist", "Listings you saved", onWatchlist)
                HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                MenuRow(Icons.Outlined.AccountBalance, "Payout account", "Where your sales money is sent", onPayoutAccount)
                HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                MenuRow(Icons.Outlined.Lock, "Security", "2-step verification", onSecurity)
                HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                MenuRow(Icons.Outlined.LocalShipping, "Deliver with Choropia", "Earn as a delivery driver", onDriver)
                HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                MenuRow(Icons.Outlined.Storefront, "Open a storefront", "Apply to sell as a verified merchant", onApplyMerchant)
            }
        }

        val legalContext = androidx.compose.ui.platform.LocalContext.current
        SurfaceCard(Modifier.fillMaxWidth(), padding = PaddingValues(vertical = 4.dp)) {
            Column {
                MenuRow(Icons.Outlined.Lock, "Terms and Conditions", "How Choropia works", { openWebPage(legalContext, legalUrl("terms")) })
                HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                MenuRow(Icons.Outlined.Lock, "Privacy Policy", "How we protect your data", { openWebPage(legalContext, legalUrl("privacy")) })
            }
        }

        SectionTitle("Appearance")
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
            Icon(Icons.Outlined.DarkMode, null, tint = MaterialTheme.colorScheme.onSurfaceVariant)
            listOf("system" to "System", "light" to "Light", "dark" to "Dark").forEach { (value, label) ->
                Chip(label, themeMode == value, { scope.launch { repo.setThemeMode(value) } })
            }
        }

        SecondaryButton("Log out", { confirmLogout = true }, icon = Icons.AutoMirrored.Outlined.Logout, destructive = true)
        Text(
            "Choropia ${BuildConfig.VERSION_NAME} · escrow-protected marketplace for Uyo",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.outline,
            modifier = Modifier.fillMaxWidth(),
        )
        Spacer(Modifier.height(24.dp))
    }

    if (confirmLogout) {
        AlertDialog(
            onDismissRequest = { confirmLogout = false },
            title = { Text("Log out?") },
            text = { Text("You'll need to sign in again to buy, sell or message.") },
            confirmButton = {
                TextButton(onClick = {
                    confirmLogout = false
                    scope.launch { session.logout(); showMessage("Logged out") }
                }) { Text("Log out") }
            },
            dismissButton = { TextButton(onClick = { confirmLogout = false }) { Text("Cancel") } },
        )
    }
}

@Composable
private fun MenuRow(icon: ImageVector, title: String, subtitle: String, onClick: () -> Unit) {
    Row(
        Modifier.fillMaxWidth().clickable(onClick = onClick).padding(horizontal = 16.dp, vertical = 14.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Icon(icon, null, tint = MaterialTheme.colorScheme.secondary)
        Column(Modifier.weight(1f)) {
            Text(title, style = MaterialTheme.typography.titleSmall)
            Text(subtitle, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Icon(Icons.Outlined.ChevronRight, null, tint = MaterialTheme.colorScheme.outline)
    }
}

// --- edit profile ---------------------------------------------------------------------------

class EditProfileViewModel(private val repo: ChoropiaRepository, private val session: Session) : ViewModel() {
    var busy by mutableStateOf(false)
        private set
    var error by mutableStateOf<String?>(null)
        private set
    var fieldErrors by mutableStateOf<Map<String, String>>(emptyMap())
        private set

    fun save(first: String, last: String, phone: String, bio: String, location: String, onDone: () -> Unit) {
        if (busy) return
        busy = true
        error = null
        fieldErrors = emptyMap()
        viewModelScope.launch {
            try {
                val theme = session.user.value?.profile?.theme_preference ?: "light"
                session.setUser(repo.updateProfile(first, last, phone.ifBlank { null }, bio, location, theme))
                onDone()
            } catch (e: ApiException) {
                error = e.message
                fieldErrors = e.fieldErrors
            } finally {
                busy = false
            }
        }
    }
}

@Composable
fun EditProfileScreen(onBack: () -> Unit, onSaved: () -> Unit) {
    val repo = LocalRepository.current
    val session = LocalSession.current
    val vm = rememberVm { EditProfileViewModel(repo, session) }
    val user by session.user.collectAsState()

    var first by remember(user?.id) { mutableStateOf(user?.first_name.orEmpty()) }
    var last by remember(user?.id) { mutableStateOf(user?.last_name.orEmpty()) }
    var phone by remember(user?.id) { mutableStateOf(user?.phone_number.orEmpty()) }
    var bio by remember(user?.id) { mutableStateOf(user?.profile?.bio.orEmpty()) }
    var location by remember(user?.id) { mutableStateOf(user?.profile?.location.orEmpty()) }

    Box(Modifier.fillMaxSize()) {
        Column(Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding().imePadding()) {
            Row(Modifier.height(56.dp).padding(horizontal = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Outlined.ArrowBack, "Back") }
                Text("Edit profile", style = MaterialTheme.typography.titleLarge)
            }
            Column(
                Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(horizontal = 16.dp),
                verticalArrangement = Arrangement.spacedBy(14.dp),
            ) {
                vm.error?.let { ErrorBanner(it) }
                ChoropiaField(first, { first = it }, "First name", error = vm.fieldErrors["first_name"])
                ChoropiaField(last, { last = it }, "Last name", error = vm.fieldErrors["last_name"])
                ChoropiaField(phone, { phone = it }, "Phone", leadingIcon = Icons.Outlined.Phone, error = vm.fieldErrors["phone_number"])
                ChoropiaField(location, { location = it }, "Location", leadingIcon = Icons.Outlined.LocationOn)
                ChoropiaField(bio, { bio = it }, "Bio", singleLine = false, minLines = 3)
            }
            Box(Modifier.padding(16.dp)) {
                PrimaryButton("Save changes", { vm.save(first, last, phone, bio, location, onSaved) }, enabled = !vm.busy)
            }
        }
        BlockingLoader(visible = vm.busy)
    }
}

// --- sign-in gate for tabs that need an account ---------------------------------------------

@Composable
fun LoginGate(title: String, message: String, onLogin: () -> Unit, onRegister: () -> Unit) {
    Column(
        Modifier.fillMaxSize().statusBarsPadding().padding(24.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        EmptyState(
            icon = Icons.Outlined.Lock,
            title = title,
            message = message,
        )
        Column(Modifier.padding(horizontal = 24.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            PrimaryButton("Log in", onLogin)
            SecondaryButton("Create an account", onRegister)
        }
    }
}
