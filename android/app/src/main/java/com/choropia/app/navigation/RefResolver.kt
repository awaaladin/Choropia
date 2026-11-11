package com.choropia.app.navigation

import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import com.choropia.app.data.network.ApiException
import com.choropia.app.ui.LocalRepository
import com.choropia.app.ui.components.ErrorState
import com.choropia.app.ui.components.ScreenLoader

/**
 * Opens a website link that carries a public code (/listing/<title>-<code>, /chat/<code>, /order/<code>): asks the
 * server which item it is, then hands over to the normal screen. Someone who isn't part of a chat or order gets the
 * server's "not found", the same as on the website.
 */
@Composable
fun RefResolver(kind: String, ref: String, onResolved: (Int) -> Unit) {
    val repo = LocalRepository.current
    var error by remember { mutableStateOf<String?>(null) }
    var attempt by remember { mutableIntStateOf(0) }
    LaunchedEffect(kind, ref, attempt) {
        error = null
        try {
            onResolved(repo.resolveRef(kind, ref))
        } catch (e: ApiException) {
            error = if (e.httpCode == 404) "We couldn't find that. It may have been removed, or it isn't yours to see." else e.message
        }
    }
    val message = error
    if (message == null) {
        ScreenLoader(Modifier.fillMaxSize())
    } else {
        ErrorState(message, onRetry = { attempt += 1 }, modifier = Modifier.fillMaxSize().statusBarsPadding())
    }
}
