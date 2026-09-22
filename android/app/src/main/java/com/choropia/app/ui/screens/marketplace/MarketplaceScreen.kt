package com.choropia.app.ui.screens.marketplace

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
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
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import com.choropia.app.data.model.Category
import com.choropia.app.data.model.Listing
import com.choropia.app.data.repository.ChoropiaRepository

@Composable
fun MarketplaceScreen(repository: ChoropiaRepository, onOpenListing: (Int) -> Unit, onCreateListing: () -> Unit) {
    var listings by remember { mutableStateOf<List<Listing>>(emptyList()) }
    var categories by remember { mutableStateOf<List<Category>>(emptyList()) }
    var selectedCategory by remember { mutableStateOf<Category?>(null) }
    var loading by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf<String?>(null) }
    var categoryMenuOpen by remember { mutableStateOf(false) }

    suspend fun reload() {
        loading = true
        try {
            listings = repository.listListings(selectedCategory?.slug)
        } catch (e: Exception) {
            error = e.message
        } finally {
            loading = false
        }
    }

    LaunchedEffect(Unit) {
        categories = runCatching { repository.listCategories() }.getOrDefault(emptyList())
        reload()
    }

    Scaffold(topBar = {
        TopAppBar(
            title = { Text("Marketplace") },
            actions = { TextButton(onClick = onCreateListing) { Text("Sell") } },
        )
    }) { padding ->
        Column(Modifier.padding(padding)) {
            Row(
                modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text("Category: ${selectedCategory?.name ?: "All"}", modifier = Modifier.clickable { categoryMenuOpen = true })
                DropdownMenu(expanded = categoryMenuOpen, onDismissRequest = { categoryMenuOpen = false }) {
                    DropdownMenuItem(text = { Text("All") }, onClick = {
                        selectedCategory = null
                        categoryMenuOpen = false
                    })
                    categories.forEach { category ->
                        DropdownMenuItem(text = { Text(category.name) }, onClick = {
                            selectedCategory = category
                            categoryMenuOpen = false
                        })
                    }
                }
            }
            LaunchedEffect(selectedCategory) { reload() }

            when {
                loading -> Column(
                    Modifier.fillMaxSize(),
                    verticalArrangement = Arrangement.Center,
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) { CircularProgressIndicator() }

                error != null -> Text(
                    "Could not load listings: $error",
                    color = MaterialTheme.colorScheme.error,
                    modifier = Modifier.padding(16.dp),
                )

                listings.isEmpty() -> Text("No listings match this filter.", modifier = Modifier.padding(16.dp))

                else -> LazyVerticalGrid(columns = GridCells.Fixed(2), contentPadding = PaddingValues(12.dp)) {
                    items(listings) { listing ->
                        MarketplaceListingCard(listing, onClick = { onOpenListing(listing.id) })
                    }
                }
            }
        }
    }
}

@Composable
private fun MarketplaceListingCard(listing: Listing, onClick: () -> Unit) {
    Column(
        modifier = Modifier
            .padding(6.dp)
            .clickable(onClick = onClick)
            .background(MaterialTheme.colorScheme.surfaceVariant)
            .fillMaxWidth()
            .padding(8.dp),
    ) {
        listing.cover_photo?.let {
            AsyncImage(model = it, contentDescription = listing.title, modifier = Modifier.fillMaxWidth())
        }
        Text(listing.title, style = MaterialTheme.typography.titleSmall, maxLines = 1)
        Text("₦${listing.price}", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.primary)
        Text(listing.condition, style = MaterialTheme.typography.bodySmall)
    }
}
