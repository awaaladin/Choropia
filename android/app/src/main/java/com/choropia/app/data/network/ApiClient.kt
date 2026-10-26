package com.choropia.app.data.network

import com.choropia.app.BuildConfig
import com.choropia.app.data.TokenManager
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.Json
import okhttp3.Authenticator
import okhttp3.Interceptor
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.Route
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory
import java.util.concurrent.TimeUnit

/**
 * Builds the Retrofit client used for every API call. Auth is a plain Bearer header (no cookies).
 *
 *  - The auth endpoints (login, register, refresh) never carry a token: a stale one makes DRF answer 401 before the view even
 *    runs, which would make logging in impossible after the access token expired.
 *  - On a 401 the [Authenticator] performs one refresh and retries; if the refresh token is dead
 *    the session is cleared so the UI drops back to the logged-out state.
 */
object ApiClient {
    val json = Json { ignoreUnknownKeys = true; encodeDefaults = true; explicitNulls = false }

    fun create(tokenManager: TokenManager): ChoropiaApi {
        val authInterceptor = Interceptor { chain ->
            val original = chain.request()
            val isAuthEndpoint = original.url.encodedPath.contains("/auth/")
            val token = if (isAuthEndpoint) null else runBlocking { tokenManager.getAccessToken() }
            val request = if (token != null) {
                original.newBuilder().header("Authorization", "Bearer $token").build()
            } else {
                original
            }
            chain.proceed(request)
        }

        val authenticator = Authenticator { _: Route?, response: Response ->
            // Never try to "refresh" a failed login/refresh, and never loop.
            if (response.request.url.encodedPath.contains("/auth/")) return@Authenticator null
            if (response.request.header("X-Auth-Retry") != null) return@Authenticator null
            if (response.request.header("Authorization") == null) return@Authenticator null

            val newAccess = synchronized(this) {
                runBlocking {
                    val sentToken = response.request.header("Authorization")?.removePrefix("Bearer ")
                    val current = tokenManager.getAccessToken()
                    // Another request already refreshed while this one was in flight.
                    if (current != null && current != sentToken) return@runBlocking current

                    val refreshToken = tokenManager.getRefreshToken() ?: return@runBlocking null
                    try {
                        val result = buildRetrofit(OkHttpClient())
                            .create(ChoropiaApi::class.java)
                            .refresh(RefreshRequest(refreshToken))
                        tokenManager.saveTokens(result.access, result.refresh)
                        result.access
                    } catch (e: retrofit2.HttpException) {
                        // Refresh token rejected: the session is over.
                        if (e.code() == 401 || e.code() == 400) tokenManager.clear()
                        null
                    } catch (e: Exception) {
                        null
                    }
                }
            } ?: return@Authenticator null

            response.request.newBuilder()
                .header("Authorization", "Bearer $newAccess")
                .header("X-Auth-Retry", "1")
                .build()
        }

        val logging = HttpLoggingInterceptor().apply {
            level = if (BuildConfig.DEBUG) HttpLoggingInterceptor.Level.BASIC else HttpLoggingInterceptor.Level.NONE
            redactHeader("Authorization")
        }

        val client = OkHttpClient.Builder()
            .connectTimeout(20, TimeUnit.SECONDS)
            .readTimeout(40, TimeUnit.SECONDS)   // Vercel cold starts can be slow
            .writeTimeout(60, TimeUnit.SECONDS)  // multipart photo uploads
            .addInterceptor(authInterceptor)
            .authenticator(authenticator)
            .addInterceptor(logging)
            .build()

        return buildRetrofit(client).create(ChoropiaApi::class.java)
    }

    private fun buildRetrofit(client: OkHttpClient): Retrofit {
        val contentType = "application/json".toMediaType()
        return Retrofit.Builder()
            .baseUrl(BuildConfig.API_BASE_URL)
            .client(client)
            .addConverterFactory(json.asConverterFactory(contentType))
            .build()
    }
}
