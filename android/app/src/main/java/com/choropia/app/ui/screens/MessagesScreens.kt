package com.choropia.app.ui.screens

import com.choropia.app.ui.components.Chip
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material.icons.automirrored.outlined.Send
import androidx.compose.material.icons.outlined.AddPhotoAlternate
import androidx.compose.material.icons.outlined.ChatBubbleOutline
import androidx.compose.material.icons.outlined.Close
import androidx.compose.material.icons.outlined.Mic
import androidx.compose.material.icons.outlined.MoreVert
import androidx.compose.material.icons.outlined.Pause
import androidx.compose.material.icons.outlined.PlayArrow
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.TextButton
import androidx.compose.material3.Text
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
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.ViewModel
import androidx.lifecycle.repeatOnLifecycle
import androidx.lifecycle.viewModelScope
import com.choropia.app.data.model.Conversation
import com.choropia.app.data.model.ChatOffer
import com.choropia.app.data.model.Listing
import com.choropia.app.data.model.Message
import com.choropia.app.data.network.ApiException
import com.choropia.app.data.network.ChatSocket
import com.choropia.app.data.repository.ChoropiaRepository
import com.choropia.app.session.Session
import com.choropia.app.ui.LocalRepository
import com.choropia.app.ui.LocalSession
import com.choropia.app.ui.components.Avatar
import com.choropia.app.ui.components.BrandPullToRefresh
import com.choropia.app.ui.components.EmptyState
import com.choropia.app.ui.components.ErrorState
import com.choropia.app.ui.components.ScreenLoader
import com.choropia.app.ui.rememberVm
import com.choropia.app.ui.util.shortDateTime
import com.choropia.app.ui.util.formatNaira
import com.choropia.app.ui.util.timeAgo
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

// --- inbox ----------------------------------------------------------------------------------

data class InboxState(
    val items: List<Conversation> = emptyList(),
    val loading: Boolean = true,
    val refreshing: Boolean = false,
    val error: String? = null,
)

class InboxViewModel(private val repo: ChoropiaRepository) : ViewModel() {
    private val _state = MutableStateFlow(InboxState())
    val state: StateFlow<InboxState> = _state.asStateFlow()

    init {
        load(initial = true)
    }

    /** [silent] is the background poll: it never shows a spinner or replaces content with an error. */
    fun load(initial: Boolean = false, silent: Boolean = false) {
        viewModelScope.launch {
            if (!silent) _state.update { it.copy(loading = initial && it.items.isEmpty(), refreshing = !initial, error = null) }
            try {
                val list = repo.conversations().sortedByDescending { it.last_message?.created_at ?: it.updated_at ?: "" }
                _state.update { it.copy(items = list, loading = false, refreshing = false) }
            } catch (e: ApiException) {
                if (!silent) _state.update { it.copy(loading = false, refreshing = false, error = e.message) }
            }
        }
    }
}

@Composable
fun InboxScreen(onOpenChat: (Int) -> Unit) {
    val repo = LocalRepository.current
    val session = LocalSession.current
    val vm = rememberVm { InboxViewModel(repo) }
    val state by vm.state.collectAsState()
    val me by session.user.collectAsState()
    var query by remember { mutableStateOf("") }
    var filter by remember { mutableStateOf(0) }   // 0 all, 1 escrow deals, 2 unread
    val filtered = state.items.filter { c ->
        val last = c.last_message
        val unread = last != null && last.sender_id != me?.id && last.read_at == null
        val matchesFilter = when (filter) {
            1 -> c.order != null
            2 -> unread
            else -> true
        }
        val q = query.trim().lowercase()
        val matchesQuery = q.isEmpty() ||
            (c.other_party_name ?: "").lowercase().contains(q) ||
            (c.listing_title ?: "").lowercase().contains(q) ||
            (if (last?.is_deleted == true) "message deleted" else last?.body.orEmpty()).lowercase().contains(q)
        matchesFilter && matchesQuery
    }

    // Refresh when returning to this tab (a new message may have arrived while in a chat).
    val owner = LocalContext.current as? LifecycleOwner
    LaunchedEffect(owner) {
        owner?.repeatOnLifecycle(Lifecycle.State.RESUMED) {
            while (true) {
                delay(15_000)
                vm.load(silent = true)
            }
        }
    }

    Column(Modifier.fillMaxSize().statusBarsPadding()) {
        Text(
            "Messages",
            style = MaterialTheme.typography.headlineSmall,
            modifier = Modifier.padding(start = 16.dp, end = 16.dp, top = 12.dp, bottom = 8.dp),
        )
        OutlinedTextField(
            value = query,
            onValueChange = { query = it },
            placeholder = { Text("Search conversations or people") },
            singleLine = true,
            shape = RoundedCornerShape(50),
            modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp),
        )
        Row(Modifier.padding(horizontal = 16.dp, vertical = 10.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Chip("All", filter == 0, { filter = 0 })
            Chip("Escrow deals", filter == 1, { filter = 1 })
            Chip("Unread", filter == 2, { filter = 2 })
        }
        when {
            state.loading -> ScreenLoader()
            state.error != null -> ErrorState(state.error ?: "", { vm.load(initial = true) }, Modifier.fillMaxSize())
            else -> BrandPullToRefresh(state.refreshing, { vm.load() }, Modifier.fillMaxSize()) {
                LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(bottom = 24.dp)) {
                    if (filtered.isEmpty()) {
                        item {
                            EmptyState(
                                icon = Icons.Outlined.ChatBubbleOutline,
                                title = if (state.items.isEmpty()) "No conversations yet" else "No matches",
                                message = if (state.items.isEmpty()) {
                                    "Message a seller from any listing and your chats will show up here."
                                } else {
                                    "No conversations match your search or filter."
                                },
                            )
                        }
                    }
                    items(filtered, key = { it.id }) { conversation ->
                        val last = conversation.last_message
                        val mine = last?.sender_id != null && last.sender_id == me?.id
                        Row(
                            Modifier
                                .fillMaxWidth()
                                .clickable { onOpenChat(conversation.id) }
                                .padding(horizontal = 16.dp, vertical = 12.dp),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(12.dp),
                        ) {
                            Avatar(conversation.other_party_name ?: "Member", conversation.other_party_avatar, size = 52.dp)
                            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Text(
                                        conversation.other_party_name ?: "Member",
                                        style = MaterialTheme.typography.titleSmall,
                                        modifier = Modifier.weight(1f),
                                        maxLines = 1,
                                        overflow = TextOverflow.Ellipsis,
                                    )
                                    Text(
                                        timeAgo(last?.created_at ?: conversation.updated_at),
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    )
                                }
                                Text(
                                    conversation.listing_title.orEmpty(),
                                    style = MaterialTheme.typography.labelMedium,
                                    color = MaterialTheme.colorScheme.secondary,
                                    maxLines = 1,
                                    overflow = TextOverflow.Ellipsis,
                                )
                                Text(
                                    if (last == null) "Say hello 👋"
                                    else (if (mine) "You: " else "") + if (last.is_deleted) {
                                        "Message deleted"
                                    } else {
                                        last.body.ifBlank { last.listing_snapshot?.title.orEmpty() }
                                    },
                                    style = MaterialTheme.typography.bodyMedium,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    maxLines = 1,
                                    overflow = TextOverflow.Ellipsis,
                                )
                            }
                        }
                        HorizontalDivider(Modifier.padding(start = 80.dp), color = MaterialTheme.colorScheme.outlineVariant)
                    }
                }
            }
        }
    }
}

// --- chat -----------------------------------------------------------------------------------

data class ChatState(
    val conversation: Conversation? = null,
    val messages: List<Message> = emptyList(),
    val loading: Boolean = true,
    val error: String? = null,
    val sendError: String? = null,
)

class ChatViewModel(
    private val conversationId: Int,
    private val repo: ChoropiaRepository,
) : ViewModel() {
    private val _state = MutableStateFlow(ChatState())
    val state: StateFlow<ChatState> = _state.asStateFlow()

    private val socket = ChatSocket()
    private var server: List<Message> = emptyList()
    private val pending = mutableListOf<Message>()
    private var tempId = -1

    init {
        viewModelScope.launch {
            runCatching { repo.conversation(conversationId) }.onSuccess { c -> _state.update { it.copy(conversation = c) } }
        }
        viewModelScope.launch {
            try {
                server = repo.messages(conversationId)
                publish(loading = false)
            } catch (e: ApiException) {
                _state.update { it.copy(loading = false, error = e.message) }
            }
        }
        if (socket.isAvailable) {
            viewModelScope.launch {
                repo.accessTokenOrNull()?.let { socket.connect(conversationId, it) }
                socket.incoming.collect { incoming ->
                    if (incoming.conversation == conversationId) {
                        val existing = server.indexOfFirst { it.id != null && it.id == incoming.id }
                        server = if (existing < 0) server + incoming else server.toMutableList().also { it[existing] = incoming }
                        publish()
                    }
                }
            }
        }
    }

    private fun publish(loading: Boolean = false) {
        val ordered = (server + pending).sortedWith(compareBy({ it.created_at ?: "~" }, { it.id ?: Int.MAX_VALUE }))
        _state.update { it.copy(messages = ordered, loading = loading, error = null) }
    }

    /** Called on a timer by the screen; failures are silent (a flaky network shouldn't nag). */
    suspend fun poll() {
        runCatching { repo.conversation(conversationId) }.onSuccess { c -> _state.update { it.copy(conversation = c) } }
        runCatching { repo.messages(conversationId) }.onSuccess { latest ->
            if (latest != server) {
                server = latest
                publish()
            }
        }
    }

    fun send(text: String, myId: Int?) {
        val body = text.trim()
        if (body.isEmpty()) return
        val temp = Message(id = tempId--, conversation = conversationId, sender_id = myId, body = body, created_at = java.time.Instant.now().toString())
        pending += temp
        _state.update { it.copy(sendError = null) }
        publish()
        viewModelScope.launch {
            try {
                val saved = repo.sendMessage(conversationId, body)
                pending.remove(temp)
                if (server.none { it.id == saved.id }) server = server + saved
                publish()
            } catch (e: ApiException) {
                pending.remove(temp)
                publish()
                _state.update { it.copy(sendError = e.message) }
            }
        }
    }

    fun deleteMessage(messageId: Int, onError: (String) -> Unit) {
        viewModelScope.launch {
            try {
                repo.deleteMessage(messageId)
                server = server.map { message ->
                    if (message.id == messageId) {
                        message.copy(
                            body = "",
                            attachment = null,
                            attachment_type = "",
                            duration_seconds = null,
                            is_deleted = true,
                        )
                    } else message
                }
                publish()
            } catch (e: ApiException) {
                onError(e.message ?: "Could not delete the message.")
            }
        }
    }

    fun sendImage(uri: android.net.Uri, myId: Int?) = sendAttachment(myId) { repo.sendImage(conversationId, uri) }

    fun sendVoice(file: java.io.File, seconds: Int, myId: Int?) =
        sendAttachment(myId) { repo.sendVoiceNote(conversationId, file, seconds).also { file.delete() } }

    private fun sendAttachment(myId: Int?, call: suspend () -> Message) {
        val temp = Message(
            id = tempId--,
            conversation = conversationId,
            sender_id = myId,
            attachment_type = "uploading",
            created_at = java.time.Instant.now().toString(),
        )
        pending += temp
        _state.update { it.copy(sendError = null) }
        publish()
        viewModelScope.launch {
            try {
                val saved = call()
                pending.remove(temp)
                if (server.none { it.id == saved.id }) server = server + saved
                publish()
            } catch (e: ApiException) {
                pending.remove(temp)
                publish()
                _state.update { it.copy(sendError = e.message) }
            }
        }
    }

    override fun onCleared() {
        socket.disconnect()
    }
}

@Composable
fun ChatScreen(
    conversationId: Int,
    onBack: () -> Unit,
    onOpenListing: (Int) -> Unit,
    onOpenOrder: (Int) -> Unit,
) {
    val repo = LocalRepository.current
    val session = LocalSession.current
    val vm = rememberVm(key = "chat-$conversationId") { ChatViewModel(conversationId, repo) }
    val state by vm.state.collectAsState()
    val me by session.user.collectAsState()
    val scope = androidx.compose.runtime.rememberCoroutineScope()
    var draft by remember { mutableStateOf("") }
    val listState = rememberLazyListState()
    val context = LocalContext.current
    // The first load of a conversation marks its messages read; update the badge right away.
    LaunchedEffect(state.loading) { if (!state.loading) session.refreshUnread() }
    val recorder = remember { com.choropia.app.ui.util.VoiceRecorder(context) }
    var recording by remember { mutableStateOf(false) }
    var recordedSeconds by remember { mutableStateOf(0) }
    var offerDialogOpen by remember { mutableStateOf(false) }
    var sellerListings by remember { mutableStateOf<List<Listing>>(emptyList()) }
    var payingOffer by remember { mutableStateOf<ChatOffer?>(null) }
    var deleteTarget by remember { mutableStateOf<Message?>(null) }
    val canMakeOffer = state.conversation?.let { it.listing != null && it.seller == me?.id } == true
    androidx.compose.runtime.DisposableEffect(Unit) { onDispose { recorder.cancel() } }

    fun openOfferComposer() {
        scope.launch {
            runCatching { repo.myActiveListings() }
                .onSuccess { listings ->
                    sellerListings = listings
                    if (listings.isEmpty()) {
                        android.widget.Toast.makeText(context, "Create an active listing before making an offer.", android.widget.Toast.LENGTH_LONG).show()
                    } else {
                        offerDialogOpen = true
                    }
                }
                .onFailure {
                    android.widget.Toast.makeText(context, it.message ?: "Could not load your listings.", android.widget.Toast.LENGTH_LONG).show()
                }
        }
    }

    fun toast(text: String) = android.widget.Toast.makeText(context, text, android.widget.Toast.LENGTH_SHORT).show()

    val offerActions = remember(conversationId) {
        com.choropia.app.ui.offers.OfferCardActions(
            onPay = { payingOffer = it },
            onDecline = { offer ->
                try { repo.declineOffer(offer.id); toast("Offer declined.") } catch (e: ApiException) { toast(e.message ?: "Could not decline the offer.") }
                vm.poll()
            },
            onCancel = { offer ->
                try { repo.cancelOffer(offer.id); toast("Offer cancelled.") } catch (e: ApiException) { toast(e.message ?: "Could not cancel the offer.") }
                vm.poll()
            },
            onCheckPayment = { offer ->
                try {
                    val updated = repo.verifyOfferPayment(offer.id)
                    toast(
                        when {
                            updated.status == "paid" -> "Payment received. It's held safely in escrow."
                            updated.last_payment_failed -> "The payment didn't go through. Nothing was taken."
                            else -> "No payment yet. If you've just paid, give it a minute."
                        },
                    )
                } catch (e: ApiException) {
                    toast(e.message ?: "Could not check the payment.")
                }
                vm.poll()
            },
            onReleased = {
                toast("Handover confirmed. Your payout is on its way.")
                scope.launch { vm.poll() }
            },
            onOpenOrder = onOpenOrder,
        )
    }

    val photoPicker = androidx.activity.compose.rememberLauncherForActivityResult(
        androidx.activity.result.contract.ActivityResultContracts.PickVisualMedia(),
    ) { uri -> if (uri != null) vm.sendImage(uri, me?.id) }

    fun beginRecording() {
        if (recorder.start()) { recording = true; recordedSeconds = 0 }
    }
    val micPermission = androidx.activity.compose.rememberLauncherForActivityResult(
        androidx.activity.result.contract.ActivityResultContracts.RequestPermission(),
    ) { granted -> if (granted) beginRecording() }

    // Tick the visible timer while recording; stop automatically at the 10-minute cap.
    LaunchedEffect(recording) {
        while (recording) {
            recordedSeconds = recorder.elapsedSeconds
            if (recordedSeconds >= 600) {
                recorder.stop()?.let { (file, secs) -> vm.sendVoice(file, secs, me?.id) }
                recording = false
            }
            delay(250)
        }
    }

    val owner = LocalContext.current as? LifecycleOwner
    LaunchedEffect(owner) {
        owner?.repeatOnLifecycle(Lifecycle.State.STARTED) {
            while (true) {
                delay(3_000)
                vm.poll()
                session.refreshUnread() // opening the chat marked these messages read on the server
            }
        }
    }
    // Newest message sits at index 0 (reverse layout) — keep it in view as messages arrive.
    LaunchedEffect(state.messages.size) {
        if (state.messages.isNotEmpty()) listState.animateScrollToItem(0)
    }

    Column(Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding().imePadding()) {
        Row(
            Modifier.fillMaxWidth().height(64.dp).padding(horizontal = 4.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Outlined.ArrowBack, "Back") }
            val c = state.conversation
            Avatar(c?.other_party_name ?: "Member", c?.other_party_avatar, size = 40.dp)
            Column(Modifier.padding(start = 10.dp)) {
                Text(c?.other_party_name ?: "Conversation", style = MaterialTheme.typography.titleSmall, maxLines = 1, overflow = TextOverflow.Ellipsis)
                val status = if (c?.other_party_online == true) "online" else c?.other_party_last_seen?.let { "last seen " + shortDateTime(it) }
                if (status != null) {
                    Text(
                        status,
                        style = MaterialTheme.typography.labelSmall,
                        color = if (c?.other_party_online == true) androidx.compose.ui.graphics.Color(0xFF12A58A) else MaterialTheme.colorScheme.outline,
                    )
                }
                if (!c?.listing_title.isNullOrBlank()) {
                    Text(
                        c?.listing_title.orEmpty(),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            }
        }
        HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
        if (canMakeOffer) {
            TextButton(
                onClick = { openOfferComposer() },
                modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp),
            ) {
                Text("Offer a different price")
            }
        }

        Box(Modifier.weight(1f)) {
            when {
                state.loading -> ScreenLoader()
                state.error != null -> ErrorState(state.error ?: "", null, Modifier.fillMaxSize())
                else -> LazyColumn(
                    state = listState,
                    reverseLayout = true,
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(horizontal = 12.dp, vertical = 10.dp),
                    verticalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    val reversed = state.messages.asReversed()
                    if (reversed.isEmpty()) {
                        item {
                            EmptyState(
                                icon = Icons.Outlined.ChatBubbleOutline,
                                title = "Start the conversation",
                                message = "Ask about condition, price or pickup. Keep payments inside Choropia escrow.",
                            )
                        }
                    }
                    items(reversed, key = { it.id ?: it.hashCode() }) { message ->
                        val mine = message.sender_id != null && message.sender_id == me?.id
                        Bubble(
                            message,
                            mine,
                            state.conversation?.other_party_last_seen,
                            { draft = it },
                            onOpenListing,
                            offerActions,
                            onDelete = { deleteTarget = message },
                        )
                    }
                }
            }

            if (offerDialogOpen) {
                com.choropia.app.ui.offers.OfferComposerSheet(
                    conversationId = conversationId,
                    listings = sellerListings,
                    defaultListingId = state.conversation?.listing,
                    sellerVerified = me?.profile?.seller_verified == true,
                    onDismiss = { offerDialogOpen = false },
                    onSent = {
                        offerDialogOpen = false
                        toast("Offer sent. The buyer can pay from the chat.")
                        scope.launch { vm.poll() }
                    },
                )
            }
            payingOffer?.let { offer ->
                com.choropia.app.ui.offers.PaySheet(
                    offer = offer,
                    onDismiss = { payingOffer = null },
                    onCheckout = { checkout ->
                        payingOffer = null
                        scope.launch { vm.poll() }
                        val url = checkout.authorization_url
                        if (url != null) {
                            context.startActivity(android.content.Intent(android.content.Intent.ACTION_VIEW, android.net.Uri.parse(url)))
                        } else {
                            onOpenOrder(checkout.order_id)
                        }
                    },
                )
            }

            deleteTarget?.let { message ->
                AlertDialog(
                    onDismissRequest = { deleteTarget = null },
                    title = { Text("Delete message?") },
                    text = { Text("This removes the message for everyone in the conversation.") },
                    confirmButton = {
                        TextButton(
                            onClick = {
                                deleteTarget = null
                                message.id?.let { messageId ->
                                    vm.deleteMessage(messageId) { error ->
                                        android.widget.Toast.makeText(context, error, android.widget.Toast.LENGTH_LONG).show()
                                    }
                                }
                            },
                        ) { Text("Delete for everyone") }
                    },
                    dismissButton = {
                        TextButton(onClick = { deleteTarget = null }) { Text("Cancel") }
                    },
                )
            }
        }

        state.sendError?.let {
            Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(horizontal = 16.dp))
        }
        Row(
            Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            if (recording) {
                // Recording bar: cancel on the left, live timer, send on the right.
                IconButton(onClick = { recorder.cancel(); recording = false }) {
                    Icon(androidx.compose.material.icons.Icons.Outlined.Close, "Cancel recording", tint = MaterialTheme.colorScheme.error)
                }
                Text(
                    "Recording  %d:%02d".format(recordedSeconds / 60, recordedSeconds % 60),
                    style = MaterialTheme.typography.titleSmall,
                    color = MaterialTheme.colorScheme.error,
                    modifier = Modifier.weight(1f),
                )
                IconButton(
                    onClick = {
                        recording = false
                        recorder.stop()?.let { (file, secs) -> vm.sendVoice(file, secs, me?.id) }
                    },
                    modifier = Modifier.clip(RoundedCornerShape(50)).background(MaterialTheme.colorScheme.primary),
                ) {
                    Icon(Icons.AutoMirrored.Outlined.Send, "Send voice note", tint = MaterialTheme.colorScheme.onPrimary)
                }
            } else {
                IconButton(
                    onClick = {
                        photoPicker.launch(
                            androidx.activity.result.PickVisualMediaRequest(
                                androidx.activity.result.contract.ActivityResultContracts.PickVisualMedia.ImageOnly,
                            ),
                        )
                    },
                ) {
                    Icon(androidx.compose.material.icons.Icons.Outlined.AddPhotoAlternate, "Attach photo")
                }
                OutlinedTextField(
                    value = draft,
                    onValueChange = { draft = it },
                    placeholder = { Text("Message") },
                    modifier = Modifier.weight(1f),
                    shape = RoundedCornerShape(26.dp),
                    maxLines = 4,
                )
                if (draft.isBlank()) {
                    IconButton(
                        onClick = {
                            val granted = androidx.core.content.ContextCompat.checkSelfPermission(
                                context, android.Manifest.permission.RECORD_AUDIO,
                            ) == android.content.pm.PackageManager.PERMISSION_GRANTED
                            if (granted) beginRecording() else micPermission.launch(android.Manifest.permission.RECORD_AUDIO)
                        },
                    ) {
                        Icon(androidx.compose.material.icons.Icons.Outlined.Mic, "Record a voice note")
                    }
                } else {
                    IconButton(
                        onClick = { vm.send(draft, me?.id); draft = "" },
                        modifier = Modifier.clip(RoundedCornerShape(50)).background(MaterialTheme.colorScheme.primary),
                    ) {
                        Icon(Icons.AutoMirrored.Outlined.Send, "Send", tint = MaterialTheme.colorScheme.onPrimary)
                    }
                }
            }
        }
    }
}

/** Play/pause for a voice note streamed from its URL. */
@Composable
private fun VoiceNote(url: String?, durationSeconds: Int?, tint: androidx.compose.ui.graphics.Color) {
    var playing by remember { mutableStateOf(false) }
    val player = remember { android.media.MediaPlayer() }
    androidx.compose.runtime.DisposableEffect(Unit) { onDispose { runCatching { player.release() } } }

    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        IconButton(
            onClick = {
                if (url == null) return@IconButton
                if (playing) {
                    runCatching { player.pause() }
                    playing = false
                } else {
                    runCatching {
                        player.reset()
                        player.setDataSource(url)
                        player.setOnPreparedListener { it.start(); playing = true }
                        player.setOnCompletionListener { playing = false }
                        player.setOnErrorListener { _, _, _ -> playing = false; true }
                        player.prepareAsync()
                    }
                }
            },
        ) {
            Icon(
                if (playing) androidx.compose.material.icons.Icons.Outlined.Pause else androidx.compose.material.icons.Icons.Outlined.PlayArrow,
                if (playing) "Pause voice note" else "Play voice note",
                tint = tint,
            )
        }
        Text(
            "Voice note" + (durationSeconds?.let { "  %d:%02d".format(it / 60, it % 60) } ?: ""),
            style = MaterialTheme.typography.bodyMedium,
            color = tint,
        )
    }
}

@Composable
private fun Bubble(
    message: Message,
    mine: Boolean,
    otherLastSeen: String?,
    onQuickReply: (String) -> Unit,
    onOpenListing: (Int) -> Unit,
    offerActions: com.choropia.app.ui.offers.OfferCardActions,
    onDelete: () -> Unit,
) {
    val pendingSend = (message.id ?: 0) < 0
    Row(Modifier.fillMaxWidth(), horizontalArrangement = if (mine) Arrangement.End else Arrangement.Start) {
        Column(
            Modifier
                .fillMaxWidth(0.82f),
            horizontalAlignment = if (mine) Alignment.End else Alignment.Start,
        ) {
            Column(
                Modifier
                    .clip(
                        RoundedCornerShape(
                            topStart = 18.dp, topEnd = 18.dp,
                            bottomStart = if (mine) 18.dp else 4.dp,
                            bottomEnd = if (mine) 4.dp else 18.dp,
                        )
                    )
                    .background(
                        when {
                            // The offer card draws its own surface, border and corners.
                            message.type == "offer" && message.offer != null && !message.is_deleted -> androidx.compose.ui.graphics.Color.Transparent
                            mine && message.type != "listing_ref" -> MaterialTheme.colorScheme.primary
                            else -> MaterialTheme.colorScheme.surfaceContainer
                        }
                    )
                    .padding(
                        if (message.type == "offer" && message.offer != null && !message.is_deleted) PaddingValues(0.dp)
                        else PaddingValues(horizontal = 14.dp, vertical = 9.dp),
                    ),
            ) {
                val textColor = if (mine) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onSurface
                if (message.is_deleted) {
                    Text("Message deleted", style = MaterialTheme.typography.bodyMedium, color = textColor)
                } else if (message.type == "listing_ref") {
                    ListingReferenceBubble(message, mine, onQuickReply, onOpenListing)
                } else if (message.type == "offer" && message.offer != null) {
                    com.choropia.app.ui.offers.OfferCard(message.offer, offerActions)
                } else when (message.attachment_type) {
                    "uploading" -> Text("Sending attachment...", style = MaterialTheme.typography.bodyMedium, color = textColor)
                    "image" -> coil.compose.AsyncImage(
                        model = message.attachment,
                        contentDescription = "Photo",
                        contentScale = androidx.compose.ui.layout.ContentScale.Crop,
                        modifier = Modifier
                            .width(220.dp)
                            .height(220.dp)
                            .clip(RoundedCornerShape(12.dp)),
                    )
                    "audio" -> VoiceNote(message.attachment, message.duration_seconds, textColor)
                    "file" -> Text("Document attached", style = MaterialTheme.typography.bodyMedium, color = textColor)
                }

                if (message.body.isNotBlank() && message.type != "offer") {
                    Text(
                        message.body,
                        style = MaterialTheme.typography.bodyLarge,
                        color = textColor,
                        modifier = Modifier.padding(top = if (message.attachment_type.isNotBlank()) 6.dp else 0.dp),
                    )
                }
            }
            val seen = message.read_at != null
            val delivered = !otherLastSeen.isNullOrBlank() && !message.created_at.isNullOrBlank() && otherLastSeen >= message.created_at
            val ticks = if (!mine || message.is_deleted || message.type != "text" || pendingSend) "" else if (seen || delivered) "  ✓✓" else "  ✓"
            Row(Modifier.padding(horizontal = 6.dp, vertical = 2.dp), verticalAlignment = Alignment.CenterVertically) {
                Text(
                    if (pendingSend) "Sending…" else shortDateTime(message.created_at),
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.outline,
                )
                if (ticks.isNotEmpty()) {
                    Text(
                        ticks,
                        style = MaterialTheme.typography.labelSmall,
                        color = if (seen) androidx.compose.ui.graphics.Color(0xFF0EA5E9) else MaterialTheme.colorScheme.outline,
                    )
                }
            }
        }
        // WhatsApp-style options on any message: Copy text for everyone, Delete for everyone on your own.
        if (message.type == "text" && !message.is_deleted && !pendingSend && (message.body.isNotBlank() || mine)) {
            var menuExpanded by remember(message.id) { mutableStateOf(false) }
            val clipboard = androidx.compose.ui.platform.LocalClipboardManager.current
            val menuContext = LocalContext.current
            Box {
                IconButton(onClick = { menuExpanded = true }) {
                    Icon(
                        Icons.Outlined.MoreVert,
                        contentDescription = "Message options",
                        tint = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                DropdownMenu(expanded = menuExpanded, onDismissRequest = { menuExpanded = false }) {
                    if (message.body.isNotBlank()) {
                        DropdownMenuItem(
                            text = { Text("Copy text") },
                            onClick = {
                                menuExpanded = false
                                clipboard.setText(androidx.compose.ui.text.AnnotatedString(message.body))
                                android.widget.Toast.makeText(menuContext, "Copied", android.widget.Toast.LENGTH_SHORT).show()
                            },
                        )
                    }
                    if (mine) {
                        DropdownMenuItem(
                            text = { Text("Delete for everyone", color = MaterialTheme.colorScheme.error) },
                            onClick = { menuExpanded = false; onDelete() },
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun ListingReferenceBubble(
    message: Message,
    showQuickReplies: Boolean,
    onQuickReply: (String) -> Unit,
    onOpenListing: (Int) -> Unit,
) {
    val snapshot = message.listing_snapshot
    val status = when (message.listing_status ?: snapshot?.status) {
        "active" -> "Available"
        "sold" -> "Sold"
        else -> "No longer listed"
    }
    Column(
        Modifier.width(260.dp)
            .clip(RoundedCornerShape(14.dp))
            .background(MaterialTheme.colorScheme.surface)
            .then(if (message.listing != null) Modifier.clickable { onOpenListing(message.listing) } else Modifier),
    ) {
        Row(
            Modifier.fillMaxWidth().padding(10.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            if (snapshot?.thumbnail != null) {
                coil.compose.AsyncImage(
                    model = snapshot.thumbnail,
                    contentDescription = snapshot.title,
                    contentScale = androidx.compose.ui.layout.ContentScale.Crop,
                    modifier = Modifier.width(64.dp).height(64.dp).clip(RoundedCornerShape(10.dp)),
                )
            }
            Column(Modifier.weight(1f)) {
                Text(snapshot?.title?.ifBlank { "Listing" } ?: "Listing", style = MaterialTheme.typography.titleSmall, maxLines = 2)
                snapshot?.price_kobo?.let {
                    Text(formatNaira((it / 100.0).toString()), style = MaterialTheme.typography.bodyMedium)
                }
                Text(status, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
        if (showQuickReplies) {
            Column(Modifier.padding(start = 10.dp, end = 10.dp, bottom = 10.dp)) {
                listOf("Is this still available?", "Can you lower the price?").forEach { reply ->
                    Text(
                        reply,
                        color = MaterialTheme.colorScheme.primary,
                        style = MaterialTheme.typography.labelMedium,
                        modifier = Modifier
                            .clip(RoundedCornerShape(50))
                            .clickable { onQuickReply(reply) }
                            .padding(horizontal = 10.dp, vertical = 7.dp),
                    )
                }
            }
        }
    }
}
