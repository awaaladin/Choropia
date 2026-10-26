package com.choropia.app.data.network

import com.choropia.app.BuildConfig
import com.choropia.app.data.model.Message
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.serialization.json.Json
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener

/**
 * Optional realtime channel for `/ws/chat/<id>/`. Vercel's serverless runtime can't hold
 * WebSockets, so this only connects when `WS_BASE_URL` points at the Docker realtime host; the
 * chat screen polls REST either way, so a missing/dropped socket only costs latency, never data.
 */
class ChatSocket(private val client: OkHttpClient = OkHttpClient()) {
    private val json = Json { ignoreUnknownKeys = true }
    private var webSocket: WebSocket? = null

    private val _incoming = MutableSharedFlow<Message>(extraBufferCapacity = 64)
    val incoming = _incoming.asSharedFlow()

    val isAvailable: Boolean get() = BuildConfig.WS_BASE_URL.isNotBlank()

    fun connect(conversationId: Int, accessToken: String) {
        if (!isAvailable || webSocket != null) return
        val url = "${BuildConfig.WS_BASE_URL.trimEnd('/')}/ws/chat/$conversationId/?token=$accessToken"
        val request = Request.Builder().url(url).build()
        webSocket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onMessage(webSocket: WebSocket, text: String) {
                runCatching { json.decodeFromString(Message.serializer(), text) }
                    .onSuccess { _incoming.tryEmit(it) }
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                this@ChatSocket.webSocket = null
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                this@ChatSocket.webSocket = null
            }
        })
    }

    fun disconnect() {
        webSocket?.close(1000, "done")
        webSocket = null
    }
}
