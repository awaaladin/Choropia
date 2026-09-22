package com.choropia.app.data

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map

private val Context.dataStore by preferencesDataStore(name = "choropia_auth")

/**
 * Holds the JWT access/refresh pair. Mirrors the web frontend's use of localStorage — auth is
 * fully token-based, there is no session/cookie involved anywhere in the Choropia stack.
 */
class TokenManager(private val context: Context) {
    private val accessKey = stringPreferencesKey("access_token")
    private val refreshKey = stringPreferencesKey("refresh_token")

    val accessTokenFlow = context.dataStore.data.map { it[accessKey] }
    val isLoggedInFlow = context.dataStore.data.map { it[refreshKey] != null }

    suspend fun getAccessToken(): String? = context.dataStore.data.first()[accessKey]
    suspend fun getRefreshToken(): String? = context.dataStore.data.first()[refreshKey]

    suspend fun saveTokens(access: String, refresh: String?) {
        context.dataStore.edit { prefs ->
            prefs[accessKey] = access
            if (refresh != null) prefs[refreshKey] = refresh
        }
    }

    suspend fun clear() {
        context.dataStore.edit { it.clear() }
    }
}
