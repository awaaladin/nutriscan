package com.nutriscan.app.ui.screens

import android.app.Activity
import android.content.ActivityNotFoundException
import android.content.Intent
import android.speech.RecognizerIntent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.Send
import androidx.compose.material.icons.automirrored.rounded.VolumeUp
import androidx.compose.material.icons.rounded.Mic
import androidx.compose.material.icons.rounded.Stop
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.unit.dp
import com.nutriscan.app.data.local.AppPreferencesManager
import com.nutriscan.app.data.model.AskSource
import com.nutriscan.app.data.model.AskTurn
import com.nutriscan.app.data.repository.NutriScanRepository
import com.nutriscan.app.ui.MainViewModel
import com.nutriscan.app.ui.ScanUiState
import com.nutriscan.app.ui.components.NsScreenScaffold
import com.nutriscan.app.ui.util.rememberSpeaker
import kotlinx.coroutines.launch

private data class ChatMessage(
    val fromUser: Boolean,
    val text: String,
    val sources: List<AskSource> = emptyList(),
    val webResearch: Boolean = false,
)

private val suggestions = listOf(
    "Is this OK for me?",
    "What do the ingredients do?",
    "Is it healthy for a diabetic?",
    "Who makes it and is it registered?",
    "Is there a healthier alternative?",
)

/**
 * "Ask about this product": a small chat where the user asks follow-ups. The
 * server answers from our own data about the product (score, ingredients,
 * NAFDAC and authenticity status, community reports, the user's health goals)
 * and researches the rest. Answers can be read aloud, and each one says whether
 * live web research was used so the user knows how far to trust it.
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun AskScreen(
    viewModel: MainViewModel,
    repository: NutriScanRepository,
    preferences: AppPreferencesManager,
    barcode: String,
    onBack: () -> Unit,
) {
    val scope = rememberCoroutineScope()
    val speaker = rememberSpeaker()
    val uriHandler = LocalUriHandler.current
    val autoRead by preferences.autoReadAloud.collectAsState(initial = false)
    val scanState by viewModel.scanState.collectAsState()
    val productName = (scanState as? ScanUiState.Success)?.result?.product?.takeIf { it.barcode == barcode }?.name

    val messages = remember { mutableStateListOf<ChatMessage>() }
    var input by remember { mutableStateOf("") }
    var sending by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var speakingIndex by remember { mutableStateOf<Int?>(null) }
    val listState = rememberLazyListState()

    fun ask(question: String) {
        val trimmed = question.trim()
        if (trimmed.isBlank() || sending) return
        val history = messages.map { AskTurn(if (it.fromUser) "user" else "assistant", it.text) }
        messages += ChatMessage(fromUser = true, text = trimmed)
        input = ""
        error = null
        sending = true
        scope.launch {
            repository.ask(barcode, trimmed, history)
                .onSuccess { reply ->
                    messages += ChatMessage(false, reply.answer, reply.sources, reply.web_research)
                    if (autoRead) {
                        speakingIndex = messages.lastIndex
                        speaker.speak(reply.answer)
                    }
                }
                .onFailure { error = it.message ?: "Something went wrong. Please try again." }
            sending = false
        }
    }

    // Keep the newest message in view.
    LaunchedEffect(messages.size, sending) {
        if (messages.isNotEmpty()) listState.animateScrollToItem(messages.size - 1)
    }

    val voiceLauncher = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        if (result.resultCode == Activity.RESULT_OK) {
            result.data?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)?.firstOrNull()?.let { input = it }
        }
    }

    NsScreenScaffold(title = "Ask about this product", onBack = { speaker.stop(); onBack() }) { padding ->
        Column(modifier = Modifier.fillMaxSize().padding(padding).imePadding()) {
            LazyColumn(
                state = listState,
                modifier = Modifier.weight(1f).fillMaxWidth().padding(horizontal = 16.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                item {
                    Spacer(Modifier.height(8.dp))
                    Text(
                        "Ask anything about ${productName ?: "this product"}: ingredients, whether it suits you, " +
                            "who makes it. Answers use what NutriScan knows about the product and your health profile. " +
                            "General information, not medical advice.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                if (messages.isEmpty()) {
                    item {
                        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            suggestions.forEach { suggestion ->
                                AssistChip(onClick = { ask(suggestion) }, label = { Text(suggestion) })
                            }
                        }
                    }
                }
                items(messages.size) { index ->
                    val message = messages[index]
                    Box(modifier = Modifier.fillMaxWidth(), contentAlignment = if (message.fromUser) Alignment.CenterEnd else Alignment.CenterStart) {
                        Card(
                            shape = RoundedCornerShape(16.dp),
                            colors = CardDefaults.cardColors(
                                containerColor = if (message.fromUser) MaterialTheme.colorScheme.primaryContainer
                                else MaterialTheme.colorScheme.surfaceVariant,
                            ),
                            modifier = Modifier.widthIn(max = 320.dp),
                        ) {
                            Column(modifier = Modifier.padding(12.dp)) {
                                Text(message.text, style = MaterialTheme.typography.bodyMedium)
                                if (!message.fromUser) {
                                    Spacer(Modifier.height(4.dp))
                                    Text(
                                        if (message.webResearch) "Researched on the web" else "From NutriScan's data and the AI's knowledge (no live web search)",
                                        style = MaterialTheme.typography.labelSmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    )
                                    message.sources.forEach { source ->
                                        TextButton(onClick = { uriHandler.openUri(source.url) }) {
                                            Text(source.title, style = MaterialTheme.typography.labelSmall, maxLines = 1)
                                        }
                                    }
                                    val speakingThis = speaker.isSpeaking && speakingIndex == index
                                    IconButton(onClick = {
                                        if (speakingThis) {
                                            speaker.stop()
                                        } else {
                                            speakingIndex = index
                                            speaker.speak(message.text)
                                        }
                                    }) {
                                        Icon(
                                            if (speakingThis) Icons.Rounded.Stop else Icons.AutoMirrored.Rounded.VolumeUp,
                                            contentDescription = if (speakingThis) "Stop reading" else "Read this answer aloud",
                                        )
                                    }
                                }
                            }
                        }
                    }
                }
                if (sending) {
                    item {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            CircularProgressIndicator(modifier = Modifier.height(20.dp).widthIn(max = 20.dp), strokeWidth = 2.dp)
                            Spacer(Modifier.widthIn(min = 8.dp))
                            Text("Researching…", style = MaterialTheme.typography.bodySmall)
                        }
                    }
                }
                error?.let {
                    item { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }
                }
                item { Spacer(Modifier.height(8.dp)) }
            }
            Row(
                modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                OutlinedTextField(
                    value = input,
                    onValueChange = { input = it.take(500) },
                    placeholder = { Text("Ask a question…") },
                    modifier = Modifier.weight(1f),
                    maxLines = 3,
                )
                IconButton(onClick = {
                    val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                        putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                        putExtra(RecognizerIntent.EXTRA_PROMPT, "Ask about this product")
                    }
                    try {
                        voiceLauncher.launch(intent)
                    } catch (_: ActivityNotFoundException) {
                        error = "Voice input isn't available on this phone. Type your question instead."
                    }
                }) { Icon(Icons.Rounded.Mic, contentDescription = "Ask by voice") }
                IconButton(onClick = { ask(input) }, enabled = input.isNotBlank() && !sending) {
                    Icon(Icons.AutoMirrored.Rounded.Send, contentDescription = "Send")
                }
            }
        }
    }
}
