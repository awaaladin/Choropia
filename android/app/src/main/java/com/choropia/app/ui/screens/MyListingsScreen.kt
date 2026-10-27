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
import androidx.compose.material.icons.outlined.Sell
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
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.choropia.app.data.model.Listing
import com.choropia.app.data.network.ApiException
import com.choropia.app.data.repository.ChoropiaRepository
import com.choropia.app.data.repository.ListingQuery
import com.choropia.app.ui.LocalRepository
import com.choropia.app.ui.components.BrandPullToRefresh
import com.choropia.app.ui.components.Chip
import com.choropia.app.ui.components.EmptyState
import com.choropia.app.ui.components.ErrorState
import com.choropia.app.ui.components.GridListingCard
import com.choropia.app.ui.components.ScreenLoader
import com.choropia.app.ui.rememberVm
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class MyListingsState(
    val items: List<Listing> = emptyList(),
    val loading: Boolean = true,
    val refreshing: Boolean = false,
    val error: String? = null,
)

/** The signed-in user's own listings, active and sold (`GET /listings/?mine=true`). */
class MyListingsViewModel(private val repo: ChoropiaRepository) : ViewModel() {
    private val _state = MutableStateFlow(MyListingsState())
    val state: StateFlow<MyListingsState> = _state.asStateFlow()

    init {
        load(initial = true)
    }

    fun load(initial: Boolean = false) {
        viewModelScope.launch {
            _state.update { it.copy(loading = initial && it.items.isEmpty(), refreshing = !initial, error = null) }
            try {
                val page = repo.listings(ListingQuery(mine = true, ordering = "-created_at"))
                _state.update { it.copy(items = page.items, loading = false, refreshing = false) }
            } catch (e: ApiException) {
                _state.update { it.copy(loading = false, refreshing = false, error = e.message) }
            }
        }
    }
}

@Composable
fun MyListingsScreen(onBack: () -> Unit, onOpenListing: (Int) -> Unit, onSell: () -> Unit, onDelivery: (Int) -> Unit = {}) {
    val repo = LocalRepository.current
    val vm = rememberVm { MyListingsViewModel(repo) }
    val state by vm.state.collectAsState()
    var tab by remember { mutableIntStateOf(0) }   // 0 active, 1 sold

    val visible = state.items.filter { if (tab == 0) it.status == "active" else it.status == "sold" }

    Column(Modifier.fillMaxSize().statusBarsPadding()) {
        Row(Modifier.height(56.dp).padding(horizontal = 4.dp), verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Outlined.ArrowBack, "Back") }
            Text("My listings", style = MaterialTheme.typography.titleLarge)
        }
        Row(Modifier.padding(horizontal = 16.dp, vertical = 6.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Chip("Active (${state.items.count { it.status == "active" }})", tab == 0, { tab = 0 })
            Chip("Sold (${state.items.count { it.status == "sold" }})", tab == 1, { tab = 1 })
        }
        when {
            state.loading -> ScreenLoader()
            state.error != null -> ErrorState(state.error ?: "", { vm.load(initial = true) }, Modifier.fillMaxSize())
            else -> BrandPullToRefresh(state.refreshing, { vm.load() }, Modifier.fillMaxSize()) {
                LazyVerticalGrid(
                    columns = GridCells.Fixed(2),
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(16.dp),
                    horizontalArrangement = Arrangement.spacedBy(12.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    if (visible.isEmpty()) {
                        item(span = { GridItemSpan(maxLineSpan) }) {
                            EmptyState(
                                icon = Icons.Outlined.Sell,
                                title = if (tab == 0) "No active listings" else "Nothing sold yet",
                                message = if (tab == 0) "Post something for sale and it will show up here." else "Items you mark as sold will be listed here.",
                                actionLabel = if (tab == 0) "Post a listing" else null,
                                onAction = if (tab == 0) onSell else null,
                            )
                        }
                    }
                    items(visible, key = { it.id }) { listing ->
                        Column {
                            GridListingCard(listing, onClick = { onOpenListing(listing.id) })
                            if (listing.status == "active") {
                                androidx.compose.material3.TextButton(onClick = { onDelivery(listing.id) }) { Text("Delivery options") }
                            }
                        }
                    }
                }
            }
        }
    }
}
