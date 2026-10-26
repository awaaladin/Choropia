package com.choropia.app.ui.util

import android.content.Context
import android.media.MediaRecorder
import android.os.Build
import android.os.SystemClock
import java.io.File

/** Records a voice note to an AAC/m4a file in the app cache. One recording at a time. */
class VoiceRecorder(private val context: Context) {
    private var recorder: MediaRecorder? = null
    private var file: File? = null
    private var startedAt = 0L

    val isRecording: Boolean get() = recorder != null

    /** Seconds recorded so far (0 when idle). */
    val elapsedSeconds: Int
        get() = if (recorder == null) 0 else ((SystemClock.elapsedRealtime() - startedAt) / 1000).toInt()

    fun start(): Boolean {
        if (recorder != null) return true
        val target = File.createTempFile("voice_", ".m4a", context.cacheDir)
        @Suppress("DEPRECATION")
        val r = if (Build.VERSION.SDK_INT >= 31) MediaRecorder(context) else MediaRecorder()
        return try {
            r.setAudioSource(MediaRecorder.AudioSource.MIC)
            r.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4)
            r.setAudioEncoder(MediaRecorder.AudioEncoder.AAC)
            r.setAudioEncodingBitRate(48_000)
            r.setAudioSamplingRate(44_100)
            r.setOutputFile(target.absolutePath)
            r.prepare()
            r.start()
            recorder = r
            file = target
            startedAt = SystemClock.elapsedRealtime()
            true
        } catch (e: Exception) {
            runCatching { r.release() }
            target.delete()
            false
        }
    }

    /** Stops and returns the file with its duration, or null if it was too short to be valid. */
    fun stop(): Pair<File, Int>? {
        val r = recorder ?: return null
        val out = file
        val seconds = elapsedSeconds
        recorder = null
        file = null
        return try {
            r.stop()
            r.release()
            if (out != null && seconds >= 1) out to seconds else { out?.delete(); null }
        } catch (e: Exception) {
            // MediaRecorder.stop() throws if nothing meaningful was captured.
            runCatching { r.release() }
            out?.delete()
            null
        }
    }

    fun cancel() {
        val r = recorder ?: return
        val out = file
        recorder = null
        file = null
        runCatching { r.stop() }
        runCatching { r.release() }
        out?.delete()
    }
}
