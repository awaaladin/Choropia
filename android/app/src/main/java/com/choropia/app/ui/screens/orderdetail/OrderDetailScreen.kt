package com.choropia.app.ui.screens.orderdetail

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.choropia.app.data.model.Order
import com.choropia.app.data.model.OrderStatusHistoryEntry
import com.choropia.app.data.model.Review
import com.choropia.app.data.repository.ChoropiaRepository
import kotlinx.coroutines.launch

private val STATUS_LABELS = mapOf(
    "pending_payment" to "Awaiting payment",
    "paid_escrow" to "Paid — held in escrow",
    "courier_assigned" to "Courier assigned",
    "in_transit" to "In transit",
    "delivered" to "Delivered",
    "confirmed" to "Confirmed by buyer",
    "disputed" to "Disputed",
    "completed" to "Completed — escrow released",
    "refunded" to "Refunded",
)

@Composable
fun OrderDetailScreen(orderId: Int, repository: ChoropiaRepository) {
    var order by remember { mutableStateOf<Order?>(null) }
    var myUserId by remember { mutableStateOf<Int?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var actionError by remember { mutableStateOf<String?>(null) }
    var disputeDialogOpen by remember { mutableStateOf(false) }
    var disputeReason by remember { mutableStateOf("") }
    var myReview by remember { mutableStateOf<Review?>(null) }
    var reviewRating by remember { mutableStateOf(5) }
    var reviewComment by remember { mutableStateOf("") }
    val scope = rememberCoroutineScope()
    val context = LocalContext.current

    suspend fun reload() {
        try {
            val current = repository.getOrder(orderId)
            order = current
            if (current.status == "completed" && myUserId != null) {
                val otherPartyId = if (myUserId == current.buyer) current.seller else current.buyer
                val existing = runCatching { repository.listReviewsFor(otherPartyId) }.getOrDefault(emptyList())
                myReview = existing.find { it.order == current.id && it.reviewer == myUserId }
            }
        } catch (e: Exception) {
            error = e.message
        }
    }

    LaunchedEffect(orderId) {
        try {
            myUserId = repository.me().id
            reload()
        } catch (e: Exception) {
            error = e.message
        }
    }

    Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {
        when {
            error != null -> Text("Could not load order: $error", color = MaterialTheme.colorScheme.error)
            order == null -> CircularProgressIndicator()
            else -> {
                val current = order!!
                val isBuyer = myUserId == current.buyer
                val isSeller = myUserId == current.seller

                Text("Order #${current.id}", style = MaterialTheme.typography.headlineSmall)
                Text(
                    STATUS_LABELS[current.status] ?: current.status,
                    color = MaterialTheme.colorScheme.primary,
                    style = MaterialTheme.typography.titleMedium,
                )
                Text("₦${current.price}", modifier = Modifier.padding(top = 4.dp))

                if (current.dispute_reason.isNotBlank()) {
                    Text(
                        "Dispute: ${current.dispute_reason}",
                        color = MaterialTheme.colorScheme.error,
                        modifier = Modifier.padding(top = 8.dp),
                    )
                }

                actionError?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(top = 8.dp)) }

                Text("Escrow timeline", style = MaterialTheme.typography.titleSmall, modifier = Modifier.padding(top = 16.dp))
                LazyColumn(modifier = Modifier.padding(top = 4.dp)) {
                    items(current.history) { entry: OrderStatusHistoryEntry ->
                        Column(modifier = Modifier.padding(vertical = 4.dp)) {
                            Text(STATUS_LABELS[entry.to_status] ?: entry.to_status, style = MaterialTheme.typography.bodyMedium)
                            Text(entry.created_at, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.outline)
                        }
                    }
                }

                Row(modifier = Modifier.padding(top = 16.dp)) {
                    if (current.status == "pending_payment" && isBuyer) {
                        Button(onClick = {
                            scope.launch {
                                try {
                                    val payment = repository.initializePayment(current.id)
                                    context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(payment.authorization_url)))
                                } catch (e: Exception) {
                                    actionError = e.message
                                }
                            }
                        }) { Text("Pay into escrow") }
                    }
                    if (current.status == "paid_escrow" && isSeller) {
                        Button(onClick = {
                            scope.launch {
                                try {
                                    repository.assignCourier(current.id)
                                    reload()
                                } catch (e: Exception) {
                                    actionError = e.message
                                }
                            }
                        }) { Text("Assign courier") }
                    }
                    if (current.status == "delivered" && isBuyer) {
                        Button(onClick = {
                            scope.launch {
                                try {
                                    repository.confirmReceipt(current.id)
                                    reload()
                                } catch (e: Exception) {
                                    actionError = e.message
                                }
                            }
                        }) { Text("Confirm receipt") }
                        OutlinedButton(
                            onClick = { disputeDialogOpen = true },
                            modifier = Modifier.padding(start = 8.dp),
                        ) { Text("Report a problem") }
                    }
                }

                if (current.status == "completed") {
                    Text("Review", style = MaterialTheme.typography.titleSmall, modifier = Modifier.padding(top = 16.dp))
                    val existingReview = myReview
                    if (existingReview != null) {
                        Text(
                            "★".repeat(existingReview.rating) + "☆".repeat(5 - existingReview.rating),
                            color = MaterialTheme.colorScheme.primary,
                        )
                        if (existingReview.comment.isNotBlank()) Text(existingReview.comment, style = MaterialTheme.typography.bodySmall)
                    } else {
                        Row(modifier = Modifier.padding(top = 4.dp)) {
                            (1..5).forEach { star ->
                                Text(
                                    if (star <= reviewRating) "★" else "☆",
                                    color = MaterialTheme.colorScheme.primary,
                                    modifier = Modifier.clickable { reviewRating = star }.padding(end = 2.dp),
                                )
                            }
                        }
                        OutlinedTextField(
                            value = reviewComment,
                            onValueChange = { reviewComment = it },
                            label = { Text("How was this transaction?") },
                            modifier = Modifier.padding(top = 8.dp),
                        )
                        Button(
                            onClick = {
                                scope.launch {
                                    try {
                                        repository.createReview(current.id, reviewRating, reviewComment)
                                        reload()
                                    } catch (e: Exception) {
                                        actionError = e.message
                                    }
                                }
                            },
                            modifier = Modifier.padding(top = 8.dp),
                        ) { Text("Submit review") }
                    }
                }

                if (disputeDialogOpen) {
                    AlertDialog(
                        onDismissRequest = { disputeDialogOpen = false },
                        title = { Text("What went wrong?") },
                        text = {
                            OutlinedTextField(
                                value = disputeReason,
                                onValueChange = { disputeReason = it },
                                label = { Text("Describe the problem") },
                            )
                        },
                        confirmButton = {
                            TextButton(
                                enabled = disputeReason.isNotBlank(),
                                onClick = {
                                    val reason = disputeReason
                                    disputeDialogOpen = false
                                    disputeReason = ""
                                    scope.launch {
                                        try {
                                            repository.openDispute(current.id, reason)
                                            reload()
                                        } catch (e: Exception) {
                                            actionError = e.message
                                        }
                                    }
                                },
                            ) { Text("Submit") }
                        },
                        dismissButton = {
                            TextButton(onClick = { disputeDialogOpen = false }) { Text("Cancel") }
                        },
                    )
                }
            }
        }
    }
}
