package com.choropia.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material.icons.automirrored.outlined.Send
import androidx.compose.material.icons.filled.Bookmark
import androidx.compose.material.icons.outlined.BookmarkBorder
import androidx.compose.material.icons.outlined.ChatBubbleOutline
import androidx.compose.material.icons.outlined.Share
import androidx.compose.material.icons.outlined.Flag
import androidx.compose.material.icons.outlined.LocationOn
import androidx.compose.material.icons.outlined.MoreVert
import androidx.compose.material.icons.outlined.ShoppingBag
import androidx.compose.material.icons.outlined.VerifiedUser
import androidx.compose.material.icons.outlined.Visibility
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.choropia.app.data.model.Comment
import com.choropia.app.data.model.Listing
import com.choropia.app.data.network.ApiException
import com.choropia.app.data.repository.ChoropiaRepository
import com.choropia.app.session.Session
import com.choropia.app.ui.LocalRepository
import com.choropia.app.ui.LocalSession
import com.choropia.app.ui.components.Avatar
import com.choropia.app.ui.components.BlockingLoader
import com.choropia.app.ui.components.ErrorState
import com.choropia.app.ui.components.LikeButton
import com.choropia.app.ui.components.ListingImage
import com.choropia.app.ui.components.PrimaryButton
import com.choropia.app.ui.components.ScreenLoader
import com.choropia.app.ui.components.SecondaryButton
import com.choropia.app.ui.components.SectionTitle
import com.choropia.app.ui.components.StatusPill
import com.choropia.app.ui.components.SurfaceCard
import com.choropia.app.ui.rememberVm
import com.choropia.app.ui.theme.MoneyStyle
import com.choropia.app.ui.util.formatNaira
import com.choropia.app.ui.util.timeAgo
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class DetailState(
    val listing: Listing? = null,
    val comments: List<Comment> = emptyList(),
    val following: Boolean = false,
    val merchantName: String? = null,
    val loading: Boolean = true,
    val busy: Boolean = false,
    val error: String? = null,
    val message: String? = null,
)

class ListingDetailViewModel(
    private val id: Int,
    private val repo: ChoropiaRepository,
    private val session: Session,
) : ViewModel() {
    private val _state = MutableStateFlow(DetailState())
    val state: StateFlow<DetailState> = _state.asStateFlow()

    init {
        load()
    }

    private val Listing.followTarget: Pair<String, Int>?
        get() = merchantRef?.let { "merchant" to it } ?: sellerUserId?.let { "user" to it }

    fun load() {
        viewModelScope.launch {
            _state.update { it.copy(loading = it.listing == null, error = null) }
            try {
                val listing = repo.getListing(id)
                _state.update { it.copy(listing = listing, loading = false) }
                runCatching { repo.comments(id) }.onSuccess { c -> _state.update { it.copy(comments = c) } }
                if (session.loggedIn.value) {
                    listing.followTarget?.let { (type, tid) ->
                        runCatching { repo.isFollowing(type, tid) }.onSuccess { f -> _state.update { it.copy(following = f) } }
                    }
                }
            } catch (e: ApiException) {
                _state.update { it.copy(loading = false, error = e.message) }
            }
        }
    }

    private fun guarded(onNeedsLogin: () -> Unit, block: suspend () -> Unit) {
        if (!session.loggedIn.value) {
            onNeedsLogin()
            return
        }
        if (_state.value.busy) return
        viewModelScope.launch {
            _state.update { it.copy(busy = true) }
            try {
                block()
            } catch (e: ApiException) {
                _state.update { it.copy(message = e.message) }
            } finally {
                _state.update { it.copy(busy = false) }
            }
        }
    }

    fun toggleLike(onNeedsLogin: () -> Unit) {
        val listing = _state.value.listing ?: return
        if (!session.loggedIn.value) return onNeedsLogin()
        val want = !listing.is_liked
        _state.update {
            it.copy(listing = listing.copy(is_liked = want, likes_count = (listing.likes_count + if (want) 1 else -1).coerceAtLeast(0)))
        }
        viewModelScope.launch {
            try {
                repo.setLiked(listing.id, want)
            } catch (e: ApiException) {
                _state.update { it.copy(listing = listing, message = e.message) }
            }
        }
    }

    fun toggleFollow(onNeedsLogin: () -> Unit) {
        val target = _state.value.listing?.followTarget ?: return
        guarded(onNeedsLogin) {
            val want = !_state.value.following
            repo.setFollowing(target.first, target.second, want)
            _state.update { it.copy(following = want, message = if (want) "Following seller" else "Unfollowed") }
        }
    }

    fun addComment(text: String, parentId: Int?, onNeedsLogin: () -> Unit, onDone: () -> Unit) {
        if (text.isBlank()) return
        guarded(onNeedsLogin) {
            val comment = repo.addComment(id, text, parentId)
            _state.update { s ->
                s.copy(
                    comments = s.comments + comment,
                    listing = s.listing?.let { it.copy(comments_count = it.comments_count + 1) },
                )
            }
            onDone()
        }
    }

    fun messageSeller(onNeedsLogin: () -> Unit, onOpenChat: (Int) -> Unit) {
        guarded(onNeedsLogin) { onOpenChat(repo.startConversation(id).id) }
    }

    fun buyNow(onNeedsLogin: () -> Unit, onOpenOrder: (Int) -> Unit) {
        guarded(onNeedsLogin) { onOpenOrder(repo.createOrder(id).id) }
    }

    fun markSold() {
        guarded({}) {
            val updated = repo.markSold(id)
            _state.update { it.copy(listing = _state.value.listing?.copy(status = updated.status), message = "Marked as sold") }
        }
    }

    fun report(reason: String, onNeedsLogin: () -> Unit) {
        guarded(onNeedsLogin) {
            repo.reportListing(id, reason)
            _state.update { it.copy(message = "Thanks — our moderators will review this listing.") }
        }
    }

    fun messageShown() = _state.update { it.copy(message = null) }
}

@Composable
fun ListingDetailScreen(
    listingId: Int,
    onBack: () -> Unit,
    onOpenChat: (Int) -> Unit,
    onOpenOrder: (Int) -> Unit,
    onOpenMerchant: (Int) -> Unit,
    onNeedsLogin: () -> Unit,
    showMessage: (String) -> Unit,
) {
    val repo = LocalRepository.current
    val session = LocalSession.current
    val vm = rememberVm(key = "listing-$listingId") { ListingDetailViewModel(listingId, repo, session) }
    val state by vm.state.collectAsState()
    val me by session.user.collectAsState()

    LaunchedEffect(state.message) {
        state.message?.let { showMessage(it); vm.messageShown() }
    }

    var confirmBuy by remember { mutableStateOf(false) }
    var replyTo by remember { mutableStateOf<Comment?>(null) }
    val context = androidx.compose.ui.platform.LocalContext.current
    val saved by repo.savedIdsFlow.collectAsState(initial = emptySet())
    val scope = androidx.compose.runtime.rememberCoroutineScope()
    var reportOpen by remember { mutableStateOf(false) }

    Box(Modifier.fillMaxSize()) {
        val listing = state.listing
        when {
            state.loading -> ScreenLoader()
            listing == null -> Column(Modifier.fillMaxSize().statusBarsPadding()) {
                IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Outlined.ArrowBack, "Back") }
                ErrorState(state.error ?: "Listing not found.", vm::load, Modifier.fillMaxSize())
            }
            else -> {
                val isOwner = me != null && (listing.owner_id == me?.id)
                Column(Modifier.fillMaxSize()) {
                    LazyColumn(Modifier.weight(1f), contentPadding = PaddingValues(bottom = 16.dp)) {
                        item(key = "gallery") {
                            Gallery(
                                listing = listing,
                                saved = listing.id in saved,
                                onBack = onBack,
                                onShare = { com.choropia.app.ui.util.shareListing(context, listing) },
                                onToggleSave = {
                                    scope.launch {
                                        val wasSaved = listing.id in saved
                                        repo.toggleSaved(listing.id)
                                        showMessage(if (wasSaved) "Removed from watchlist" else "Saved to watchlist")
                                    }
                                },
                                onReport = { reportOpen = true },
                            )
                        }
                        item(key = "info") {
                            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                                Text(listing.title, style = MaterialTheme.typography.headlineSmall)
                                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                    Text(formatNaira(listing.price), style = MoneyStyle.copy(fontSize = androidx.compose.ui.unit.TextUnit(26f, androidx.compose.ui.unit.TextUnitType.Sp)))
                                    Box(Modifier.weight(1f))
                                    StatusPill(
                                        listing.condition,
                                        MaterialTheme.colorScheme.secondaryContainer,
                                        MaterialTheme.colorScheme.onSecondaryContainer,
                                    )
                                    if (listing.status != "active") {
                                        StatusPill(listing.status, MaterialTheme.colorScheme.errorContainer, MaterialTheme.colorScheme.error)
                                    }
                                }
                                Row(horizontalArrangement = Arrangement.spacedBy(14.dp), verticalAlignment = Alignment.CenterVertically) {
                                    if (listing.location.isNotBlank()) {
                                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                                            Icon(Icons.Outlined.LocationOn, null, Modifier.size(16.dp), tint = MaterialTheme.colorScheme.onSurfaceVariant)
                                            Text(listing.location, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                        }
                                    }
                                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                                        Icon(Icons.Outlined.Visibility, null, Modifier.size(16.dp), tint = MaterialTheme.colorScheme.onSurfaceVariant)
                                        Text("${listing.views_count} views", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                    }
                                    Text(timeAgo(listing.created_at), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                }
                            }
                        }
                        item(key = "seller") {
                            SurfaceCard(
                                Modifier.padding(horizontal = 16.dp).fillMaxWidth(),
                                onClick = listing.merchantRef?.let { id -> { onOpenMerchant(id) } },
                            ) {
                                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                                    Avatar(listing.seller_name.ifBlank { "Seller" }, listing.seller_avatar, size = 46.dp)
                                    Column(Modifier.weight(1f)) {
                                        Text(listing.seller_name.ifBlank { "Choropia seller" }, style = MaterialTheme.typography.titleSmall, maxLines = 1, overflow = TextOverflow.Ellipsis)
                                        Text(
                                            if (listing.merchantRef != null) "Verified storefront" else "Individual seller",
                                            style = MaterialTheme.typography.bodySmall,
                                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                                        )
                                    }
                                    if (!isOwner) {
                                        TextButton(onClick = { vm.toggleFollow(onNeedsLogin) }) {
                                            Text(if (state.following) "Following" else "Follow", style = MaterialTheme.typography.labelLarge)
                                        }
                                    }
                                }
                            }
                        }
                        item(key = "escrow") {
                            Row(
                                Modifier
                                    .padding(16.dp)
                                    .fillMaxWidth()
                                    .clip(RoundedCornerShape(16.dp))
                                    .background(MaterialTheme.colorScheme.secondaryContainer.copy(alpha = 0.55f))
                                    .padding(14.dp),
                                horizontalArrangement = Arrangement.spacedBy(12.dp),
                            ) {
                                Icon(Icons.Outlined.VerifiedUser, null, tint = MaterialTheme.colorScheme.secondary)
                                Text(
                                    "Escrow protected. Your payment is held until you confirm delivery. The seller only gets paid when you're satisfied.",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurface,
                                )
                            }
                        }
                        if (listing.description.isNotBlank()) {
                            item(key = "desc") {
                                Column(Modifier.padding(horizontal = 16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                                    SectionTitle("Description")
                                    Text(listing.description, style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                }
                            }
                        }
                        item(key = "social") {
                            Row(
                                Modifier.padding(horizontal = 10.dp, vertical = 12.dp),
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(8.dp),
                            ) {
                                LikeButton(listing.is_liked, listing.likes_count, { vm.toggleLike(onNeedsLogin) })
                                Icon(Icons.Outlined.ChatBubbleOutline, null, Modifier.size(21.dp), tint = MaterialTheme.colorScheme.onSurfaceVariant)
                                Text("${listing.comments_count}", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        }
                        item(key = "comments-title") {
                            Column(Modifier.padding(horizontal = 16.dp).padding(bottom = 6.dp)) { SectionTitle("Comments") }
                        }
                        if (state.comments.isEmpty()) {
                            item(key = "no-comments") {
                                Text(
                                    "No comments yet. Ask the seller a question.",
                                    style = MaterialTheme.typography.bodyMedium,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 6.dp),
                                )
                            }
                        }
                        // Threads: each reply is shown under the top-level comment it descends from.
                        val byId = state.comments.associateBy { it.id }
                        fun rootOf(c: Comment): Int {
                            var cur = c
                            var guard = 0
                            while (guard++ < 20) {
                                val parent = cur.parent?.let { byId[it] } ?: break
                                cur = parent
                            }
                            return cur.id
                        }
                        val roots = state.comments.filter { c -> c.parent == null || byId[c.parent] == null }
                        val repliesByRoot = state.comments
                            .filter { c -> c.parent != null && byId[c.parent] != null }
                            .groupBy { rootOf(it) }
                        roots.forEach { root ->
                            item(key = "c${root.id}") {
                                CommentRow(root, listing.owner_id, me?.id, depth = 0) { replyTo = root }
                            }
                            repliesByRoot[root.id].orEmpty().forEach { reply ->
                                item(key = "c${reply.id}") {
                                    CommentRow(reply, listing.owner_id, me?.id, depth = 1) { replyTo = root }
                                }
                            }
                        }
                        item(key = "composer") {
                            CommentComposer(
                                replyingTo = replyTo?.let {
                                    when (it.author_id) {
                                        me?.id -> "yourself"
                                        listing.owner_id -> "the seller"
                                        else -> "a member"
                                    }
                                },
                                onCancelReply = { replyTo = null },
                                onSend = { text, clear ->
                                    vm.addComment(text, replyTo?.id, onNeedsLogin) {
                                        replyTo = null
                                        clear()
                                    }
                                },
                            )
                        }
                    }

                    // Sticky action bar.
                    Row(
                        Modifier
                            .fillMaxWidth()
                            .background(MaterialTheme.colorScheme.surfaceContainerLowest)
                            .navigationBarsPadding()
                            .padding(horizontal = 16.dp, vertical = 12.dp),
                        horizontalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        when {
                            isOwner && listing.status == "active" ->
                                SecondaryButton("Mark as sold", { vm.markSold() }, Modifier.weight(1f), enabled = !state.busy)
                            isOwner -> Text(
                                "This is your listing (${listing.status}).",
                                style = MaterialTheme.typography.bodyMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                            listing.status != "active" -> Text(
                                "This item is no longer available.",
                                style = MaterialTheme.typography.bodyMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                            else -> {
                                SecondaryButton(
                                    "Message",
                                    { vm.messageSeller(onNeedsLogin, onOpenChat) },
                                    Modifier.weight(1f),
                                    enabled = !state.busy,
                                    icon = Icons.Outlined.ChatBubbleOutline,
                                )
                                PrimaryButton(
                                    "Buy now",
                                    { if (session.loggedIn.value) confirmBuy = true else onNeedsLogin() },
                                    Modifier.weight(1f),
                                    enabled = !state.busy,
                                    icon = Icons.Outlined.ShoppingBag,
                                )
                            }
                        }
                    }
                }

                if (confirmBuy) {
                    AlertDialog(
                        onDismissRequest = { confirmBuy = false },
                        title = { Text("Buy with escrow?") },
                        text = {
                            Text(
                                "We'll create an order for ${formatNaira(listing.price)}. You'll pay into escrow next; the seller is paid only after you confirm you received the item.",
                            )
                        },
                        confirmButton = {
                            TextButton(onClick = { confirmBuy = false; vm.buyNow(onNeedsLogin, onOpenOrder) }) { Text("Create order") }
                        },
                        dismissButton = { TextButton(onClick = { confirmBuy = false }) { Text("Cancel") } },
                    )
                }
                if (reportOpen) {
                    ReportDialog(
                        onDismiss = { reportOpen = false },
                        onSubmit = { reason -> reportOpen = false; vm.report(reason, onNeedsLogin) },
                    )
                }
            }
        }
        BlockingLoader(visible = state.busy && state.listing != null)
    }
}

@Composable
private fun Gallery(
    listing: Listing,
    saved: Boolean,
    onBack: () -> Unit,
    onShare: () -> Unit,
    onToggleSave: () -> Unit,
    onReport: () -> Unit,
) {
    val urls = listing.imageUrls
    val pageCount = urls.size.coerceAtLeast(1)
    val pager = rememberPagerState(pageCount = { pageCount })
    Box(Modifier.fillMaxWidth().aspectRatio(1f)) {
        HorizontalPager(state = pager, modifier = Modifier.fillMaxSize()) { page ->
            ListingImage(urls.getOrNull(page), Modifier.fillMaxSize(), listing.title)
        }
        // Back + overflow floating over the photo.
        Row(
            Modifier.fillMaxWidth().statusBarsPadding().padding(8.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            FloatingCircle { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Outlined.ArrowBack, "Back", tint = Color.White) } }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                FloatingCircle {
                    IconButton(onClick = onShare) { Icon(Icons.Outlined.Share, "Share", tint = Color.White) }
                }
                FloatingCircle {
                    IconButton(onClick = onToggleSave) {
                        Icon(
                            if (saved) Icons.Filled.Bookmark else Icons.Outlined.BookmarkBorder,
                            if (saved) "Remove from watchlist" else "Save to watchlist",
                            tint = Color.White,
                        )
                    }
                }
                var menu by remember { mutableStateOf(false) }
                FloatingCircle {
                    IconButton(onClick = { menu = true }) { Icon(Icons.Outlined.MoreVert, "More", tint = Color.White) }
                    DropdownMenu(expanded = menu, onDismissRequest = { menu = false }) {
                        DropdownMenuItem(
                            text = { Text("Report listing") },
                            leadingIcon = { Icon(Icons.Outlined.Flag, null) },
                            onClick = { menu = false; onReport() },
                        )
                    }
                }
            }
        }
        if (pageCount > 1) {
            Row(
                Modifier.align(Alignment.BottomCenter).padding(bottom = 12.dp),
                horizontalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                repeat(pageCount) { index ->
                    Box(
                        Modifier
                            .size(if (index == pager.currentPage) 9.dp else 7.dp)
                            .clip(CircleShape)
                            .background(Color.White.copy(alpha = if (index == pager.currentPage) 1f else 0.55f)),
                    )
                }
            }
        }
    }
}

@Composable
private fun FloatingCircle(content: @Composable () -> Unit) {
    Box(
        Modifier.size(44.dp).clip(CircleShape).background(Color.Black.copy(alpha = 0.38f)),
        contentAlignment = Alignment.Center,
    ) { content() }
}

@Composable
private fun CommentRow(comment: Comment, sellerId: Int?, myId: Int?, depth: Int, onReply: () -> Unit) {
    val label = when (comment.author_id) {
        null -> "Member"
        myId -> "You"
        sellerId -> "Seller"
        else -> "Member"
    }
    Row(
        Modifier.padding(start = 16.dp + (depth * 36).dp, end = 16.dp, top = 6.dp, bottom = 6.dp),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Avatar(label, null, size = if (depth == 0) 32.dp else 26.dp)
        Column {
            Column(
                Modifier
                    .clip(RoundedCornerShape(14.dp))
                    .background(MaterialTheme.colorScheme.surfaceContainer)
                    .padding(horizontal = 12.dp, vertical = 8.dp),
            ) {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                    Text(label, style = MaterialTheme.typography.labelLarge)
                    Text(timeAgo(comment.created_at), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Text(comment.body, style = MaterialTheme.typography.bodyMedium)
            }
            Text(
                "Reply",
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.secondary,
                modifier = Modifier
                    .clip(RoundedCornerShape(8.dp))
                    .clickable(onClick = onReply)
                    .padding(horizontal = 10.dp, vertical = 4.dp),
            )
        }
    }
}

@Composable
private fun CommentComposer(replyingTo: String?, onCancelReply: () -> Unit, onSend: (String, () -> Unit) -> Unit) {
    var text by remember { mutableStateOf("") }
    Column(Modifier.fillMaxWidth()) {
        if (replyingTo != null) {
            Row(
                Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 4.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    "Replying to $replyingTo",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.secondary,
                    modifier = Modifier.weight(1f),
                )
                TextButton(onClick = onCancelReply) { Text("Cancel") }
            }
        }
        Row(
            Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            OutlinedTextField(
                value = text,
                onValueChange = { text = it },
                placeholder = { Text(if (replyingTo != null) "Write a reply..." else "Write a comment...") },
                modifier = Modifier.weight(1f),
                shape = RoundedCornerShape(50),
                maxLines = 3,
            )
            IconButton(onClick = { onSend(text) { text = "" } }, enabled = text.isNotBlank()) {
                Icon(Icons.AutoMirrored.Outlined.Send, "Send")
            }
        }
    }
}

@Composable
private fun ReportDialog(onDismiss: () -> Unit, onSubmit: (String) -> Unit) {
    var reason by remember { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Report listing") },
        text = {
            OutlinedTextField(
                value = reason,
                onValueChange = { reason = it },
                label = { Text("What's wrong with it?") },
                minLines = 3,
            )
        },
        confirmButton = { TextButton(onClick = { onSubmit(reason) }, enabled = reason.isNotBlank()) { Text("Submit") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}
