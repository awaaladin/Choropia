package com.choropia.app.ui.screens.feed

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
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
import com.choropia.app.data.model.Listing
import com.choropia.app.data.repository.ChoropiaRepository

@Composable
fun FeedScreen(
    repository: ChoropiaRepository,
    onOpenListing: (Int) -> Unit,
    onNeedsLogin: () -> Unit,
    onOpenMarketplace: () -> Unit = {},
    onOpenNotifications: () -> Unit = {},
    onOpenOrders: () -> Unit = {},
    onOpenProfile: () -> Unit = {},
) {
    var listings by remember { mutableStateOf<List<Listing>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf<String?>(null) }
    var loggedIn by remember { mutableStateOf(false) }

    LaunchedEffect(Unit) {
        loggedIn = repository.getAccessTokenOrNull() != null
        try {
            listings = repository.feedOrListings(loggedIn)
        } catch (e: Exception) {
            error = e.message
        } finally {
            loading = false
        }
    }

    var moreMenuOpen by remember { mutableStateOf(false) }

    Scaffold(topBar = {
        TopAppBar(
            title = { Text("Choropia") },
            actions = {
                TextButton(onClick = onOpenMarketplace) { Text("Marketplace") }
                if (loggedIn) {
                    TextButton(onClick = onOpenNotifications) { Text("Alerts") }
                    TextButton(onClick = { moreMenuOpen = true }) { Text("More") }
                    DropdownMenu(expanded = moreMenuOpen, onDismissRequest = { moreMenuOpen = false }) {
                        DropdownMenuItem(text = { Text("Orders") }, onClick = { moreMenuOpen = false; onOpenOrders() })
                        DropdownMenuItem(text = { Text("Profile") }, onClick = { moreMenuOpen = false; onOpenProfile() })
                    }
                } else {
                    TextButton(onClick = onNeedsLogin) { Text("Log in") }
                }
            },
        )
    }) { padding ->
        when {
            loading -> Column(
                Modifier.fillMaxSize().padding(padding),
                verticalArrangement = Arrangement.Center,
                horizontalAlignment = Alignment.CenterHorizontally,
            ) { CircularProgressIndicator() }

            error != null -> Text(
                "Could not load listings: $error",
                color = MaterialTheme.colorScheme.error,
                modifier = Modifier.padding(padding).padding(16.dp),
            )

            listings.isEmpty() -> Text("No listings yet.", modifier = Modifier.padding(padding).padding(16.dp))

            else -> LazyVerticalGrid(
                columns = GridCells.Fixed(2),
                contentPadding = PaddingValues(12.dp),
                modifier = Modifier.padding(padding),
            ) {
                items(listings) { listing ->
                    ListingCard(listing, onClick = { onOpenListing(listing.id) })
                }
            }
        }
    }
}

@Composable
private fun ListingCard(listing: Listing, onClick: () -> Unit) {
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
