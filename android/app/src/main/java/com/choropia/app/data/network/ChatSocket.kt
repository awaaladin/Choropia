package com.choropia.app.data.network

import com.choropia.app.BuildConfig
import com.choropia.app.data.model.Message
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import okio.ByteString

@Serializable private data class OutgoingChatMessage(val body: String)

/** Thin wrapper around the /ws/chat/<id>/ endpoint. Auth is a query-string JWT, same contract
 * as the web frontend uses (see common/ws_auth.py on the backend). */
class ChatSocket(private val client: OkHttpClient = OkHttpClient()) {
    private val json = Json { ignoreUnknownKeys = true }
    private var webSocket: WebSocket? = null

    private val _incoming = MutableSharedFlow<Message>(extraBufferCapacity = 64)
    val incoming = _incoming.asSharedFlow()

    fun connect(conversationId: Int, accessToken: String) {
        val url = "${BuildConfig.WS_BASE_URL}/ws/chat/$conversationId/?token=$accessToken"
        val request = Request.Builder().url(url).build()
        webSocket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onMessage(webSocket: WebSocket, text: String) {
                runCatching { json.decodeFromString(Message.serializer(), text) }
                    .onSuccess { _incoming.tryEmit(it) }
            }

            override fun onMessage(webSocket: WebSocket, bytes: ByteString) {
                onMessage(webSocket, bytes.utf8())
            }
        })
    }

    /** Returns false if there's no live socket to send on (caller should fall back to REST). */
    fun send(body: String): Boolean {
        val socket = webSocket ?: return false
        return socket.send(json.encodeToString(OutgoingChatMessage.serializer(), OutgoingChatMessage(body)))
    }

    fun disconnect() {
        webSocket?.close(1000, "done")
        webSocket = null
    }
}
