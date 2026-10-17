package com.nutriscan.app.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Delete
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.ListItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.nutriscan.app.data.model.ChatThreadSummary
import com.nutriscan.app.data.repository.NutriScanRepository
import com.nutriscan.app.ui.components.NsButton
import com.nutriscan.app.ui.components.NsScreenScaffold
import kotlinx.coroutines.launch

/** The user's past conversations with the assistant: reopen one, delete one, or start a new chat. */
@Composable
fun ChatThreadsScreen(
    repository: NutriScanRepository,
    onBack: () -> Unit,
    onOpen: (threadId: Int?) -> Unit,
) {
    val scope = rememberCoroutineScope()
    var threads by remember { mutableStateOf<List<ChatThreadSummary>?>(null) }
    var error by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(Unit) {
        repository.chatThreads().onSuccess { threads = it }.onFailure { error = it.message }
    }

    NsScreenScaffold(title = "Past chats", onBack = onBack) { padding ->
        Column(modifier = Modifier.fillMaxSize().padding(padding).padding(16.dp)) {
            NsButton(text = "New chat", onClick = { onOpen(null) }, modifier = Modifier.fillMaxWidth())
            Spacer(Modifier.height(12.dp))
            val list = threads
            when {
                error != null -> Text(error ?: "", color = MaterialTheme.colorScheme.error)
                list == null -> CircularProgressIndicator()
                list.isEmpty() -> Text(
                    "No conversations yet. Ask the assistant something and it will appear here.",
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                else -> LazyColumn {
                    items(list, key = { it.id }) { thread ->
                        ListItem(
                            modifier = Modifier.clickable { onOpen(thread.id) },
                            headlineContent = { Text(thread.title, maxLines = 2) },
                            supportingContent = { Text(thread.updated_at.take(10)) },
                            trailingContent = {
                                IconButton(onClick = {
                                    scope.launch {
                                        repository.deleteChatThread(thread.id)
                                            .onSuccess { threads = list.filterNot { it.id == thread.id } }
                                            .onFailure { error = it.message }
                                    }
                                }) { Icon(Icons.Rounded.Delete, contentDescription = "Delete this chat") }
                            },
                        )
                        HorizontalDivider()
                    }
                }
            }
        }
    }
}
