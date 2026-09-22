package com.choropia.app.ui.screens.notifications

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.choropia.app.data.model.Notification
import com.choropia.app.data.repository.ChoropiaRepository
import kotlinx.coroutines.launch

@Composable
fun NotificationsScreen(repository: ChoropiaRepository) {
    var notifications by remember { mutableStateOf<List<Notification>>(emptyList()) }
    var error by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    suspend fun reload() {
        try {
            notifications = repository.listNotifications()
        } catch (e: Exception) {
            error = e.message
        }
    }

    LaunchedEffect(Unit) { reload() }

    Scaffold(topBar = {
        TopAppBar(
            title = { Text("Notifications") },
            actions = {
                TextButton(onClick = { scope.launch { repository.markAllNotificationsRead(); reload() } }) {
                    Text("Mark all read")
                }
            },
        )
    }) { padding ->
        Column(modifier = Modifier.fillMaxSize().padding(padding)) {
            error?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(16.dp)) }
            if (notifications.isEmpty() && error == null) {
                Text("You're all caught up.", modifier = Modifier.padding(16.dp))
            }
            LazyColumn {
                items(notifications) { notification ->
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .background(if (notification.is_read) MaterialTheme.colorScheme.surface else MaterialTheme.colorScheme.surfaceVariant)
                            .clickable(enabled = !notification.is_read) {
                                scope.launch { repository.markNotificationRead(notification.id); reload() }
                            }
                            .padding(16.dp),
                    ) {
                        Text(notification.verb, modifier = Modifier.fillMaxWidth())
                    }
                }
            }
        }
    }
}
