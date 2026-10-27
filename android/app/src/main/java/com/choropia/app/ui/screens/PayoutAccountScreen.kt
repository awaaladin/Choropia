package com.choropia.app.ui.screens

import androidx.compose.foundation.clickable
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
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material.icons.outlined.AccountBalance
import androidx.compose.material.icons.outlined.CheckCircle
import androidx.compose.material.icons.outlined.ExpandMore
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.choropia.app.data.model.Bank
import com.choropia.app.data.model.PayoutAccount
import com.choropia.app.data.network.ApiException
import com.choropia.app.data.repository.ChoropiaRepository
import com.choropia.app.ui.LocalRepository
import com.choropia.app.ui.components.BlockingLoader
import com.choropia.app.ui.components.ChoropiaField
import com.choropia.app.ui.components.ErrorBanner
import com.choropia.app.ui.components.PrimaryButton
import com.choropia.app.ui.components.SecondaryButton
import com.choropia.app.ui.components.SurfaceCard
import com.choropia.app.ui.rememberVm
import kotlinx.coroutines.launch

class PayoutAccountViewModel(private val repo: ChoropiaRepository) : ViewModel() {
    var loading by mutableStateOf(true)
        private set
    var busy by mutableStateOf(false)
        private set
    var banks by mutableStateOf<List<Bank>>(emptyList())
        private set
    var account by mutableStateOf(PayoutAccount())
        private set
    var error by mutableStateOf<String?>(null)
        private set
    var saved by mutableStateOf(false)
        private set

    init {
        viewModelScope.launch {
            try {
                account = repo.payoutAccount()
                banks = repo.banks()
            } catch (e: ApiException) {
                error = e.message
            } finally {
                loading = false
            }
        }
    }

    fun save(bankCode: String, accountNumber: String) {
        if (busy) return
        busy = true
        error = null
        saved = false
        viewModelScope.launch {
            try {
                account = repo.savePayoutAccount(bankCode, accountNumber)
                saved = true
            } catch (e: ApiException) {
                error = e.message
            } finally {
                busy = false
            }
        }
    }

    fun dismissSaved() {
        saved = false
    }

    fun remove() {
        if (busy) return
        busy = true
        viewModelScope.launch {
            try {
                repo.deletePayoutAccount()
                account = PayoutAccount()
                saved = false
            } catch (e: ApiException) {
                error = e.message
            } finally {
                busy = false
            }
        }
    }
}

@Composable
fun PayoutAccountScreen(onBack: () -> Unit) {
    val repo = LocalRepository.current
    val vm = rememberVm { PayoutAccountViewModel(repo) }

    var bank by remember { mutableStateOf<Bank?>(null) }
    var number by remember { mutableStateOf("") }
    var menu by remember { mutableStateOf(false) }
    var editing by remember { mutableStateOf(false) }

    Box(Modifier.fillMaxSize()) {
        Column(Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding().imePadding()) {
            Row(Modifier.height(56.dp).padding(horizontal = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Outlined.ArrowBack, "Back") }
                Text("Payout account", style = MaterialTheme.typography.titleLarge)
            }
            Column(
                Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(horizontal = 16.dp),
                verticalArrangement = Arrangement.spacedBy(16.dp),
            ) {
                Text(
                    "When a buyer confirms they received an item, your money is sent to this account automatically. " +
                        "Choropia keeps a small commission, which you see on every listing before you post it. Delivery drivers are paid here too.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                vm.error?.let { ErrorBanner(it) }

                val configured = vm.account.configured
                if (configured && !editing) {
                    SurfaceCard(Modifier.fillMaxWidth()) {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(14.dp)) {
                            Icon(Icons.Outlined.CheckCircle, null, tint = MaterialTheme.colorScheme.secondary)
                            Column(Modifier.weight(1f)) {
                                Text(vm.account.account_name, style = MaterialTheme.typography.titleSmall)
                                Text(
                                    "${vm.account.bank_name}  ••••${vm.account.account_last4}",
                                    style = MaterialTheme.typography.bodyMedium,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                        }
                    }
                    if (vm.saved) {
                        Text(
                            "Saved. Any payout that was waiting is on its way.",
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.secondary,
                        )
                    }
                    SecondaryButton("Change account", { editing = true; vm.dismissSaved() })
                    SecondaryButton("Remove account", { vm.remove() }, destructive = true)
                } else if (!vm.loading) {
                    Box {
                        OutlinedTextField(
                            value = bank?.name.orEmpty(),
                            onValueChange = {},
                            readOnly = true,
                            label = { Text("Bank") },
                            leadingIcon = { Icon(Icons.Outlined.AccountBalance, null) },
                            trailingIcon = { Icon(Icons.Outlined.ExpandMore, null) },
                            shape = RoundedCornerShape(14.dp),
                            modifier = Modifier.fillMaxWidth(),
                        )
                        Box(Modifier.matchParentSize().clickable { menu = true })
                        DropdownMenu(expanded = menu, onDismissRequest = { menu = false }) {
                            vm.banks.forEach { b ->
                                DropdownMenuItem(text = { Text(b.name) }, onClick = { bank = b; menu = false })
                            }
                        }
                    }
                    ChoropiaField(
                        number, { number = it.filter { c -> c.isDigit() }.take(10) }, "Account number (10 digits)",
                        keyboardType = KeyboardType.Number,
                    )
                    Text(
                        "We check the account with your bank and show you the name on it before anything is paid.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    PrimaryButton(
                        "Verify and save",
                        { bank?.let { vm.save(it.code, number); editing = false; number = "" } },
                        enabled = bank != null && number.length == 10 && !vm.busy,
                    )
                    if (configured) SecondaryButton("Cancel", { editing = false })
                }
            }
        }
        BlockingLoader(visible = vm.busy)
    }
}
