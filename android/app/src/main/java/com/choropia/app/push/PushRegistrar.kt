package com.choropia.app.push

import com.choropia.app.data.repository.ChoropiaRepository
import com.google.firebase.messaging.FirebaseMessaging
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlin.coroutines.resume

/**
 * Hands this phone's Firebase token to the server after sign-in, so it can push messages and order updates.
 * Everything here is best-effort: with Firebase not configured (no google-services.json in the build) it quietly does nothing.
 */
object PushRegistrar {
    suspend fun currentToken(): String? = runCatching {
        suspendCancellableCoroutine<String?> { cont ->
            FirebaseMessaging.getInstance().token.addOnCompleteListener { task ->
                cont.resume(if (task.isSuccessful) task.result else null)
            }
        }
    }.getOrNull()

    suspend fun register(repository: ChoropiaRepository) {
        val token = currentToken() ?: return
        runCatching { repository.registerPushToken(token) }
    }

    suspend fun unregister(repository: ChoropiaRepository) {
        val token = currentToken() ?: return
        runCatching { repository.unregisterPushToken(token) }
    }
}
