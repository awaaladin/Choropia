package com.choropia.app.ui.screens.chat

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.choropia.app.data.model.Message
import com.choropia.app.data.network.ChatSocket
import com.choropia.app.data.repository.ChoropiaRepository
import kotlinx.coroutines.launch

@Composable
fun ChatScreen(conversationId: Int, repository: ChoropiaRepository) {
    var messages by remember { mutableStateOf<List<Message>>(emptyList()) }
    var draft by remember { mutableStateOf("") }
    val socket = remember { ChatSocket() }
    val scope = rememberCoroutineScope()

    LaunchedEffect(conversationId) {
        messages = runCatching { repository.getMessages(conversationId) }.getOrDefault(emptyList())

        val token = repository.getAccessTokenOrNull()
        if (token != null) socket.connect(conversationId, token)

        socket.incoming.collect { incoming -> messages = messages + incoming }
    }

    DisposableEffect(conversationId) {
        onDispose { socket.disconnect() }
    }

    Column(modifier = Modifier.fillMaxSize().padding(12.dp)) {
        LazyColumn(modifier = Modifier.weight(1f)) {
            items(messages) { message ->
                Text(message.body, modifier = Modifier.padding(vertical = 4.dp), style = MaterialTheme.typography.bodyMedium)
            }
        }
        Row(modifier = Modifier.fillMaxWidth().padding(top = 8.dp)) {
            OutlinedTextField(
                value = draft,
                onValueChange = { draft = it },
                modifier = Modifier.weight(1f),
                label = { Text("Message") },
            )
            Button(
                onClick = {
                    if (draft.isBlank()) return@Button
                    val body = draft
                    draft = ""
                    scope.launch {
                        // The socket handles the happy path; if it's not connected (e.g. auth
                        // hiccup) fall back to the plain REST endpoint so the message isn't lost.
                        val sentOverSocket = runCatching { socket.send(body) }.getOrDefault(false)
                        if (!sentOverSocket) runCatching { repository.sendMessage(conversationId, body) }
                    }
                },
                modifier = Modifier.padding(start = 8.dp),
            ) { Text("Send") }
        }
    }
}
