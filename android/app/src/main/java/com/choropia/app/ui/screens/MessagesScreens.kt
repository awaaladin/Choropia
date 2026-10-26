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
import androidx.compose.material.icons.outlined.Pause
import androidx.compose.material.icons.outlined.PlayArrow
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
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
            c.listing_title.lowercase().contains(q) ||
            (last?.body ?: "").lowercase().contains(q)
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
                                    conversation.listing_title,
                                    style = MaterialTheme.typography.labelMedium,
                                    color = MaterialTheme.colorScheme.secondary,
                                    maxLines = 1,
                                    overflow = TextOverflow.Ellipsis,
                                )
                                Text(
                                    if (last == null) "Say hello 👋" else (if (mine) "You: " else "") + last.body,
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
                    if (incoming.conversation == conversationId && server.none { it.id == incoming.id && incoming.id != null }) {
                        server = server + incoming
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
        runCatching { repo.messages(conversationId) }.onSuccess { latest ->
            if (latest.size != server.size || latest.lastOrNull()?.id != server.lastOrNull()?.id) {
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
fun ChatScreen(conversationId: Int, onBack: () -> Unit) {
    val repo = LocalRepository.current
    val session = LocalSession.current
    val vm = rememberVm(key = "chat-$conversationId") { ChatViewModel(conversationId, repo) }
    val state by vm.state.collectAsState()
    val me by session.user.collectAsState()
    var draft by remember { mutableStateOf("") }
    val listState = rememberLazyListState()
    val context = LocalContext.current
    val recorder = remember { com.choropia.app.ui.util.VoiceRecorder(context) }
    var recording by remember { mutableStateOf(false) }
    var recordedSeconds by remember { mutableStateOf(0) }
    androidx.compose.runtime.DisposableEffect(Unit) { onDispose { recorder.cancel() } }

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
                        Bubble(message, mine)
                    }
                }
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
private fun Bubble(message: Message, mine: Boolean) {
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
                    .background(if (mine) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.surfaceContainer)
                    .padding(horizontal = 14.dp, vertical = 9.dp),
            ) {
                val textColor = if (mine) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onSurface
                when (message.attachment_type) {
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
                if (message.body.isNotBlank()) {
                    Text(
                        message.body,
                        style = MaterialTheme.typography.bodyLarge,
                        color = textColor,
                        modifier = Modifier.padding(top = if (message.attachment_type.isNotBlank()) 6.dp else 0.dp),
                    )
                }
            }
            Text(
                if (pendingSend) "Sending…" else shortDateTime(message.created_at),
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.outline,
                modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
            )
        }
    }
}

