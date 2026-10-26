package com.choropia.app.data

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.core.stringSetPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map

private val Context.dataStore by preferencesDataStore(name = "choropia_auth")

/**
 * Holds the JWT access/refresh pair plus device-level UI preferences. Mirrors the web
 * frontend's localStorage use — auth is fully token-based, no session/cookie anywhere.
 */
class TokenManager(private val context: Context) {
    private val accessKey = stringPreferencesKey("access_token")
    private val refreshKey = stringPreferencesKey("refresh_token")
    private val themeKey = stringPreferencesKey("theme_mode")
    private val savedKey = stringSetPreferencesKey("saved_listing_ids")

    val isLoggedInFlow: Flow<Boolean> =
        context.dataStore.data.map { it[refreshKey] != null }.distinctUntilChanged()

    /** "system" | "light" | "dark" */
    val themeModeFlow: Flow<String> =
        context.dataStore.data.map { it[themeKey] ?: "system" }.distinctUntilChanged()

    /** Listing ids the user bookmarked on this device (the app's "Watchlist"). */
    val savedIdsFlow: Flow<Set<Int>> = context.dataStore.data
        .map { prefs -> prefs[savedKey].orEmpty().mapNotNull { it.toIntOrNull() }.toSet() }
        .distinctUntilChanged()

    suspend fun toggleSaved(listingId: Int) {
        context.dataStore.edit { prefs ->
            val current = prefs[savedKey].orEmpty().toMutableSet()
            if (!current.add(listingId.toString())) current.remove(listingId.toString())
            prefs[savedKey] = current
        }
    }

    suspend fun getAccessToken(): String? = context.dataStore.data.first()[accessKey]
    suspend fun getRefreshToken(): String? = context.dataStore.data.first()[refreshKey]

    suspend fun saveTokens(access: String, refresh: String?) {
        context.dataStore.edit { prefs ->
            prefs[accessKey] = access
            if (refresh != null) prefs[refreshKey] = refresh
        }
    }

    suspend fun setThemeMode(mode: String) {
        context.dataStore.edit { it[themeKey] = mode }
    }

    /** Signs out but keeps device preferences such as the theme. */
    suspend fun clear() {
        context.dataStore.edit {
            it.remove(accessKey)
            it.remove(refreshKey)
        }
    }
}
