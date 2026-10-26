package com.choropia.app.ui.screens

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
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.GridItemSpan
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.lazy.grid.rememberLazyGridState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Close
import androidx.compose.material.icons.outlined.Search
import androidx.compose.material.icons.outlined.SearchOff
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.snapshotFlow
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.choropia.app.data.model.Category
import com.choropia.app.data.model.Listing
import com.choropia.app.data.network.ApiException
import com.choropia.app.data.repository.ChoropiaRepository
import com.choropia.app.data.repository.ListingQuery
import com.choropia.app.ui.LocalRepository
import com.choropia.app.ui.components.BrandLoader
import com.choropia.app.ui.components.BrandPullToRefresh
import com.choropia.app.ui.components.Chip
import com.choropia.app.ui.components.EmptyState
import com.choropia.app.ui.components.ErrorState
import com.choropia.app.ui.components.GridListingCard
import com.choropia.app.ui.components.LoaderStyle
import com.choropia.app.ui.components.ScreenLoader
import com.choropia.app.ui.rememberVm
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class MarketState(
    val items: List<Listing> = emptyList(),
    val categories: List<Category> = emptyList(),
    val search: String = "",
    val categorySlug: String? = null,
    val ordering: String = "-created_at",
    val condition: String? = null,
    val minPrice: String = "",
    val maxPrice: String = "",
    val loading: Boolean = true,
    val refreshing: Boolean = false,
    val loadingMore: Boolean = false,
    val next: String? = null,
    val error: String? = null,
)

class MarketplaceViewModel(private val repo: ChoropiaRepository) : ViewModel() {
    private val _state = MutableStateFlow(MarketState())
    val state: StateFlow<MarketState> = _state.asStateFlow()
    private var searchJob: Job? = null
    private var loadJob: Job? = null

    init {
        viewModelScope.launch {
            runCatching { repo.categories() }.onSuccess { cats ->
                _state.update { it.copy(categories = cats.filter { c -> c.parent == null }) }
            }
        }
        load(initial = true)
    }

    private fun query(s: MarketState) = ListingQuery(
        search = s.search.ifBlank { null },
        categorySlug = s.categorySlug,
        ordering = s.ordering,
        condition = s.condition,
        minPrice = s.minPrice.ifBlank { null },
        maxPrice = s.maxPrice.ifBlank { null },
    )

    fun load(initial: Boolean = false) {
        loadJob?.cancel()
        loadJob = viewModelScope.launch {
            _state.update { it.copy(loading = initial, refreshing = !initial, error = null) }
            try {
                val page = repo.listings(query(_state.value))
                _state.update { it.copy(items = page.items, next = page.next, loading = false, refreshing = false) }
            } catch (e: ApiException) {
                _state.update { it.copy(loading = false, refreshing = false, error = e.message) }
            }
        }
    }

    fun setSearch(text: String) {
        _state.update { it.copy(search = text) }
        searchJob?.cancel()
        searchJob = viewModelScope.launch {
            delay(400)
            load(initial = true)
        }
    }

    fun submitSearch() {
        searchJob?.cancel()
        load(initial = true)
    }

    fun setCategory(slug: String?) {
        _state.update { it.copy(categorySlug = slug) }
        load(initial = true)
    }

    fun setFilters(condition: String?, minPrice: String, maxPrice: String) {
        _state.update { it.copy(condition = condition, minPrice = minPrice, maxPrice = maxPrice) }
        load(initial = true)
    }

    fun setOrdering(ordering: String) {
        _state.update { it.copy(ordering = ordering) }
        load(initial = true)
    }

    fun loadMore() {
        val current = _state.value
        val next = current.next ?: return
        if (current.loadingMore || current.loading || current.refreshing) return
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
}

private val sortOptions = listOf(
    "Newest" to "-created_at",
    "Price: low to high" to "price",
    "Price: high to low" to "-price",
    "Most viewed" to "-views_count",
)

@Composable
fun MarketplaceScreen(onOpenListing: (Int) -> Unit) {
    val repo = LocalRepository.current
    val vm = rememberVm { MarketplaceViewModel(repo) }
    val state by vm.state.collectAsState()
    val gridState = rememberLazyGridState()

    LaunchedEffect(gridState, state.items.size) {
        snapshotFlow { gridState.layoutInfo.visibleItemsInfo.lastOrNull()?.index ?: 0 }
            .collect { last -> if (state.items.isNotEmpty() && last >= state.items.size - 3) vm.loadMore() }
    }

    Column(Modifier.fillMaxSize().statusBarsPadding()) {
        Text(
            "Marketplace",
            style = MaterialTheme.typography.headlineSmall,
            modifier = Modifier.padding(start = 16.dp, end = 16.dp, top = 12.dp, bottom = 10.dp),
        )
        OutlinedTextField(
            value = state.search,
            onValueChange = vm::setSearch,
            placeholder = { Text("Search phones, fashion, services…") },
            leadingIcon = { Icon(Icons.Outlined.Search, null) },
            trailingIcon = if (state.search.isNotEmpty()) {
                { IconButton(onClick = { vm.setSearch("") }) { Icon(Icons.Outlined.Close, "Clear search") } }
            } else null,
            singleLine = true,
            shape = RoundedCornerShape(50),
            keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
            keyboardActions = KeyboardActions(onSearch = { vm.submitSearch() }),
            colors = OutlinedTextFieldDefaults.colors(
                focusedBorderColor = MaterialTheme.colorScheme.primary,
                unfocusedBorderColor = MaterialTheme.colorScheme.outlineVariant,
                unfocusedContainerColor = MaterialTheme.colorScheme.surfaceContainerLowest,
                focusedContainerColor = MaterialTheme.colorScheme.surfaceContainerLowest,
            ),
            modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp),
        )

        LazyRow(
            contentPadding = PaddingValues(horizontal = 16.dp, vertical = 12.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            item { Chip("All", state.categorySlug == null, { vm.setCategory(null) }) }
            items(state.categories.size) { index ->
                val category = state.categories[index]
                Chip(category.name, state.categorySlug == category.slug, { vm.setCategory(category.slug) })
            }
        }

        var sortOpen by remember { mutableStateOf(false) }
        var filtersOpen by remember { mutableStateOf(false) }
        val activeFilters = listOf(
            state.condition != null,
            state.minPrice.isNotBlank(),
            state.maxPrice.isNotBlank(),
        ).count { it }
        Row(
            Modifier.fillMaxWidth().padding(horizontal = 16.dp).padding(bottom = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                if (state.loading) "Loading…" else "${state.items.size}${if (state.next != null) "+" else ""} listings",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.weight(1f),
            )
            Chip(
                if (activeFilters > 0) "Filters ($activeFilters)" else "Filters",
                selected = activeFilters > 0,
                onClick = { filtersOpen = true },
                modifier = Modifier.padding(end = 8.dp),
            )
            Box {
                Chip(
                    sortOptions.firstOrNull { it.second == state.ordering }?.first ?: "Sort",
                    selected = false,
                    onClick = { sortOpen = true },
                )
                androidx.compose.material3.DropdownMenu(expanded = sortOpen, onDismissRequest = { sortOpen = false }) {
                    sortOptions.forEach { (label, value) ->
                        androidx.compose.material3.DropdownMenuItem(
                            text = { Text(label) },
                            onClick = { sortOpen = false; vm.setOrdering(value) },
                        )
                    }
                }
            }
        }

        if (filtersOpen) {
            FilterSheet(
                condition = state.condition,
                minPrice = state.minPrice,
                maxPrice = state.maxPrice,
                onDismiss = { filtersOpen = false },
                onApply = { c, lo, hi -> filtersOpen = false; vm.setFilters(c, lo, hi) },
            )
        }
        when {
            state.loading -> ScreenLoader()
            state.error != null -> ErrorState(state.error ?: "", { vm.load(initial = true) }, Modifier.fillMaxSize())
            else -> BrandPullToRefresh(
                refreshing = state.refreshing,
                onRefresh = { vm.load() },
                modifier = Modifier.fillMaxSize(),
            ) {
                LazyVerticalGrid(
                    state = gridState,
                    columns = GridCells.Fixed(2),
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 4.dp, bottom = 24.dp),
                    horizontalArrangement = Arrangement.spacedBy(12.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    if (state.items.isEmpty()) {
                        item(span = { GridItemSpan(maxLineSpan) }) {
                            EmptyState(
                                icon = Icons.Outlined.SearchOff,
                                title = "No listings found",
                                message = "Try a different search or category.",
                            )
                        }
                    }
                    items(state.items, key = { it.id }) { listing ->
                        GridListingCard(listing, onClick = { onOpenListing(listing.id) })
                    }
                    if (state.loadingMore) {
                        item(span = { GridItemSpan(maxLineSpan) }) {
                            Box(Modifier.fillMaxWidth().height(64.dp), contentAlignment = Alignment.Center) {
                                BrandLoader(style = LoaderStyle.Light, markSize = 36.dp)
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun FilterSheet(
    condition: String?,
    minPrice: String,
    maxPrice: String,
    onDismiss: () -> Unit,
    onApply: (String?, String, String) -> Unit,
) {
    var cond by remember { mutableStateOf(condition) }
    var lo by remember { mutableStateOf(minPrice) }
    var hi by remember { mutableStateOf(maxPrice) }
    androidx.compose.material3.ModalBottomSheet(onDismissRequest = onDismiss) {
        Column(
            Modifier.padding(horizontal = 20.dp).padding(bottom = 28.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Text("Filters", style = MaterialTheme.typography.titleLarge)
            Text("Condition", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Chip("Any", cond == null, { cond = null })
                Chip("New", cond == "new", { cond = "new" })
                Chip("Used", cond == "used", { cond = "used" })
            }
            Text("Price (₦)", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                OutlinedTextField(
                    value = lo,
                    onValueChange = { lo = it.filter { c -> c.isDigit() } },
                    label = { Text("Min") },
                    singleLine = true,
                    modifier = Modifier.weight(1f),
                )
                OutlinedTextField(
                    value = hi,
                    onValueChange = { hi = it.filter { c -> c.isDigit() } },
                    label = { Text("Max") },
                    singleLine = true,
                    modifier = Modifier.weight(1f),
                )
            }
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                androidx.compose.material3.OutlinedButton(
                    onClick = { onApply(null, "", "") },
                    modifier = Modifier.weight(1f),
                ) { Text("Reset") }
                androidx.compose.material3.Button(
                    onClick = { onApply(cond, lo, hi) },
                    modifier = Modifier.weight(1f),
                ) { Text("Apply") }
            }
        }
    }
}
