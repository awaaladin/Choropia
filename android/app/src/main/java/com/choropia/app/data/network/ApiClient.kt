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

/**
 * Builds the Retrofit client used for every API call. Auth is a plain Bearer header attached
 * per-request (no cookies) — on a 401 the Authenticator does one synchronous refresh-token call
 * and retries, mirroring the retry-once logic in the web frontend's api.js.
 */
object ApiClient {
    private val json = Json { ignoreUnknownKeys = true; encodeDefaults = true }

    fun create(tokenManager: TokenManager): ChoropiaApi {
        val authInterceptor = Interceptor { chain ->
            val token = runBlocking { tokenManager.getAccessToken() }
            val request = if (token != null) {
                chain.request().newBuilder().addHeader("Authorization", "Bearer $token").build()
            } else {
                chain.request()
            }
            chain.proceed(request)
        }

        val authenticator = Authenticator { _: Route?, response: Response ->
            if (response.request.header("Authorization-Retry") != null) return@Authenticator null

            val newAccessToken = runBlocking {
                val refreshToken = tokenManager.getRefreshToken() ?: return@runBlocking null
                try {
                    val plainRetrofit = buildRetrofit(OkHttpClient())
                    val result = plainRetrofit.create(ChoropiaApi::class.java).refresh(RefreshRequest(refreshToken))
                    tokenManager.saveTokens(result.access, refresh = null)
                    result.access
                } catch (e: Exception) {
                    null
                }
            } ?: return@Authenticator null

            response.request.newBuilder()
                .header("Authorization", "Bearer $newAccessToken")
                .header("Authorization-Retry", "1")
                .build()
        }

        val logging = HttpLoggingInterceptor().apply { level = HttpLoggingInterceptor.Level.BASIC }

        val client = OkHttpClient.Builder()
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
