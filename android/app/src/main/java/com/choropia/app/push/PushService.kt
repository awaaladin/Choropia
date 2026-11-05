package com.choropia.app.push

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import com.choropia.app.ChoropiaApp
import com.choropia.app.MainActivity
import com.choropia.app.R
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

private const val CHANNEL_ID = "choropia_alerts"

/**
 * Receives Firebase push messages. The server sends data-only messages, so every notification is built here and a tap always
 * opens the right screen (choropia://chat/12, choropia://order/7, choropia://listing/3). Without Firebase configured
 * (no google-services.json at build time) this service simply never gets called.
 */
class PushService : FirebaseMessagingService() {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    override fun onNewToken(token: String) {
        val app = application as? ChoropiaApp ?: return
        scope.launch { runCatching { app.repository.registerPushToken(token) } }
    }

    override fun onMessageReceived(message: RemoteMessage) {
        val data = message.data
        val body = data["body"] ?: return
        show(this, data["title"] ?: "Choropia", body, data["target"].orEmpty(), data["target_id"].orEmpty(), data["notification_id"])
    }

    companion object {
        fun ensureChannel(context: Context) {
            if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
            val manager = context.getSystemService(NotificationManager::class.java)
            if (manager.getNotificationChannel(CHANNEL_ID) == null) {
                manager.createNotificationChannel(
                    NotificationChannel(CHANNEL_ID, "Messages and orders", NotificationManager.IMPORTANCE_HIGH).apply {
                        description = "New messages, orders, deliveries and listings from people you follow"
                    },
                )
            }
        }

        fun show(context: Context, title: String, body: String, target: String, targetId: String, notificationId: String?) {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
                ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
            ) return
            ensureChannel(context)

            val open = Intent(context, MainActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
                if (target in setOf("chat", "order", "listing") && targetId.isNotBlank()) {
                    action = Intent.ACTION_VIEW
                    data = Uri.parse("choropia://$target/$targetId")
                }
            }
            val id = notificationId?.toIntOrNull() ?: System.currentTimeMillis().toInt()
            val pending = PendingIntent.getActivity(context, id, open, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
            val notification = NotificationCompat.Builder(context, CHANNEL_ID)
                .setSmallIcon(R.mipmap.ic_launcher)
                .setContentTitle(title)
                .setContentText(body)
                .setStyle(NotificationCompat.BigTextStyle().bigText(body))
                .setAutoCancel(true)
                .setPriority(NotificationCompat.PRIORITY_HIGH)
                .setContentIntent(pending)
                .build()
            NotificationManagerCompat.from(context).notify(id, notification)
        }
    }
}
