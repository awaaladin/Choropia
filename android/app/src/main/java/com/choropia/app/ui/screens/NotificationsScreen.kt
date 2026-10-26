package com.choropia.app.ui.screens

import androidx.compose.runtime.setValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.mutableStateOf
import com.choropia.app.ui.components.Chip
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material.icons.outlined.Gavel
import androidx.compose.material.icons.outlined.LocalShipping
import androidx.compose.material.icons.outlined.Mail
import androidx.compose.material.icons.outlined.NotificationsNone
import androidx.compose.material.icons.outlined.PersonAdd
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.choropia.app.data.model.AppNotification
import com.choropia.app.data.network.ApiException
import com.choropia.app.data.repository.ChoropiaRepository
import com.choropia.app.session.Session
import com.choropia.app.ui.LocalRepository
import com.choropia.app.ui.LocalSession
import com.choropia.app.ui.components.BrandPullToRefresh
import com.choropia.app.ui.components.EmptyState
import com.choropia.app.ui.components.ErrorState
import com.choropia.app.ui.components.ScreenLoader
import com.choropia.app.ui.rememberVm
import com.choropia.app.ui.util.timeAgo
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class NotificationsState(
    val items: List<AppNotification> = emptyList(),
    val loading: Boolean = true,
    val refreshing: Boolean = false,
    val error: String? = null,
)

class NotificationsViewModel(private val repo: ChoropiaRepository, private val session: Session) : ViewModel() {
    private val _state = MutableStateFlow(NotificationsState())
    val state: StateFlow<NotificationsState> = _state.asStateFlow()

    init {
        load(initial = true)
    }

    fun load(initial: Boolean = false) {
        viewModelScope.launch {
            _state.update { it.copy(loading = initial && it.items.isEmpty(), refreshing = !initial, error = null) }
            try {
                val list = repo.notifications().sortedByDescending { it.created_at }
                _state.update { it.copy(items = list, loading = false, refreshing = false) }
                session.refreshUnread()
            } catch (e: ApiException) {
                _state.update { it.copy(loading = false, refreshing = false, error = e.message) }
            }
        }
    }

    fun markRead(notification: AppNotification) {
        if (notification.is_read) return
        _state.update { s -> s.copy(items = s.items.map { if (it.id == notification.id) it.copy(is_read = true) else it }) }
        viewModelScope.launch {
            runCatching { repo.markNotificationRead(notification.id) }
            session.refreshUnread()
        }
    }

    fun markAllRead() {
        _state.update { s -> s.copy(items = s.items.map { it.copy(is_read = true) }) }
        session.clearUnread()
        viewModelScope.launch { runCatching { repo.markAllNotificationsRead() } }
    }
}

private fun iconFor(type: String): ImageVector = when (type) {
    "follow" -> Icons.Outlined.PersonAdd
    "message" -> Icons.Outlined.Mail
    "order_status" -> Icons.Outlined.LocalShipping
    "dispute" -> Icons.Outlined.Gavel
    else -> Icons.Outlined.NotificationsNone
}

@Composable
fun NotificationsScreen(
    onBack: () -> Unit,
    onOpenOrder: (Int) -> Unit,
    onOpenChat: (Int) -> Unit,
    onOpenMerchant: (Int) -> Unit,
) {
    val repo = LocalRepository.current
    val session = LocalSession.current
    val vm = rememberVm { NotificationsViewModel(repo, session) }
    val state by vm.state.collectAsState()
    var filter by remember { mutableStateOf(0) }   // 0 all, 1 orders & escrow, 2 messages, 3 followers
    val visible = state.items.filter { n ->
        when (filter) {
            1 -> n.notification_type == "order_status" || n.notification_type == "dispute"
            2 -> n.notification_type == "message"
            3 -> n.notification_type == "follow"
            else -> true
        }
    }

    Column(Modifier.fillMaxSize().statusBarsPadding()) {
        Row(Modifier.height(56.dp).padding(horizontal = 4.dp), verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Outlined.ArrowBack, "Back") }
            Text("Notifications", style = MaterialTheme.typography.titleLarge, modifier = Modifier.weight(1f))
            if (state.items.any { !it.is_read }) {
                TextButton(onClick = { vm.markAllRead() }) { Text("Mark all read") }
            }
        }
        Row(Modifier.padding(horizontal = 16.dp, vertical = 6.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Chip("All", filter == 0, { filter = 0 })
            Chip("Orders", filter == 1, { filter = 1 })
            Chip("Messages", filter == 2, { filter = 2 })
            Chip("Followers", filter == 3, { filter = 3 })
        }
        when {
            state.loading -> ScreenLoader()
            state.error != null -> ErrorState(state.error ?: "", { vm.load(initial = true) }, Modifier.fillMaxSize())
            else -> BrandPullToRefresh(state.refreshing, { vm.load() }, Modifier.fillMaxSize()) {
                LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(bottom = 24.dp)) {
                    if (visible.isEmpty()) {
                        item {
                            EmptyState(
                                Icons.Outlined.NotificationsNone,
                                "You're all caught up",
                                "Order updates, new followers and messages will show up here.",
                            )
                        }
                    }
                    items(visible, key = { it.id }) { n ->
                        Row(
                            Modifier
                                .fillMaxWidth()
                                .background(if (n.is_read) androidx.compose.ui.graphics.Color.Transparent else MaterialTheme.colorScheme.secondaryContainer.copy(alpha = 0.35f))
                                .clickable {
                                    vm.markRead(n)
                                    val target = n.target_object_id
                                    when {
                                        target == null -> Unit
                                        n.target_type == "order" -> onOpenOrder(target)
                                        n.target_type == "conversation" -> onOpenChat(target)
                                        n.target_type == "merchant" -> onOpenMerchant(target)
                                    }
                                }
                                .padding(horizontal = 16.dp, vertical = 14.dp),
                            horizontalArrangement = Arrangement.spacedBy(14.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Box(
                                Modifier.size(44.dp).clip(CircleShape).background(MaterialTheme.colorScheme.surfaceContainer),
                                contentAlignment = Alignment.Center,
                            ) { Icon(iconFor(n.notification_type), null, tint = MaterialTheme.colorScheme.secondary) }
                            Column(Modifier.weight(1f)) {
                                Text(n.verb, style = MaterialTheme.typography.bodyMedium)
                                Text(timeAgo(n.created_at), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                            if (!n.is_read) {
                                Box(Modifier.size(9.dp).clip(CircleShape).background(MaterialTheme.colorScheme.secondary))
                            }
                        }
                        HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                    }
                }
            }
        }
    }
}
