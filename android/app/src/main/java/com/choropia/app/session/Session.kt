package com.choropia.app.session

import com.choropia.app.data.model.User
import com.choropia.app.data.repository.ChoropiaRepository
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.launch

/**
 * App-wide auth state: who is logged in, and the unread-notification badge.
 * Follows the token store, so a refresh failure (session expired) drops the UI to logged-out
 * automatically.
 */
class Session(private val repository: ChoropiaRepository) {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)

    private val _user = MutableStateFlow<User?>(null)
    val user: StateFlow<User?> = _user.asStateFlow()

    private val _loggedIn = MutableStateFlow(false)
    val loggedIn: StateFlow<Boolean> = _loggedIn.asStateFlow()

    private val _unread = MutableStateFlow(0)
    val unreadNotifications: StateFlow<Int> = _unread.asStateFlow()

    /** True once the first launch check (token present? who am I?) has finished. */
    private val _ready = MutableStateFlow(false)
    val ready: StateFlow<Boolean> = _ready.asStateFlow()

    init {
        scope.launch {
            repository.isLoggedInFlow.distinctUntilChanged().collect { loggedIn ->
                _loggedIn.value = loggedIn
                if (loggedIn) {
                    runCatching { repository.me() }.onSuccess { _user.value = it }
                    refreshUnread()
                } else {
                    _user.value = null
                    _unread.value = 0
                }
                _ready.value = true
            }
        }
        // Keep the bell badge fresh without a socket (works on serverless hosting too).
        scope.launch {
            while (true) {
                delay(45_000)
                if (_loggedIn.value) refreshUnread()
            }
        }
    }

    fun setUser(user: User) {
        _user.value = user
    }

    suspend fun refreshUser() {
        if (_loggedIn.value) runCatching { repository.me() }.onSuccess { _user.value = it }
    }

    suspend fun refreshUnread() {
        if (!_loggedIn.value) return
        runCatching { repository.notifications() }.onSuccess { list -> _unread.value = list.count { !it.is_read } }
    }

    fun clearUnread() {
        _unread.value = 0
    }

    suspend fun logout() = repository.logout()
}
