package com.choropia.app.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.GridItemSpan
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material.icons.outlined.BookmarkBorder
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.choropia.app.data.model.Listing
import com.choropia.app.data.repository.ChoropiaRepository
import com.choropia.app.ui.LocalRepository
import com.choropia.app.ui.components.BrandPullToRefresh
import com.choropia.app.ui.components.EmptyState
import com.choropia.app.ui.components.GridListingCard
import com.choropia.app.ui.components.ScreenLoader
import com.choropia.app.ui.rememberVm
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class WatchlistState(
    val items: List<Listing> = emptyList(),
    val loading: Boolean = true,
    val refreshing: Boolean = false,
)

/**
 * The saved-listings screen. Bookmarks are device-level (see TokenManager.savedIdsFlow); this
 * screen resolves each saved id to its current listing so price and status are always fresh.
 */
class WatchlistViewModel(private val repo: ChoropiaRepository) : ViewModel() {
    private val _state = MutableStateFlow(WatchlistState())
    val state: StateFlow<WatchlistState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            // Re-resolve whenever the set of saved ids changes (e.g. after un-saving elsewhere).
            repo.savedIdsFlow.collect { ids -> load(ids, initial = _state.value.items.isEmpty()) }
        }
    }

    private suspend fun load(ids: Set<Int>, initial: Boolean) {
        _state.update { it.copy(loading = initial, refreshing = !initial) }
        val listings = repo.savedListings(ids).sortedByDescending { it.created_at ?: "" }
        _state.update { it.copy(items = listings, loading = false, refreshing = false) }
    }

    fun refresh() {
        viewModelScope.launch {
            // Pull-to-refresh: read the current ids once and re-fetch.
            val ids = _state.value.items.map { it.id }.toSet()
            load(ids, initial = false)
        }
    }
}

@Composable
fun WatchlistScreen(onBack: () -> Unit, onOpenListing: (Int) -> Unit) {
    val repo = LocalRepository.current
    val vm = rememberVm { WatchlistViewModel(repo) }
    val state by vm.state.collectAsState()

    Column(Modifier.fillMaxSize().statusBarsPadding()) {
        Row(Modifier.height(56.dp).padding(horizontal = 4.dp), verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Outlined.ArrowBack, "Back") }
            Text("Watchlist", style = MaterialTheme.typography.titleLarge)
        }
        if (state.loading) {
            ScreenLoader()
        } else {
            BrandPullToRefresh(state.refreshing, { vm.refresh() }, Modifier.fillMaxSize()) {
                LazyVerticalGrid(
                    columns = GridCells.Fixed(2),
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(16.dp),
                    horizontalArrangement = Arrangement.spacedBy(12.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    if (state.items.isEmpty()) {
                        item(span = { GridItemSpan(maxLineSpan) }) {
                            EmptyState(
                                icon = Icons.Outlined.BookmarkBorder,
                                title = "Nothing saved yet",
                                message = "Tap the bookmark on any listing to keep it here so you can find it again.",
                            )
                        }
                    }
                    items(state.items, key = { it.id }) { listing ->
                        GridListingCard(listing, onClick = { onOpenListing(listing.id) })
                    }
                }
            }
        }
    }
}
