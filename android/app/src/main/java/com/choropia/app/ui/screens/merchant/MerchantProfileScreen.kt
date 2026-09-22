package com.choropia.app.ui.screens.merchant

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
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
import com.choropia.app.data.model.Listing
import com.choropia.app.data.model.Merchant
import com.choropia.app.data.model.Review
import com.choropia.app.data.repository.ChoropiaRepository
import kotlinx.coroutines.launch

@Composable
fun MerchantProfileScreen(
    merchantId: Int,
    repository: ChoropiaRepository,
    onOpenListing: (Int) -> Unit,
    onNeedsLogin: () -> Unit = {},
) {
    var merchant by remember { mutableStateOf<Merchant?>(null) }
    var listings by remember { mutableStateOf<List<Listing>>(emptyList()) }
    var reviews by remember { mutableStateOf<List<Review>>(emptyList()) }
    var isFollowing by remember { mutableStateOf(false) }
    var myFollowId by remember { mutableStateOf<Int?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    suspend fun reload() {
        try {
            val current = repository.getMerchant(merchantId)
            merchant = current
            listings = repository.listMerchantListings(merchantId)
            reviews = runCatching { repository.listReviewsFor(current.owner_id) }.getOrDefault(emptyList())

            if (repository.getAccessTokenOrNull() != null) {
                val mine = runCatching { repository.listMyFollows() }.getOrDefault(emptyList())
                val existing = mine.find { it.target_type_display == "merchant" && it.object_id == merchantId }
                isFollowing = existing != null
                myFollowId = existing?.id
            }
        } catch (e: Exception) {
            error = e.message
        }
    }

    LaunchedEffect(merchantId) { reload() }

    Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {
        when {
            error != null -> Text("Could not load storefront: $error", color = MaterialTheme.colorScheme.error)
            merchant == null -> CircularProgressIndicator()
            else -> {
                val current = merchant!!
                Row {
                    current.logo?.let {
                        AsyncImage(model = it, contentDescription = current.business_name, modifier = Modifier.padding(end = 12.dp))
                    }
                    Column {
                        Text(current.business_name, style = MaterialTheme.typography.headlineSmall)
                        Text(current.location, style = MaterialTheme.typography.bodySmall)
                        val avg = if (reviews.isNotEmpty()) reviews.map { it.rating }.average() else null
                        Text(
                            "${current.followers_count} followers" +
                                (avg?.let { " · %.1f★ (%d)".format(it, reviews.size) } ?: ""),
                            style = MaterialTheme.typography.bodySmall,
                        )
                    }
                }

                val followAction: () -> Unit = {
                    scope.launch {
                        if (repository.getAccessTokenOrNull() == null) {
                            onNeedsLogin()
                            return@launch
                        }
                        try {
                            if (isFollowing) {
                                myFollowId?.let { repository.unfollow(it) }
                            } else {
                                repository.follow("merchant", merchantId)
                            }
                            reload()
                        } catch (e: Exception) {
                            error = e.message
                        }
                    }
                }
                if (isFollowing) {
                    OutlinedButton(onClick = followAction, modifier = Modifier.padding(top = 8.dp)) { Text("Following") }
                } else {
                    Button(onClick = followAction, modifier = Modifier.padding(top = 8.dp)) { Text("Follow") }
                }

                Text(current.description, modifier = Modifier.padding(top = 12.dp))
                Text("Listings", style = MaterialTheme.typography.titleSmall, modifier = Modifier.padding(top = 16.dp))

                if (listings.isEmpty()) {
                    Text("No listings yet.", modifier = Modifier.padding(top = 8.dp))
                } else {
                    LazyVerticalGrid(columns = GridCells.Fixed(2), contentPadding = PaddingValues(top = 8.dp)) {
                        items(listings) { listing ->
                            Column(
                                modifier = Modifier
                                    .padding(6.dp)
                                    .clickable { onOpenListing(listing.id) }
                                    .background(MaterialTheme.colorScheme.surfaceVariant)
                                    .fillMaxWidth()
                                    .padding(8.dp),
                            ) {
                                listing.cover_photo?.let {
                                    AsyncImage(model = it, contentDescription = listing.title, modifier = Modifier.fillMaxWidth())
                                }
                                Text(listing.title, style = MaterialTheme.typography.titleSmall, maxLines = 1)
                                Text("₦${listing.price}", color = MaterialTheme.colorScheme.primary)
                            }
                        }
                    }
                }

                Text("Reviews", style = MaterialTheme.typography.titleSmall, modifier = Modifier.padding(top = 16.dp))
                if (reviews.isEmpty()) {
                    Text("No reviews yet.", modifier = Modifier.padding(top = 4.dp))
                } else {
                    reviews.forEach { review ->
                        Column(modifier = Modifier.padding(top = 6.dp)) {
                            Text("★".repeat(review.rating) + "☆".repeat(5 - review.rating), color = MaterialTheme.colorScheme.primary)
                            if (review.comment.isNotBlank()) Text(review.comment, style = MaterialTheme.typography.bodySmall)
                        }
                    }
                }
            }
        }
    }
}
