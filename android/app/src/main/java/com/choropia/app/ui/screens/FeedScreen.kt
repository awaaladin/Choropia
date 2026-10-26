package com.choropia.app.ui.screens

import androidx.compose.runtime.setValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.mutableStateOf
import androidx.compose.foundation.lazy.LazyRow
import com.choropia.app.ui.components.Chip
import androidx.compose.foundation.Image
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.AddCircleOutline
import androidx.compose.material.icons.outlined.Inventory2
import androidx.compose.material.icons.outlined.NotificationsNone
import androidx.compose.material.icons.outlined.PersonOutline
import androidx.compose.material3.Badge
import androidx.compose.material3.BadgedBox
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.snapshotFlow
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.choropia.app.R
import com.choropia.app.data.model.Listing
import com.choropia.app.data.network.ApiException
import com.choropia.app.data.repository.ChoropiaRepository
import com.choropia.app.session.Session
import com.choropia.app.ui.LocalRepository
import com.choropia.app.ui.LocalSession
import com.choropia.app.ui.components.BrandPullToRefresh
import com.choropia.app.ui.components.BrandLoader
import com.choropia.app.ui.components.EmptyState
import com.choropia.app.ui.components.ErrorState
import com.choropia.app.ui.components.LoaderStyle
import com.choropia.app.ui.components.PostCard
import com.choropia.app.ui.components.ScreenLoader
import com.choropia.app.ui.components.SurfaceCard
import com.choropia.app.ui.rememberVm
import com.choropia.app.ui.theme.LocalIsDark
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class FeedState(
    val items: List<Listing> = emptyList(),
    val categories: Map<Int, String> = emptyMap(),
    val loading: Boolean = true,
    val refreshing: Boolean = false,
    val loadingMore: Boolean = false,
    val next: String? = null,
    val error: String? = null,
    val message: String? = null,
)

class FeedViewModel(private val repo: ChoropiaRepository, private val session: Session) : ViewModel() {
    private val _state = MutableStateFlow(FeedState())
    val state: StateFlow<FeedState> = _state.asStateFlow()

    init {
        load(initial = true)
        viewModelScope.launch {
            runCatching { repo.categories() }.onSuccess { cats ->
                _state.update { it.copy(categories = cats.associate { c -> c.id to c.name }) }
            }
        }
    }

    fun load(initial: Boolean = false) {
        viewModelScope.launch {
            _state.update { it.copy(loading = initial && it.items.isEmpty(), refreshing = !initial, error = null) }
            try {
                val loggedIn = repo.isLoggedIn()
                var page = if (loggedIn) repo.feed() else repo.listings()
                // A brand-new account follows nobody yet: fall back to what's selling around.
                if (loggedIn && page.items.isEmpty()) page = repo.listings()
                _state.update { it.copy(items = page.items, next = page.next, loading = false, refreshing = false) }
            } catch (e: ApiException) {
                _state.update { it.copy(loading = false, refreshing = false, error = if (it.items.isEmpty()) e.message else null, message = e.message) }
            }
        }
    }

    fun loadMore() {
        val current = _state.value
        val next = current.next ?: return
        if (current.loadingMore || current.refreshing) return
        viewModelScope.launch {
            _state.update { it.copy(loadingMore = true) }
            try {
                val page = repo.listingsPage(next)
                _state.update { s ->
                    val known = s.items.map { it.id }.toSet()
                    s.copy(items = s.items + page.items.filter { it.id !in known }, next = page.next, loadingMore = false)
                }
            } catch (e: ApiException) {
                _state.update { it.copy(loadingMore = false) }
            }
        }
    }

    fun toggleLike(listing: Listing, onNeedsLogin: () -> Unit) {
        if (!session.loggedIn.value) {
            onNeedsLogin()
            return
        }
        val wantLiked = !listing.is_liked
        replace(listing.id) { it.copy(is_liked = wantLiked, likes_count = (it.likes_count + if (wantLiked) 1 else -1).coerceAtLeast(0)) }
        viewModelScope.launch {
            try {
                repo.setLiked(listing.id, wantLiked)
            } catch (e: ApiException) {
                replace(listing.id) { listing }   // roll back
                _state.update { it.copy(message = e.message) }
            }
        }
    }

    fun messageShown() = _state.update { it.copy(message = null) }

    private fun replace(id: Int, transform: (Listing) -> Listing) = _state.update { s ->
        s.copy(items = s.items.map { if (it.id == id) transform(it) else it })
    }
}

@Composable
fun FeedScreen(
    onOpenListing: (Int) -> Unit,
    onOpenSeller: (Listing) -> Unit,
    onSell: () -> Unit,
    onNotifications: () -> Unit,
    onProfile: () -> Unit,
    onNeedsLogin: () -> Unit,
    showMessage: (String) -> Unit,
) {
    val repo = LocalRepository.current
    val session = LocalSession.current
    val vm = rememberVm { FeedViewModel(repo, session) }
    val state by vm.state.collectAsState()
    val unread by session.unreadNotifications.collectAsState()
    val listState = rememberLazyListState()
    var selectedCategory by remember { mutableStateOf<Int?>(null) }
    val context = androidx.compose.ui.platform.LocalContext.current

    LaunchedEffect(state.message) {
        state.message?.let { showMessage(it); vm.messageShown() }
    }
    LaunchedEffect(listState, state.items.size) {
        snapshotFlow { listState.layoutInfo.visibleItemsInfo.lastOrNull()?.index ?: 0 }
            .collect { last -> if (state.items.isNotEmpty() && last >= state.items.size - 2) vm.loadMore() }
    }

    Box(Modifier.fillMaxSize()) {
        androidx.compose.foundation.layout.Column(Modifier.fillMaxSize()) {
            // Top bar: wordmark left, bell right.
            Row(
                Modifier.fillMaxWidth().statusBarsPadding().height(56.dp).padding(horizontal = 16.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                val dark = LocalIsDark.current
                Image(
                    painterResource(if (dark) R.drawable.brand_mark_white else R.drawable.brand_mark_navy),
                    contentDescription = null,
                    modifier = Modifier.height(26.dp).aspectRatio(452f / 364f),
                )
                Image(
                    painterResource(if (dark) R.drawable.brand_wordmark_white else R.drawable.brand_wordmark_navy),
                    contentDescription = "Choropia",
                    modifier = Modifier.padding(start = 10.dp).height(15.dp).aspectRatio(463f / 104f),
                )
                Box(Modifier.weight(1f))
                IconButton(onClick = onProfile) {
                    Icon(Icons.Outlined.PersonOutline, contentDescription = "Profile")
                }
                IconButton(onClick = onNotifications) {
                    BadgedBox(badge = { if (unread > 0) Badge { Text(if (unread > 9) "9+" else unread.toString()) } }) {
                        Icon(Icons.Outlined.NotificationsNone, contentDescription = "Notifications")
                    }
                }
            }

            when {
                state.loading -> ScreenLoader()
                state.error != null -> ErrorState(state.error ?: "", onRetry = { vm.load(initial = true) }, modifier = Modifier.fillMaxSize())
                else -> BrandPullToRefresh(
                    refreshing = state.refreshing,
                    onRefresh = { vm.load() },
                    modifier = Modifier.fillMaxSize(),
                ) {
                    LazyColumn(
                        state = listState,
                        modifier = Modifier.fillMaxSize(),
                        contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 4.dp, bottom = 24.dp),
                        verticalArrangement = Arrangement.spacedBy(14.dp),
                    ) {
                        item(key = "composer") {
                            SurfaceCard(Modifier.fillMaxWidth(), onClick = onSell) {
                                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                                    Icon(Icons.Outlined.AddCircleOutline, null, tint = MaterialTheme.colorScheme.onSurfaceVariant)
                                    Text(
                                        "Post something for sale or a service you offer…",
                                        style = MaterialTheme.typography.bodyMedium,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    )
                                }
                            }
                        }
                        // Category chips (only categories that actually appear in the feed).
                        val presentCategories = state.items.map { it.category }.distinct()
                            .filter { state.categories.containsKey(it) }
                        if (presentCategories.size > 1) {
                            item(key = "chips") {
                                LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                    item { Chip("All", selectedCategory == null, { selectedCategory = null }) }
                                    items(presentCategories.size) { index ->
                                        val id = presentCategories[index]
                                        Chip(state.categories[id].orEmpty(), selectedCategory == id, { selectedCategory = id })
                                    }
                                }
                            }
                        }
                        val visibleItems = state.items.filter { selectedCategory == null || it.category == selectedCategory }
                        if (visibleItems.isEmpty()) {
                            item(key = "empty") {
                                EmptyState(
                                    icon = Icons.Outlined.Inventory2,
                                    title = "Nothing here yet",
                                    message = "Be the first to post a listing, or pull down to refresh.",
                                    actionLabel = "Post a listing",
                                    onAction = onSell,
                                )
                            }
                        }
                        items(visibleItems, key = { it.id }) { listing ->
                            PostCard(
                                listing = listing,
                                categoryName = state.categories[listing.category],
                                onOpen = { onOpenListing(listing.id) },
                                onLike = { vm.toggleLike(listing, onNeedsLogin) },
                                onSeller = { onOpenSeller(listing) },
                                onBuy = { onOpenListing(listing.id) },
                                onShare = { com.choropia.app.ui.util.shareListing(context, listing) },
                            )
                        }
                        if (state.loadingMore) {
                            item(key = "more") {
                                Box(Modifier.fillMaxWidth().padding(12.dp), contentAlignment = Alignment.Center) {
                                    BrandLoader(style = LoaderStyle.Light, markSize = 36.dp)
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
