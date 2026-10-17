package com.nutriscan.app.ui.screens

import android.Manifest
import android.app.Activity
import android.content.ActivityNotFoundException
import android.content.Intent
import android.content.pm.PackageManager
import android.speech.RecognizerIntent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
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
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.Send
import androidx.compose.material.icons.automirrored.rounded.VolumeUp
import androidx.compose.material.icons.rounded.AddAPhoto
import androidx.compose.material.icons.rounded.Close
import androidx.compose.material.icons.rounded.History
import androidx.compose.material.icons.rounded.Mic
import androidx.compose.material.icons.rounded.PhotoLibrary
import androidx.compose.material.icons.rounded.Stop
import androidx.compose.material.icons.rounded.ThumbDown
import androidx.compose.material.icons.rounded.ThumbUp
import androidx.compose.material.icons.rounded.Tune
import androidx.compose.material.icons.rounded.Add
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
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
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.core.content.FileProvider
import coil.compose.AsyncImage
import com.nutriscan.app.data.local.AppPreferencesManager
import com.nutriscan.app.data.model.AskSource
import com.nutriscan.app.data.repository.ChatException
import com.nutriscan.app.data.repository.NutriScanRepository
import com.nutriscan.app.ui.components.NsScreenScaffold
import com.nutriscan.app.ui.theme.NsAmber
import com.nutriscan.app.ui.util.downscaleForUpload
import com.nutriscan.app.ui.util.importForUpload
import com.nutriscan.app.ui.util.rememberSpeaker
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

private const val MAX_ATTACHMENTS = 3

private data class UiMessage(
    val id: Int?,
    val fromUser: Boolean,
    val text: String,
    val photos: List<File> = emptyList(),
    // Photos from an earlier session aren't stored, so only the count is known.
    val photoCount: Int = 0,
    val sources: List<AskSource> = emptyList(),
    val webResearch: Boolean = false,
    val feedback: Int? = null,
)

private val starters = listOf(
    "What should I eat with diabetes?",
    "What is this medicine for? (add a photo)",
    "Read this nutrition table for me (add a photo)",
    "Is it safe to take paracetamol every day?",
    "How can I tell if a product is fake?",
)

/**
 * "Ask NutriScan": a full-page conversation with the assistant, specialised in
 * nutrition and medicines and personal to the user (their health profile, notes
 * and recent scans are used server-side). Photos can be attached -- a food pack,
 * a nutrition table, a medicine box -- and answers can be read aloud and rated.
 * Conversations are saved to the account so they can be reopened or deleted.
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun ChatScreen(
    repository: NutriScanRepository,
    preferences: AppPreferencesManager,
    threadId: Int?,
    onBack: () -> Unit,
    onOpenThreads: () -> Unit,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val speaker = rememberSpeaker()
    val uriHandler = LocalUriHandler.current
    val autoRead by preferences.autoReadAloud.collectAsState(initial = false)
    val introSeen by preferences.assistantIntroSeen.collectAsState(initial = true)
    val listState = rememberLazyListState()

    val messages = remember { mutableStateListOf<UiMessage>() }
    val attachments = remember { mutableStateListOf<File>() }
    var activeThread by remember { mutableStateOf(threadId) }
    var input by remember { mutableStateOf("") }
    var sending by remember { mutableStateOf(false) }
    var loadingThread by remember { mutableStateOf(threadId != null) }
    var error by remember { mutableStateOf<String?>(null) }
    var notice by remember { mutableStateOf<String?>(null) }
    var speakingIndex by remember { mutableStateOf<Int?>(null) }
    var showAttachMenu by remember { mutableStateOf(false) }
    var showSettings by remember { mutableStateOf(false) }

    // Reopen a saved conversation.
    LaunchedEffect(threadId) {
        if (threadId != null) {
            repository.chatThread(threadId)
                .onSuccess { detail ->
                    messages.clear()
                    messages += detail.messages.map {
                        UiMessage(it.id, it.role == "user", it.text, photoCount = it.image_count, sources = it.sources,
                            webResearch = it.web_research, feedback = it.feedback)
                    }
                }
                .onFailure { error = it.message ?: "Couldn't open that conversation." }
            loadingThread = false
        }
    }
    LaunchedEffect(messages.size, sending) {
        if (messages.isNotEmpty()) listState.animateScrollToItem(messages.size - 1)
    }

    fun addPhoto(file: File?) {
        if (file == null) {
            error = "That file couldn't be read as a photo."
        } else if (attachments.size < MAX_ATTACHMENTS) {
            attachments += file
        }
    }

    // --- photo sources ---------------------------------------------------------------
    val galleryLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.PickMultipleVisualMedia(MAX_ATTACHMENTS),
    ) { uris ->
        scope.launch {
            uris.take(MAX_ATTACHMENTS - attachments.size).forEach { uri ->
                addPhoto(withContext(Dispatchers.IO) { importForUpload(context, uri) })
            }
        }
    }
    var pendingCameraFile by remember { mutableStateOf<File?>(null) }
    val cameraLauncher = rememberLauncherForActivityResult(ActivityResultContracts.TakePicture()) { saved ->
        val file = pendingCameraFile
        if (saved && file != null) {
            scope.launch { addPhoto(withContext(Dispatchers.IO) { downscaleForUpload(file) }) }
        }
    }
    fun launchCamera() {
        val file = File(context.cacheDir, "chat_${System.nanoTime()}.jpg")
        pendingCameraFile = file
        val uri = FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", file)
        try {
            cameraLauncher.launch(uri)
        } catch (_: ActivityNotFoundException) {
            error = "No camera app is available on this phone."
        }
    }
    val cameraPermission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) launchCamera() else error = "Allow camera access to take a photo, or choose one from your gallery."
    }
    val voiceLauncher = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        if (result.resultCode == Activity.RESULT_OK) {
            result.data?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)?.firstOrNull()?.let { input = it }
        }
    }

    fun send(text: String) {
        val trimmed = text.trim()
        if ((trimmed.isBlank() && attachments.isEmpty()) || sending) return
        val photos = attachments.toList()
        messages += UiMessage(null, true, trimmed, photos = photos)
        val sentIndex = messages.lastIndex
        input = ""
        attachments.clear()
        error = null
        sending = true
        scope.launch {
            repository.chat(activeThread, trimmed, photos)
                .onSuccess { reply ->
                    activeThread = reply.thread_id
                    notice = reply.notice
                    messages += UiMessage(
                        reply.message.id, false, reply.message.text,
                        sources = reply.message.sources, webResearch = reply.message.web_research,
                    )
                    if (autoRead) {
                        speakingIndex = messages.lastIndex
                        speaker.speak(reply.message.text)
                    }
                }
                .onFailure { failure ->
                    // The turn wasn't saved server-side: put the question and photos back so
                    // the user can resend, rather than leaving a message that got no answer.
                    messages.removeAt(sentIndex)
                    input = trimmed
                    attachments.addAll(photos)
                    error = failure.message ?: "Something went wrong. Please try again."
                    notice = (failure as? ChatException)?.notice
                }
            sending = false
        }
    }

    fun newChat() {
        speaker.stop()
        messages.clear()
        attachments.clear()
        activeThread = null
        input = ""
        error = null
        notice = null
    }

    NsScreenScaffold(
        title = "Ask NutriScan",
        onBack = { speaker.stop(); onBack() },
        actions = {
            IconButton(onClick = { newChat() }) { Icon(Icons.Rounded.Add, contentDescription = "New chat") }
            IconButton(onClick = onOpenThreads) { Icon(Icons.Rounded.History, contentDescription = "Past chats") }
            IconButton(onClick = { showSettings = true }) { Icon(Icons.Rounded.Tune, contentDescription = "Assistant settings") }
        },
    ) { padding ->
        Column(modifier = Modifier.fillMaxSize().padding(padding).imePadding()) {
            notice?.let {
                Card(
                    colors = CardDefaults.cardColors(containerColor = NsAmber.copy(alpha = 0.25f)),
                    shape = RoundedCornerShape(0.dp),
                    modifier = Modifier.fillMaxWidth(),
                ) { Text(it, modifier = Modifier.padding(12.dp), style = MaterialTheme.typography.titleSmall) }
            }
            LazyColumn(
                state = listState,
                modifier = Modifier.weight(1f).fillMaxWidth().padding(horizontal = 16.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                item {
                    Spacer(Modifier.height(8.dp))
                    Text(
                        "Ask about food, nutrition, medicines or whether a product looks genuine. Attach a photo of a pack, " +
                            "a nutrition table or a medicine box. General information, not medical advice.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                if (loadingThread) item { CircularProgressIndicator(modifier = Modifier.padding(16.dp)) }
                if (messages.isEmpty() && !loadingThread) {
                    item {
                        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            starters.forEach { starter ->
                                AssistChip(onClick = { input = starter }, label = { Text(starter) })
                            }
                        }
                    }
                }
                itemsIndexed(messages) { index, message ->
                    Box(
                        modifier = Modifier.fillMaxWidth(),
                        contentAlignment = if (message.fromUser) Alignment.CenterEnd else Alignment.CenterStart,
                    ) {
                        Card(
                            shape = RoundedCornerShape(16.dp),
                            colors = CardDefaults.cardColors(
                                containerColor = if (message.fromUser) MaterialTheme.colorScheme.primaryContainer
                                else MaterialTheme.colorScheme.surfaceVariant,
                            ),
                            modifier = Modifier.widthIn(max = 330.dp),
                        ) {
                            Column(modifier = Modifier.padding(12.dp)) {
                                if (message.photos.isNotEmpty()) {
                                    Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                        message.photos.forEach { photo ->
                                            AsyncImage(
                                                model = photo,
                                                contentDescription = "Attached photo",
                                                contentScale = ContentScale.Crop,
                                                modifier = Modifier.size(84.dp).clip(RoundedCornerShape(10.dp)),
                                            )
                                        }
                                    }
                                    Spacer(Modifier.height(6.dp))
                                } else if (message.photoCount > 0) {
                                    Text(
                                        "📷 ${message.photoCount} photo${if (message.photoCount == 1) "" else "s"} attached",
                                        style = MaterialTheme.typography.labelSmall,
                                    )
                                }
                                if (message.text.isNotBlank() && message.text != "(photo)") {
                                    Text(message.text, style = MaterialTheme.typography.bodyMedium)
                                }
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
                                    Row(verticalAlignment = Alignment.CenterVertically) {
                                        val speakingThis = speaker.isSpeaking && speakingIndex == index
                                        IconButton(onClick = {
                                            if (speakingThis) speaker.stop() else { speakingIndex = index; speaker.speak(message.text) }
                                        }) {
                                            Icon(
                                                if (speakingThis) Icons.Rounded.Stop else Icons.AutoMirrored.Rounded.VolumeUp,
                                                contentDescription = if (speakingThis) "Stop reading" else "Read aloud",
                                            )
                                        }
                                        message.id?.let { id ->
                                            fun rate(value: Int) {
                                                val newValue = if (message.feedback == value) 0 else value
                                                messages[index] = message.copy(feedback = newValue.takeIf { it != 0 })
                                                scope.launch { repository.rateAnswer(id, newValue) }
                                            }
                                            IconButton(onClick = { rate(1) }) {
                                                Icon(
                                                    Icons.Rounded.ThumbUp, contentDescription = "Helpful",
                                                    tint = if (message.feedback == 1) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant,
                                                )
                                            }
                                            IconButton(onClick = { rate(-1) }) {
                                                Icon(
                                                    Icons.Rounded.ThumbDown, contentDescription = "Not helpful",
                                                    tint = if (message.feedback == -1) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant,
                                                )
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                if (sending) {
                    item {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            CircularProgressIndicator(modifier = Modifier.size(20.dp), strokeWidth = 2.dp)
                            Spacer(Modifier.width(8.dp))
                            Text(
                                if (messages.lastOrNull()?.photos?.isNotEmpty() == true) "Reading your photo…" else "Researching…",
                                style = MaterialTheme.typography.bodySmall,
                            )
                        }
                    }
                }
                error?.let { item { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) } }
                item { Spacer(Modifier.height(8.dp)) }
            }

            // --- attachments being prepared --------------------------------------------------------
            if (attachments.isNotEmpty()) {
                LazyRow(
                    modifier = Modifier.padding(horizontal = 16.dp),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    itemsIndexed(attachments.toList()) { index, file ->
                        Box {
                            AsyncImage(
                                model = file,
                                contentDescription = "Photo to send",
                                contentScale = ContentScale.Crop,
                                modifier = Modifier.size(64.dp).clip(RoundedCornerShape(10.dp)),
                            )
                            IconButton(
                                onClick = { attachments.removeAt(index) },
                                modifier = Modifier.align(Alignment.TopEnd).size(24.dp),
                            ) { Icon(Icons.Rounded.Close, contentDescription = "Remove photo") }
                        }
                    }
                }
            }
            Row(
                modifier = Modifier.fillMaxWidth().padding(horizontal = 8.dp, vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Box {
                    IconButton(onClick = { showAttachMenu = true }, enabled = attachments.size < MAX_ATTACHMENTS) {
                        Icon(Icons.Rounded.AddAPhoto, contentDescription = "Attach a photo")
                    }
                    DropdownMenu(expanded = showAttachMenu, onDismissRequest = { showAttachMenu = false }) {
                        DropdownMenuItem(
                            text = { Text("Take a photo") },
                            leadingIcon = { Icon(Icons.Rounded.AddAPhoto, contentDescription = null) },
                            onClick = {
                                showAttachMenu = false
                                if (ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) {
                                    launchCamera()
                                } else {
                                    cameraPermission.launch(Manifest.permission.CAMERA)
                                }
                            },
                        )
                        DropdownMenuItem(
                            text = { Text("Choose from gallery") },
                            leadingIcon = { Icon(Icons.Rounded.PhotoLibrary, contentDescription = null) },
                            onClick = {
                                showAttachMenu = false
                                galleryLauncher.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly))
                            },
                        )
                    }
                }
                OutlinedTextField(
                    value = input,
                    onValueChange = { input = it.take(1000) },
                    placeholder = { Text(if (attachments.isEmpty()) "Ask a question…" else "Ask about the photo…") },
                    modifier = Modifier.weight(1f),
                    maxLines = 4,
                )
                IconButton(onClick = {
                    val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                        putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                        putExtra(RecognizerIntent.EXTRA_PROMPT, "Ask NutriScan")
                    }
                    try {
                        voiceLauncher.launch(intent)
                    } catch (_: ActivityNotFoundException) {
                        error = "Voice input isn't available on this phone. Type your question instead."
                    }
                }) { Icon(Icons.Rounded.Mic, contentDescription = "Ask by voice") }
                IconButton(
                    onClick = { send(input) },
                    enabled = (input.isNotBlank() || attachments.isNotEmpty()) && !sending,
                ) { Icon(Icons.AutoMirrored.Rounded.Send, contentDescription = "Send") }
            }
        }
    }

    // First visit: explain privacy and ask about consent. Also reachable from the settings button.
    if (showSettings || !introSeen) {
        AssistantSettingsDialog(
            repository = repository,
            firstTime = !introSeen && !showSettings,
            onDismiss = {
                showSettings = false
                scope.launch { preferences.setAssistantIntroSeen() }
            },
            onChatsDeleted = { newChat() },
        )
    }
}
