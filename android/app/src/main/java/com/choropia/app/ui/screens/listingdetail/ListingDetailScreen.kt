package com.choropia.app.ui.screens.listingdetail

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
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
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import com.choropia.app.data.model.Comment
import com.choropia.app.data.model.Listing
import com.choropia.app.data.repository.ChoropiaRepository
import kotlinx.coroutines.launch

@Composable
fun ListingDetailScreen(
    listingId: Int,
    repository: ChoropiaRepository,
    onOpenChat: (Int) -> Unit,
    onNeedsLogin: () -> Unit,
    onBuyNow: (Int) -> Unit = {},
    onOpenMerchant: (Int) -> Unit = {},
) {
    var listing by remember { mutableStateOf<Listing?>(null) }
    var comments by remember { mutableStateOf<List<Comment>>(emptyList()) }
    var commentDraft by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }
    var actionError by remember { mutableStateOf<String?>(null) }
    var reportDialogOpen by remember { mutableStateOf(false) }
    var reportReason by remember { mutableStateOf("") }
    var reportSent by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    suspend fun reload() {
        try {
            listing = repository.getListing(listingId)
            comments = runCatching { repository.listComments(listingId) }.getOrDefault(emptyList())
        } catch (e: Exception) {
            error = e.message
        }
    }

    LaunchedEffect(listingId) { reload() }

    Column(modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp)) {
        when {
            error != null -> Text("Could not load listing: $error", color = MaterialTheme.colorScheme.error)
            listing == null -> CircularProgressIndicator()
            else -> {
                val current = listing!!
                current.photos.firstOrNull()?.let {
                    AsyncImage(model = it.image, contentDescription = current.title, modifier = Modifier.fillMaxWidth())
                }
                Text(current.title, style = MaterialTheme.typography.headlineSmall, modifier = Modifier.padding(top = 12.dp))
                Text("₦${current.price}", style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.primary)
                Text("${current.condition} · ${current.location}", style = MaterialTheme.typography.bodySmall)
                Text(current.description, modifier = Modifier.padding(top = 12.dp))

                current.merchant?.let { merchantId ->
                    Text(
                        "Sold by this storefront — tap to view",
                        color = MaterialTheme.colorScheme.primary,
                        modifier = Modifier.padding(top = 8.dp).clickable { onOpenMerchant(merchantId) },
                    )
                }

                actionError?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(top = 8.dp)) }

                Row(modifier = Modifier.padding(top = 16.dp)) {
                    Button(onClick = {
                        scope.launch {
                            val token = repository.getAccessTokenOrNull()
                            if (token == null) {
                                onNeedsLogin()
                                return@launch
                            }
                            try {
                                val order = repository.createOrder(current.id)
                                onBuyNow(order.id)
                            } catch (e: Exception) {
                                actionError = e.message
                            }
                        }
                    }) { Text("Buy now") }

                    OutlinedButton(
                        onClick = {
                            scope.launch {
                                val token = repository.getAccessTokenOrNull()
                                if (token == null) {
                                    onNeedsLogin()
                                    return@launch
                                }
                                try {
                                    val conversation = repository.startConversation(current.id)
                                    onOpenChat(conversation.id)
                                } catch (e: Exception) {
                                    actionError = e.message
                                }
                            }
                        },
                        modifier = Modifier.padding(start = 8.dp),
                    ) {
                        Text("Message seller")
                    }
                }

                Row(modifier = Modifier.padding(top = 12.dp)) {
                    TextButton(onClick = {
                        scope.launch {
                            if (repository.getAccessTokenOrNull() == null) {
                                onNeedsLogin()
                                return@launch
                            }
                            try {
                                if (current.is_liked) {
                                    val mine = repository.listMyLikes()
                                    mine.find { it.listing == current.id }?.let { repository.unlikeListing(it.id) }
                                } else {
                                    repository.likeListing(current.id)
                                }
                                reload()
                            } catch (e: Exception) {
                                actionError = e.message
                            }
                        }
                    }) {
                        Text("${if (current.is_liked) "♥" else "♡"} ${current.likes_count}")
                    }
                    Text(
                        "${current.comments_count} comments",
                        modifier = Modifier.padding(top = 12.dp, start = 8.dp),
                        style = MaterialTheme.typography.bodySmall,
                    )
                    TextButton(onClick = {
                        scope.launch {
                            if (repository.getAccessTokenOrNull() == null) {
                                onNeedsLogin()
                            } else {
                                reportDialogOpen = true
                            }
                        }
                    }) { Text("Report") }
                }
                if (reportSent) {
                    Text("Thanks — sent to our moderators.", color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.bodySmall)
                }

                Text("Comments", style = MaterialTheme.typography.titleSmall, modifier = Modifier.padding(top = 12.dp))
                comments.forEach { comment ->
                    Column(modifier = Modifier.padding(top = 6.dp)) {
                        Text("User #${comment.author_id ?: "?"}", style = MaterialTheme.typography.labelSmall)
                        Text(comment.body, style = MaterialTheme.typography.bodyMedium)
                    }
                }
                if (comments.isEmpty()) {
                    Text("No comments yet.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.outline, modifier = Modifier.padding(top = 6.dp))
                }

                Row(modifier = Modifier.padding(top = 8.dp)) {
                    OutlinedTextField(
                        value = commentDraft,
                        onValueChange = { commentDraft = it },
                        label = { Text("Add a comment") },
                        modifier = Modifier.weight(1f),
                    )
                    TextButton(
                        onClick = {
                            val body = commentDraft
                            if (body.isBlank()) return@TextButton
                            scope.launch {
                                if (repository.getAccessTokenOrNull() == null) {
                                    onNeedsLogin()
                                    return@launch
                                }
                                try {
                                    repository.createComment(current.id, body)
                                    commentDraft = ""
                                    reload()
                                } catch (e: Exception) {
                                    actionError = e.message
                                }
                            }
                        },
                        modifier = Modifier.padding(start = 4.dp),
                    ) { Text("Post") }
                }

                if (reportDialogOpen) {
                    AlertDialog(
                        onDismissRequest = { reportDialogOpen = false },
                        title = { Text("Report this listing") },
                        text = {
                            OutlinedTextField(
                                value = reportReason,
                                onValueChange = { reportReason = it },
                                label = { Text("Why are you reporting it?") },
                            )
                        },
                        confirmButton = {
                            TextButton(
                                enabled = reportReason.isNotBlank(),
                                onClick = {
                                    val reason = reportReason
                                    reportDialogOpen = false
                                    reportReason = ""
                                    scope.launch {
                                        try {
                                            repository.reportListing(current.id, reason)
                                            reportSent = true
                                        } catch (e: Exception) {
                                            actionError = e.message
                                        }
                                    }
                                },
                            ) { Text("Submit") }
                        },
                        dismissButton = {
                            TextButton(onClick = { reportDialogOpen = false }) { Text("Cancel") }
                        },
                    )
                }
            }
        }
    }
}
