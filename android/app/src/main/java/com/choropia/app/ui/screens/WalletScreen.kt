package com.choropia.app.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.choropia.app.data.network.ApiException
import com.choropia.app.data.network.WalletSummary
import com.choropia.app.data.network.WalletTransaction
import com.choropia.app.ui.LocalRepository
import com.choropia.app.ui.components.ErrorBanner
import com.choropia.app.ui.components.ScreenLoader
import com.choropia.app.ui.components.SurfaceCard
import com.choropia.app.ui.util.formatNaira

private fun statusLabel(status: String) = when (status) {
    "paid_held" -> "Held in escrow"
    "released" -> "Released"
    "refunded" -> "Refunded"
    "failed" -> "Failed"
    else -> status.replace('_', ' ').replaceFirstChar { it.uppercase() }
}

/** Where your escrow money stands: held while an order is open, released once it completes. */
@Composable
fun WalletScreen(onBack: () -> Unit, onOpenOrder: (Int) -> Unit) {
    val repo = LocalRepository.current
    var summary by remember { mutableStateOf<WalletSummary?>(null) }
    var transactions by remember { mutableStateOf<List<WalletTransaction>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(Unit) {
        try {
            summary = repo.walletSummary()
            transactions = repo.walletTransactions()
        } catch (e: ApiException) {
            error = e.message
        } finally {
            loading = false
        }
    }

    Column(Modifier.fillMaxSize().statusBarsPadding()) {
        Row(Modifier.height(56.dp).padding(horizontal = 4.dp), verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Outlined.ArrowBack, "Back") }
            Text("Wallet", style = MaterialTheme.typography.titleLarge)
        }
        val s = summary
        when {
            loading -> ScreenLoader()
            s == null -> Column(Modifier.padding(16.dp)) { ErrorBanner(error ?: "We couldn't load your wallet.") }
            else -> Column(
                Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(14.dp),
            ) {
                Text(
                    "Where your escrow money stands. When you pay, we hold it safely until the order is confirmed, then release it to the seller.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                SurfaceCard(Modifier.fillMaxWidth()) {
                    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text("As a seller", style = MaterialTheme.typography.titleSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Text(formatNaira(s.selling.released_total), style = MaterialTheme.typography.headlineSmall)
                        Text("Released to you", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Text(formatNaira(s.selling.held_total), style = MaterialTheme.typography.titleMedium, modifier = Modifier.padding(top = 8.dp))
                        Text("Still held in escrow from buyers", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
                SurfaceCard(Modifier.fillMaxWidth()) {
                    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text("As a buyer", style = MaterialTheme.typography.titleSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Text(formatNaira(s.buying.held_total), style = MaterialTheme.typography.headlineSmall)
                        Text("Held, waiting for you to confirm delivery", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Text(formatNaira(s.buying.spent_total), style = MaterialTheme.typography.titleMedium, modifier = Modifier.padding(top = 8.dp))
                        Text("Total paid into escrow", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
                Text("Activity", style = MaterialTheme.typography.titleMedium)
                if (transactions.isEmpty()) {
                    Text("Nothing yet. Payments for your orders will show here.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                transactions.forEach { tx ->
                    SurfaceCard(Modifier.fillMaxWidth(), onClick = { onOpenOrder(tx.order) }) {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                            Column(Modifier.weight(1f)) {
                                Text(tx.listing_title, style = MaterialTheme.typography.titleSmall, maxLines = 1)
                                Text(
                                    (if (tx.role == "selling") "Sale" else "Purchase") + " · " + statusLabel(tx.status),
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                            Text(formatNaira(tx.amount), style = MaterialTheme.typography.titleSmall)
                        }
                    }
                }
            }
        }
    }
}
