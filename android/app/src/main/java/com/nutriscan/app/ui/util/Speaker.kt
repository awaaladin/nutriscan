package com.nutriscan.app.ui.util

import android.content.Context
import android.os.Handler
import android.os.Looper
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import com.nutriscan.app.data.model.ScanResponse
import java.util.Locale

/**
 * Reads text aloud with Android's built-in text-to-speech: no download, no
 * network, no cost. Prefers Nigerian English and falls back to whatever English
 * voice the phone has. [isSpeaking] is Compose state so buttons can flip between
 * "read aloud" and "stop".
 */
class Speaker(context: Context) : TextToSpeech.OnInitListener {
    private val main = Handler(Looper.getMainLooper())
    private var tts: TextToSpeech? = TextToSpeech(context.applicationContext, this)
    private var ready = false
    private var pending: String? = null
    private var remaining = 0

    var isSpeaking by mutableStateOf(false)
        private set

    /** Null until the engine has started; false if the phone has no usable voice. */
    var available by mutableStateOf<Boolean?>(null)
        private set

    override fun onInit(status: Int) {
        val engine = tts
        if (status != TextToSpeech.SUCCESS || engine == null) {
            available = false
            return
        }
        var result = engine.setLanguage(Locale("en", "NG"))
        if (result == TextToSpeech.LANG_MISSING_DATA || result == TextToSpeech.LANG_NOT_SUPPORTED) {
            result = engine.setLanguage(Locale.ENGLISH)
        }
        if (result == TextToSpeech.LANG_MISSING_DATA || result == TextToSpeech.LANG_NOT_SUPPORTED) {
            available = false
            return
        }
        engine.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
            override fun onStart(utteranceId: String?) = Unit
            override fun onDone(utteranceId: String?) = finishOne()
            @Deprecated("Deprecated in Java")
            override fun onError(utteranceId: String?) = finishOne()
        })
        ready = true
        available = true
        pending?.let { speak(it) }
        pending = null
    }

    private fun finishOne() {
        main.post {
            remaining = (remaining - 1).coerceAtLeast(0)
            if (remaining == 0) isSpeaking = false
        }
    }

    /** Replaces anything already being spoken. */
    fun speak(text: String) {
        val engine = tts ?: return
        if (!ready) {
            pending = text // engine still starting; speak as soon as it is
            return
        }
        val chunks = chunk(clean(text))
        if (chunks.isEmpty()) return
        engine.stop()
        remaining = chunks.size
        isSpeaking = true
        chunks.forEachIndexed { index, part ->
            engine.speak(
                part,
                if (index == 0) TextToSpeech.QUEUE_FLUSH else TextToSpeech.QUEUE_ADD,
                null,
                "nutriscan-$index",
            )
        }
    }

    fun stop() {
        tts?.stop()
        pending = null
        remaining = 0
        isSpeaking = false
    }

    fun shutdown() {
        tts?.stop()
        tts?.shutdown()
        tts = null
        ready = false
    }

    /** Engines cap a single utterance (~4000 chars); split on sentence ends. */
    private fun chunk(text: String, max: Int = 3000): List<String> {
        if (text.isBlank()) return emptyList()
        val parts = mutableListOf<String>()
        var current = StringBuilder()
        for (sentence in text.split(Regex("(?<=[.!?])\\s+"))) {
            if (current.length + sentence.length > max && current.isNotEmpty()) {
                parts += current.toString()
                current = StringBuilder()
            }
            current.append(sentence).append(' ')
        }
        if (current.isNotBlank()) parts += current.toString().trim()
        return parts
    }

    /** Drops markdown and symbols the voice would read out ("asterisk"). */
    private fun clean(text: String): String =
        text.replace(Regex("[*_#`>]+"), "").replace("%", " percent").replace(Regex("\\s+"), " ").trim()
}

@Composable
fun rememberSpeaker(): Speaker {
    val context = LocalContext.current
    val speaker = remember { Speaker(context) }
    DisposableEffect(speaker) { onDispose { speaker.shutdown() } }
    return speaker
}

/** What gets read aloud for a scan: the product, the verdict, what to watch out
 * for, and how far to trust it -- the same facts the screen shows, in sentences. */
fun spokenSummary(result: ScanResponse): String {
    val product = result.product
    val parts = mutableListOf<String>()
    parts += product.name + (product.brand?.takeIf { it.isNotBlank() }?.let { " by $it" } ?: "") + "."
    if (result.score != null && result.label != null) {
        parts += "Health score ${result.score} out of 10, rated ${result.label}."
        if (result.insufficient_data) {
            parts += "This is based on incomplete data, missing ${result.missing_nutrients.joinToString(", ")}, " +
                "so the real result could only be worse."
        }
    } else if (result.label == "Incomplete") {
        parts += "There is no health score yet because the " +
            (result.missing_nutrients.joinToString(", ").ifBlank { "nutrition" }) + " information is missing."
    }
    result.diabetic_risk?.let { parts += "Diabetic risk: $it." }
    val concerns = result.flags.map { it.replace('_', ' ') }
    parts += if (concerns.isEmpty()) "No major nutrition concerns." else "Watch out for: ${concerns.joinToString(", ")}."
    product.integrity?.let { integrity ->
        parts += "Authenticity: ${integrity.headline}."
        integrity.reasons.firstOrNull()?.let { parts += it }
    }
    product.nafdac_number?.takeIf { it.isNotBlank() }?.let {
        parts += "NAFDAC number $it, " + if (product.nafdac_verified) "confirmed." else "not yet confirmed."
    }
    if (result.is_estimated) parts += "These details were read from photos, so please double check them on the pack."
    parts += "This is educational information, not medical advice."
    return parts.joinToString(" ")
}
