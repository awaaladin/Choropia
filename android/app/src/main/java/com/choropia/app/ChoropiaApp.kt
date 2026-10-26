package com.choropia.app

import android.app.Application
import coil.ImageLoader
import coil.ImageLoaderFactory
import coil.disk.DiskCache
import coil.memory.MemoryCache
import com.choropia.app.data.TokenManager
import com.choropia.app.data.network.ApiClient
import com.choropia.app.data.repository.ChoropiaRepository
import com.choropia.app.session.Session

class ChoropiaApp : Application(), ImageLoaderFactory {
    lateinit var repository: ChoropiaRepository
        private set
    lateinit var session: Session
        private set

    override fun onCreate() {
        super.onCreate()
        val tokenManager = TokenManager(this)
        val api = ApiClient.create(tokenManager)
        repository = ChoropiaRepository(this, api, tokenManager)
        session = Session(repository)
    }

    override fun newImageLoader(): ImageLoader = ImageLoader.Builder(this)
        .crossfade(220)
        .memoryCache { MemoryCache.Builder(this).maxSizePercent(0.20).build() }
        .diskCache { DiskCache.Builder().directory(cacheDir.resolve("images")).maxSizeBytes(80L * 1024 * 1024).build() }
        .build()
}
