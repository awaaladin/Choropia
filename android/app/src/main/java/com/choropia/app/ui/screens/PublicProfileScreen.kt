package com.choropia.app.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material.icons.outlined.Inventory2
import androidx.compose.material.icons.outlined.ChatBubbleOutline
import androidx.compose.material.icons.outlined.VerifiedUser
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.choropia.app.data.model.Listing
import com.choropia.app.data.model.PublicProfile
import com.choropia.app.data.repository.ChoropiaRepository
import com.choropia.app.ui.LocalRepository
import com.choropia.app.ui.LocalSession
import com.choropia.app.ui.components.Avatar
import com.choropia.app.ui.components.Chip
import com.choropia.app.ui.components.EmptyState
import com.choropia.app.ui.components.ErrorState
import com.choropia.app.ui.components.ListingImage
import com.choropia.app.ui.components.PrimaryButton
import com.choropia.app.ui.components.ScreenLoader
import com.choropia.app.ui.components.SecondaryButton
import com.choropia.app.ui.components.SurfaceCard
import com.choropia.app.ui.rememberVm
import com.choropia.app.ui.util.formatNaira
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class PublicProfileState(
    val profile: PublicProfile? = null,
    val listings: List<Listing> = emptyList(),
    val next: String? = null,
    val loading: Boolean = true,
    val loadingMore: Boolean = false,
    val error: String? = null,
    val listingsError: String? = null,
)

class PublicProfileViewModel(
    private val userId: Int,
    private val repo: ChoropiaRepository,
) : ViewModel() {
    private val _state = MutableStateFlow(PublicProfileState())
    val state: StateFlow<PublicProfileState> = _state.asStateFlow()

    init {
        load()
    }

    fun load() {
        viewModelScope.launch {
            _state.update { it.copy(loading = it.profile == null, error = null, listingsError = null) }
            val profile = try {
                repo.publicProfile(userId)
            } catch (e: Exception) {
                _state.update { it.copy(loading = false, error = e.message ?: "Could not load this profile.") }
                return@launch
            }
            _state.update { it.copy(profile = profile, loading = false, error = null) }
            try {
                val page = repo.publicProfileListings(userId)
                _state.update {
                    it.copy(
                        listings = page.items,
                        next = page.next,
                        listingsError = null,
                    )
                }
            } catch (e: Exception) {
                _state.update { it.copy(listingsError = e.message ?: "Could not load these listings.") }
            }
        }
    }

    fun loadMore() {
        val next = _state.value.next ?: return
        if (_state.value.loadingMore) return
        viewModelScope.launch {
            _state.update { it.copy(loadingMore = true, listingsError = null) }
            try {
                val page = repo.publicProfileListingsPage(next)
                _state.update { current ->
                    val known = current.listings.map { it.id }.toSet()
                    current.copy(
                        listings = current.listings + page.items.filter { it.id !in known },
                        next = page.next,
                        loadingMore = false,
                    )
                }
            } catch (e: Exception) {
                _state.update { it.copy(loadingMore = false, listingsError = e.message ?: "Could not load more listings.") }
            }
        }
    }
}

@Composable
fun PublicProfileScreen(
    userId: Int,
    onBack: () -> Unit,
    onOpenListing: (Int) -> Unit,
    onOpenChat: (Int) -> Unit,
    onNeedsLogin: () -> Unit,
    showMessage: (String) -> Unit,
) {
    val repo = LocalRepository.current
    val session = LocalSession.current
    val vm = rememberVm(key = "public-profile-$userId") { PublicProfileViewModel(userId, repo) }
    val state by vm.state.collectAsState()
    val me by session.user.collectAsState()
    var selectedTab by remember(userId) { mutableIntStateOf(0) }
    var messageBusy by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    val profile = state.profile

    if (state.loading && profile == null) {
        ScreenLoader()
        return
    }
    if (state.error != null && profile == null) {
        ErrorState(state.error ?: "Could not load this profile.", { vm.load() }, Modifier.fillMaxSize())
        return
    }

    LazyColumn(
        Modifier.fillMaxSize(),
        contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 8.dp, bottom = 24.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        item {
            Row(verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = onBack) {
                    Icon(Icons.AutoMirrored.Outlined.ArrowBack, contentDescription = "Back")
                }
                Text("Seller profile", style = MaterialTheme.typography.titleLarge)
            }
        }
        item {
            SurfaceCard(Modifier.fillMaxWidth(), padding = PaddingValues(18.dp)) {
                Column(verticalArrangement = Arrangement.spacedBy(14.dp)) {
                    Row(horizontalArrangement = Arrangement.spacedBy(14.dp), verticalAlignment = Alignment.CenterVertically) {
                        Avatar(profile?.display_name ?: "Choropia member", profile?.avatar_url, size = 68.dp)
                        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(5.dp)) {
                                Text(
                                    profile?.display_name ?: "Choropia member",
                                    style = MaterialTheme.typography.titleLarge,
                                    maxLines = 2,
                                    overflow = TextOverflow.Ellipsis,
                                )
                                if (profile?.verified == true) {
                                    Icon(Icons.Outlined.VerifiedUser, "Verified seller", tint = MaterialTheme.colorScheme.primary)
                                }
                            }
                            profile?.username?.takeIf { it.isNotBlank() }?.let {
                                Text("@$it", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        }
                    }
                    Text(
                        profile?.bio?.ifBlank { "This member hasn’t added a bio yet." } ?: "",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        SurfaceCard(Modifier.weight(1f), padding = PaddingValues(12.dp)) {
                            Column {
                                Text("Completed sales", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                Text("${profile?.completed_sales ?: 0}", style = MaterialTheme.typography.titleMedium)
                            }
                        }
                        SurfaceCard(Modifier.weight(1f), padding = PaddingValues(12.dp)) {
                            Column {
                                Text("Member since", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                Text(joinedMonth(profile?.joined_at.orEmpty()), style = MaterialTheme.typography.titleSmall)
                            }
                        }
                    }
                    if (profile != null && profile.id != me?.id) {
                        PrimaryButton(
                            text = if (messageBusy) "Opening chat…" else "Message",
                            icon = Icons.Outlined.ChatBubbleOutline,
                            onClick = {
                                if (!session.loggedIn.value) {
                                    onNeedsLogin()
                                } else if (!messageBusy) {
                                    scope.launch {
                                        messageBusy = true
                                        try {
                                            val conversation = repo.openUserConversation(profile.id)
                                            onOpenChat(conversation.id)
                                        } catch (e: Exception) {
                                            showMessage(e.message ?: "Could not open this conversation.")
                                        } finally {
                                            messageBusy = false
                                        }
                                    }
                                }
                            },
                            enabled = !messageBusy,
                            modifier = Modifier.fillMaxWidth(),
                        )
                    }
                }
            }
        }
        item {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Chip("Listings", selectedTab == 0, { selectedTab = 0 })
                Chip("About", selectedTab == 1, { selectedTab = 1 })
            }
        }
        if (selectedTab == 1) {
            item {
                SurfaceCard(Modifier.fillMaxWidth()) {
                    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                        Text("About this member", style = MaterialTheme.typography.titleMedium)
                        Text(
                            profile?.bio?.ifBlank { "No bio has been added yet." } ?: "",
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        Text(
                            if (profile?.verified == true) "Verified seller" else "Choropia community member",
                            style = MaterialTheme.typography.bodySmall,
                        )
                    }
                }
            }
        } else {
            if (state.listingsError != null && state.listings.isEmpty()) {
                item { ErrorState(state.listingsError ?: "Could not load listings.", { vm.load() }) }
            } else if (state.listings.isEmpty()) {
                item {
                    EmptyState(
                        icon = Icons.Outlined.Inventory2,
                        title = "No public listings",
                        message = "This member doesn’t have any public listings right now.",
                    )
                }
            } else {
                items(state.listings, key = { it.id }) { listing ->
                    SurfaceCard(Modifier.fillMaxWidth(), padding = PaddingValues(0.dp), onClick = { onOpenListing(listing.id) }) {
                        Column {
                            ListingImage(listing.cover_photo, Modifier.fillMaxWidth(), listing.title)
                            Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                                Text(listing.title, style = MaterialTheme.typography.titleSmall, maxLines = 2, overflow = TextOverflow.Ellipsis)
                                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                    Text(formatNaira(listing.price), style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.primary)
                                    if (listing.status == "sold") {
                                        Text("Sold", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                    }
                                    if (listing.location.isNotBlank()) {
                                        Text(listing.location, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                    }
                                }
                            }
                        }
                    }
                }
                if (state.listingsError != null) {
                    item { ErrorState(state.listingsError ?: "Could not load more listings.", { vm.loadMore() }) }
                } else if (state.next != null) {
                    item {
                        SecondaryButton(
                            text = if (state.loadingMore) "Loading…" else "Load more listings",
                            onClick = vm::loadMore,
                            enabled = !state.loadingMore,
                            modifier = Modifier.fillMaxWidth(),
                            icon = Icons.Outlined.Inventory2,
                        )
                    }
                }
            }
        }
    }
}

private fun joinedMonth(value: String): String = runCatching {
    LocalDate.parse(value.take(10)).format(DateTimeFormatter.ofPattern("MMMM yyyy"))
}.getOrDefault("—")
