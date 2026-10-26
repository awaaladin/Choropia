package com.choropia.app.ui

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import com.choropia.app.data.repository.ChoropiaRepository
import com.choropia.app.navigation.ChoropiaNavHost
import com.choropia.app.session.Session
import com.choropia.app.ui.components.BrandSplash
import com.choropia.app.ui.theme.ChoropiaTheme
import kotlinx.coroutines.delay
import kotlinx.coroutines.withTimeoutOrNull

/**
 * Root of the app. On a cold start (the equivalent of a hard refresh) it shows the Full brand
 * loader — mark breathing with a reflection while the wordmark slides out and back — until the
 * session check against the backend has finished, then cross-fades into the app.
 */
@Composable
fun ChoropiaRoot(repository: ChoropiaRepository, session: Session) {
    val themeMode by repository.themeModeFlow.collectAsState(initial = "system")

    ChoropiaTheme(themeMode) {
        CompositionLocalProvider(LocalRepository provides repository, LocalSession provides session) {
            // rememberSaveable: rotating the phone or a theme change must not replay the splash.
            var splashDone by rememberSaveable { mutableStateOf(false) }

            LaunchedEffect(Unit) {
                if (!splashDone) {
                    val started = System.currentTimeMillis()
                    // Wait for the session check, but never strand the user on the splash.
                    withTimeoutOrNull(6_000) {
                        while (!session.ready.value) delay(50)
                    }
                    // Let the wordmark finish sliding out so the launch feels intentional, not cut off.
                    val elapsed = System.currentTimeMillis() - started
                    if (elapsed < MIN_SPLASH_MS) delay(MIN_SPLASH_MS - elapsed)
                    splashDone = true
                }
            }

            Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
                AnimatedContent(
                    targetState = splashDone,
                    transitionSpec = { fadeIn(tween(420)) togetherWith fadeOut(tween(320)) },
                    label = "splash",
                ) { done ->
                    if (done) ChoropiaNavHost() else BrandSplash()
                }
            }
        }
    }
}

private const val MIN_SPLASH_MS = 2_000L
