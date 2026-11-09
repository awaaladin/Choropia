package com.choropia.app.ui.screens

import android.media.MediaPlayer
import android.net.Uri
import android.widget.VideoView
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.material.icons.outlined.Add
import androidx.compose.material.icons.outlined.Share
import androidx.compose.material.icons.outlined.BookmarkBorder
import androidx.compose.material.icons.filled.Bookmark
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.pager.VerticalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.outlined.ChatBubbleOutline
import androidx.compose.material.icons.outlined.FavoriteBorder
import androidx.compose.material.icons.outlined.PlayCircleOutline
import androidx.compose.material.icons.outlined.ShoppingBag
import androidx.compose.material3.Icon
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.TextButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.snapshotFlow
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import coil.compose.AsyncImage
import com.choropia.app.data.model.Listing
import com.choropia.app.data.model.Reel
import com.choropia.app.data.network.ApiException
import com.choropia.app.data.repository.ChoropiaRepository
import com.choropia.app.data.repository.ListingQuery
import com.choropia.app.session.Session
import com.choropia.app.ui.LocalRepository
import com.choropia.app.ui.LocalSession
import com.choropia.app.ui.components.Avatar
import com.choropia.app.ui.components.EmptyState
import com.choropia.app.ui.components.ErrorState
import com.choropia.app.ui.components.ScreenLoader
import com.choropia.app.ui.rememberVm
import com.choropia.app.ui.theme.MoneyStyle
import com.choropia.app.ui.util.formatNaira
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class ReelsState(
    val items: List<Listing> = emptyList(),
    val reels: List<Reel> = emptyList(),
    val loading: Boolean = true,
    val error: String? = null,
    val next: String? = null,
    val reelsNext: String? = null,
    val loadingMore: Boolean = false,
    val uploading: Boolean = false,
    val uploadError: String? = null,
    val ownedListings: List<Listing> = emptyList(),
)

class ReelsViewModel(private val repo: ChoropiaRepository, private val session: Session) : ViewModel() {
    private val _state = MutableStateFlow(ReelsState())
    val state: StateFlow<ReelsState> = _state.asStateFlow()

    init {
        load()
    }

    fun load() {
        viewModelScope.launch {
            _state.update { it.copy(loading = true, error = null) }
            try {
                val reelPage = repo.reels()
                if (reelPage.items.isNotEmpty()) {
                    _state.update { it.copy(reels = reelPage.items, reelsNext = reelPage.next, items = emptyList(), next = null, loading = false) }
                } else {
                    val page = repo.listings(ListingQuery(ordering = "-created_at"))
                    val visualListings = page.items.filter { it.cover_photo != null || it.photos.isNotEmpty() }
                        .sortedByDescending { it.cover_photo != null }
                    _state.update { it.copy(reels = emptyList(), reelsNext = null, items = visualListings, next = page.next, loading = false) }
                }
            } catch (e: ApiException) {
                _state.update { it.copy(loading = false, error = e.message) }
            }
        }
    }

    fun loadMore() {
        val s = _state.value
        if (s.loadingMore) return
        if (s.reels.isNotEmpty() && s.reelsNext == null) return
        if (s.reels.isEmpty() && s.next == null) return
        viewModelScope.launch {
            _state.update { it.copy(loadingMore = true) }
            try {
                if (s.reels.isNotEmpty()) {
                    val next = s.reelsNext ?: return@launch
                    val page = repo.reelsPage(next)
                    _state.update { cur ->
                        val known = cur.reels.map { it.id }.toSet()
                        cur.copy(reels = cur.reels + page.items.filter { it.id !in known }, reelsNext = page.next, loadingMore = false)
                    }
                } else {
                    val next = s.next ?: return@launch
                    val page = repo.listingsPage(next)
                    _state.update { cur ->
                        val known = cur.items.map { it.id }.toSet()
                        val visualListings = page.items.filter { (it.cover_photo != null || it.photos.isNotEmpty()) && it.id !in known }
                        cur.copy(items = cur.items + visualListings, next = page.next, loadingMore = false)
                    }
                }
            } catch (e: Exception) {
                _state.update { it.copy(loadingMore = false) }
            }
        }
    }

    fun loadOwnedListings() {
        viewModelScope.launch {
            runCatching { repo.listings(ListingQuery(mine = true)).items }
                .onSuccess { listings -> _state.update { it.copy(ownedListings = listings) } }
        }
    }

    fun clearUploadError() {
        _state.update { it.copy(uploadError = null) }
    }

    fun createReel(uri: Uri, caption: String, listingId: Int?, onPosted: () -> Unit) {
        if (_state.value.uploading) return
        viewModelScope.launch {
            _state.update { it.copy(uploading = true, uploadError = null) }
            try {
                val reel = repo.createReel(uri, caption, listingId)
                _state.update { it.copy(reels = listOf(reel) + it.reels.filterNot { old -> old.id == reel.id }, uploading = false) }
                onPosted()
            } catch (e: Exception) {
                _state.update { it.copy(uploading = false, uploadError = e.message ?: "Could not upload this reel.") }
            }
        }
    }

    fun toggleLike(listing: Listing, onNeedsLogin: () -> Unit) {
        if (!session.loggedIn.value) return onNeedsLogin()
        val want = !listing.is_liked
        replace(listing.id) { it.copy(is_liked = want, likes_count = (it.likes_count + if (want) 1 else -1).coerceAtLeast(0)) }
        viewModelScope.launch {
            try {
                repo.setLiked(listing.id, want)
            } catch (e: ApiException) {
                replace(listing.id) { listing }
            }
        }
    }

    private fun replace(id: Int, transform: (Listing) -> Listing) =
        _state.update { s -> s.copy(items = s.items.map { if (it.id == id) transform(it) else it }) }
}

@Composable
fun ReelsScreen(onOpenListing: (Int) -> Unit, onNeedsLogin: () -> Unit) {
    val repo = LocalRepository.current
    val session = LocalSession.current
    val vm = rememberVm { ReelsViewModel(repo, session) }
    val state by vm.state.collectAsState()
    val saved by repo.savedIdsFlow.collectAsState(initial = emptySet())
    val context = androidx.compose.ui.platform.LocalContext.current
    val scope = androidx.compose.runtime.rememberCoroutineScope()
    var selectedVideo by remember { mutableStateOf<Uri?>(null) }
    var caption by remember { mutableStateOf("") }
    var selectedListing by remember { mutableStateOf<Int?>(null) }
    var listingMenuOpen by remember { mutableStateOf(false) }
    val videoPicker = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) {
        selectedVideo = it
        if (it != null) {
            selectedListing = null
            vm.clearUploadError()
            vm.loadOwnedListings()
        }
    }

    LaunchedEffect(state.items.size, state.next, state.reels.size) {
        if (state.reels.isEmpty() && state.items.isEmpty() && state.next != null && !state.loadingMore) vm.loadMore()
    }

    Box(Modifier.fillMaxSize().background(Color.Black)) {
        when {
            state.loading -> ScreenLoader()
            state.error != null -> ErrorState(state.error ?: "", { vm.load() }, Modifier.fillMaxSize())
            state.reels.isNotEmpty() -> {
                val pager = rememberPagerState(pageCount = { state.reels.size })
                LaunchedEffect(pager, state.reels.size) {
                    snapshotFlow { pager.currentPage }.collect { page ->
                        if (page >= state.reels.size - 3) vm.loadMore()
                    }
                }
                VerticalPager(state = pager, modifier = Modifier.fillMaxSize()) { page ->
                    val reel = state.reels[page]
                    ReelVideoPage(reel, page == pager.currentPage, onOpenListing)
                }
            }
            state.items.isEmpty() -> EmptyState(
                Icons.Outlined.PlayCircleOutline, "No reels yet", "New listings from sellers will show up here.",
            )
            else -> {
                val pager = rememberPagerState(pageCount = { state.items.size })
                LaunchedEffect(pager, state.items.size) {
                    snapshotFlow { pager.currentPage }.collect { page ->
                        if (page >= state.items.size - 3) vm.loadMore()
                    }
                }
                VerticalPager(state = pager, modifier = Modifier.fillMaxSize()) { page ->
                    val item = state.items[page]
                    ReelPage(
                        listing = item,
                        saved = item.id in saved,
                        onOpen = { onOpenListing(item.id) },
                        onLike = { vm.toggleLike(item, onNeedsLogin) },
                        onSave = { scope.launch { repo.toggleSaved(item.id) } },
                        onShare = { com.choropia.app.ui.util.shareListing(context, item) },
                    )
                }
            }
        }
        Text(
            "Reels",
            color = Color.White,
            style = androidx.compose.material3.MaterialTheme.typography.titleLarge,
            modifier = Modifier.statusBarsPadding().padding(16.dp),
        )
        IconButton(
            onClick = {
                if (session.loggedIn.value) videoPicker.launch("video/*") else onNeedsLogin()
            },
            modifier = Modifier.align(Alignment.TopEnd).statusBarsPadding().padding(8.dp),
        ) {
            Icon(Icons.Outlined.Add, contentDescription = "Create reel", tint = Color.White)
        }
    }

    selectedVideo?.let { uri ->
        AlertDialog(
            onDismissRequest = { if (!state.uploading) { selectedVideo = null; caption = "" } },
            title = { Text("Create a reel") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text(uri.lastPathSegment?.substringAfterLast('/') ?: "Video selected", maxLines = 1, overflow = TextOverflow.Ellipsis)
                    OutlinedTextField(
                        value = caption,
                        onValueChange = { caption = it.take(500) },
                        label = { Text("Caption") },
                        modifier = Modifier.fillMaxWidth(),
                    )
                    Box {
                        TextButton(onClick = { listingMenuOpen = true }) {
                            Text(
                                selectedListing?.let { id -> state.ownedListings.firstOrNull { it.id == id }?.title }
                                    ?: "Tag a listing (optional)",
                            )
                        }
                        DropdownMenu(expanded = listingMenuOpen, onDismissRequest = { listingMenuOpen = false }) {
                            DropdownMenuItem(
                                text = { Text("No listing") },
                                onClick = { selectedListing = null; listingMenuOpen = false },
                            )
                            state.ownedListings.forEach { listing ->
                                DropdownMenuItem(
                                    text = { Text(listing.title, maxLines = 1, overflow = TextOverflow.Ellipsis) },
                                    onClick = { selectedListing = listing.id; listingMenuOpen = false },
                                )
                            }
                        }
                    }
                    if (state.uploading) {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            CircularProgressIndicator(modifier = Modifier.size(18.dp), strokeWidth = 2.dp)
                            Text("Uploading… Keep the app open until it finishes.")
                        }
                    }
                    state.uploadError?.let { Text("Upload failed: $it. Your video is still selected; retry below.") }
                }
            },
            confirmButton = {
                TextButton(
                    enabled = !state.uploading,
                    onClick = { vm.createReel(uri, caption, selectedListing) { selectedVideo = null; caption = ""; selectedListing = null } },
                ) { Text(if (state.uploading) "Uploading…" else if (state.uploadError != null) "Retry" else "Post") }
            },
            dismissButton = {
                TextButton(enabled = !state.uploading, onClick = { selectedVideo = null; caption = ""; selectedListing = null }) { Text("Cancel") }
            },
        )
    }
}

@Composable
private fun ReelVideoPage(reel: Reel, active: Boolean, onOpenListing: (Int) -> Unit) {
    val context = androidx.compose.ui.platform.LocalContext.current
    val videoView = remember(reel.video) { VideoView(context) }
    DisposableEffect(videoView, reel.video, active) {
        videoView.setOnPreparedListener { player: MediaPlayer ->
            player.isLooping = true
            if (active) videoView.start()
        }
        if (videoView.tag != reel.video) {
            videoView.stopPlayback()
            videoView.tag = reel.video
            videoView.setVideoURI(Uri.parse(reel.video))
        } else if (active) {
            videoView.start()
        } else if (videoView.isPlaying) {
            videoView.pause()
        }
        onDispose { if (videoView.isPlaying) videoView.pause() }
    }

    Box(Modifier.fillMaxSize().background(Color(0xFF0B192C))) {
        AndroidView(factory = { videoView }, modifier = Modifier.fillMaxSize())
        Box(
            Modifier.align(Alignment.BottomCenter).fillMaxWidth().height(300.dp)
                .background(Brush.verticalGradient(listOf(Color.Transparent, Color.Black.copy(alpha = 0.8f)))),
        )
        Column(
            Modifier.align(Alignment.BottomStart).fillMaxWidth().navigationBarsPadding().padding(18.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Text(reel.creator_name.ifBlank { "Choropia creator" }, color = Color.White, fontWeight = FontWeight.SemiBold)
            if (reel.caption.isNotBlank()) Text(reel.caption, color = Color.White, maxLines = 3, overflow = TextOverflow.Ellipsis)
            val listingId = reel.listing
            if (listingId != null) {
                Row(
                    Modifier.clip(RoundedCornerShape(50)).background(Color.White).clickable { onOpenListing(listingId) }
                        .padding(horizontal = 16.dp, vertical = 10.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Icon(Icons.Outlined.ShoppingBag, null, tint = Color(0xFF0B192C), modifier = Modifier.size(18.dp))
                    Text(
                        listOfNotNull(reel.listing_title, reel.listing_price?.let(::formatNaira)).joinToString(" · ").ifBlank { "View listing" },
                        color = Color(0xFF0B192C),
                        fontWeight = FontWeight.SemiBold,
                    )
                }
            }
        }
    }
}

@Composable
private fun ReelPage(
    listing: Listing,
    saved: Boolean,
    onOpen: () -> Unit,
    onLike: () -> Unit,
    onSave: () -> Unit,
    onShare: () -> Unit,
) {
    Box(Modifier.fillMaxSize().background(Color(0xFF0B192C))) {
        val image = listing.cover_photo ?: listing.photos.firstOrNull()?.image
        if (image != null) {
            AsyncImage(
                model = image,
                contentDescription = listing.title,
                contentScale = ContentScale.Crop,
                modifier = Modifier.fillMaxSize().clickable(onClick = onOpen),
            )
        }
        // Legibility gradient for the caption.
        Box(
            Modifier
                .align(Alignment.BottomCenter)
                .fillMaxWidth()
                .height(320.dp)
                .background(Brush.verticalGradient(listOf(Color.Transparent, Color.Black.copy(alpha = 0.78f)))),
        )
        Row(
            Modifier.align(Alignment.BottomCenter).fillMaxWidth().navigationBarsPadding().padding(16.dp),
            verticalAlignment = Alignment.Bottom,
        ) {
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    Avatar(listing.seller_name.ifBlank { "Seller" }, listing.seller_avatar, size = 38.dp)
                    Text(
                        listing.seller_name.ifBlank { "Choropia seller" },
                        color = Color.White,
                        fontWeight = FontWeight.SemiBold,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
                Text(listing.title, color = Color.White, style = androidx.compose.material3.MaterialTheme.typography.titleMedium, maxLines = 2, overflow = TextOverflow.Ellipsis)
                Text(formatNaira(listing.price), color = Color.White, style = MoneyStyle)
                Row(
                    Modifier
                        .clip(RoundedCornerShape(50))
                        .background(Color.White)
                        .clickable(onClick = onOpen)
                        .padding(horizontal = 16.dp, vertical = 10.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Icon(Icons.Outlined.ShoppingBag, null, tint = Color(0xFF0B192C), modifier = Modifier.size(18.dp))
                    Text("Buy with escrow", color = Color(0xFF0B192C), fontWeight = FontWeight.SemiBold)
                }
            }
            Column(
                Modifier.padding(start = 12.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(18.dp),
            ) {
                ReelAction(
                    icon = if (listing.is_liked) Icons.Filled.Favorite else Icons.Outlined.FavoriteBorder,
                    label = listing.likes_count.toString(),
                    tint = if (listing.is_liked) Color(0xFFFF5A6E) else Color.White,
                    onClick = onLike,
                )
                ReelAction(Icons.Outlined.ChatBubbleOutline, listing.comments_count.toString(), Color.White, onOpen)
                ReelAction(Icons.Outlined.Share, "Share", Color.White, onShare)
                ReelAction(
                    icon = if (saved) Icons.Filled.Bookmark else Icons.Outlined.BookmarkBorder,
                    label = if (saved) "Saved" else "Save",
                    tint = Color.White,
                    onClick = onSave,
                )
            }
        }
    }
}

@Composable
private fun ReelAction(icon: androidx.compose.ui.graphics.vector.ImageVector, label: String, tint: Color, onClick: () -> Unit) {
    Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.clickable(onClick = onClick)) {
        Box(
            Modifier.size(48.dp).clip(CircleShape).background(Color.Black.copy(alpha = 0.35f)),
            contentAlignment = Alignment.Center,
        ) { Icon(icon, null, tint = tint, modifier = Modifier.size(26.dp)) }
        Text(label, color = Color.White, style = androidx.compose.material3.MaterialTheme.typography.labelMedium)
    }
}
