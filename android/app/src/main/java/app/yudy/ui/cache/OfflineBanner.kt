package app.yudy.ui.cache

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import java.time.Instant

val LocalCachedReadOnly = staticCompositionLocalOf { false }

@Composable
fun OfflineContainer(content: @Composable () -> Unit) {
    val model: CacheViewModel = viewModel()
    val state by model.status.collectAsStateWithLifecycle()
    Column(Modifier.fillMaxSize()) {
        if(state.readOnly) Surface(color = MaterialTheme.colorScheme.secondaryContainer) {
            Column(Modifier.fillMaxWidth().statusBarsPadding().padding(12.dp)) {
                Text("Cached data · read only", style = MaterialTheme.typography.labelLarge)
                Text("Last fetched ${Instant.ofEpochMilli(state.stale.values.minOrNull()!!)}. Prices and preferences may be outdated; prices are not live.", style = MaterialTheme.typography.bodySmall)
                TextButton(onClick = model::reconnect) { Text("Reconnect and reload") }
            }
        }
        Box(Modifier.weight(1f)) { key(state.generation) { CompositionLocalProvider(LocalCachedReadOnly provides state.readOnly) { content() } } }
    }
}
