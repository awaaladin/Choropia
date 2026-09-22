package com.choropia.app

import android.app.Application
import com.choropia.app.data.TokenManager
import com.choropia.app.data.network.ApiClient
import com.choropia.app.data.repository.ChoropiaRepository

class ChoropiaApp : Application() {
    lateinit var repository: ChoropiaRepository
        private set

    override fun onCreate() {
        super.onCreate()
        val tokenManager = TokenManager(this)
        val api = ApiClient.create(tokenManager)
        repository = ChoropiaRepository(api, tokenManager)
    }
}
