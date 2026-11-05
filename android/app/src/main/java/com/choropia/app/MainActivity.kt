package com.choropia.app

import android.Manifest
import android.os.Build
import android.os.Bundle
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import com.choropia.app.ui.ChoropiaRoot

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        // The system splash (navy + mark) hands over to the animated in-app loader.
        installSplashScreen()
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        // Android 13+ asks before an app may show notifications (messages, orders, deliveries).
        com.choropia.app.push.PushService.ensureChannel(this)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            registerForActivityResult(ActivityResultContracts.RequestPermission()) { }.launch(Manifest.permission.POST_NOTIFICATIONS)
        }

        val app = application as ChoropiaApp
        setContent {
            ChoropiaRoot(repository = app.repository, session = app.session)
        }
    }
}
