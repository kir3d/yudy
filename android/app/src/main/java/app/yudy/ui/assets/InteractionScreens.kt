package app.yudy.ui.assets

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import app.yudy.domain.auth.AuthUser
import app.yudy.ui.auth.AuthViewModel

@Composable
fun AssetActions(user: AuthUser, id: String, auth: AuthViewModel, consent: () -> Unit) {
    val model: InteractionViewModel = viewModel()
    val state by model.state.collectAsStateWithLifecycle()
    LaunchedEffect(user.id, id) { model.bind(user.id, id); model.recordView() }
    DisposableEffect(user.id, id) { onDispose { model.clear() } }
    LaunchedEffect(state.consentRequired, state.sessionExpired) {
        if (state.consentRequired) consent()
        if (state.sessionExpired) auth.restore()
    }
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text("Your actions", style = MaterialTheme.typography.titleMedium)
        Text("Like records your interest. Save keeps an asset in Saved.", style = MaterialTheme.typography.bodySmall)
        val enabled = !app.yudy.ui.cache.LocalCachedReadOnly.current && !state.busy && state.value != null && state.error == null
        val value = state.value
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            FilterChip(selected = value?.liked == true, enabled = enabled, onClick = { model.change("like") }, label = { Text("Like") })
            FilterChip(selected = value?.saved == true, enabled = enabled, onClick = { model.change("save") }, label = { Text(if (value?.saved == true) "Saved · Remove" else "Save") })
        }
        FilterChip(selected = value?.disliked == true, enabled = enabled, onClick = { model.change("dislike") }, label = { Text(if (value?.disliked == true) "Not interested · Undo" else "Not interested") })
        if (state.busy) LinearProgressIndicator(Modifier.fillMaxWidth())
        state.error?.let { Text(it, color = MaterialTheme.colorScheme.error); TextButton(onClick = model::reload) { Text("Reload actions") } }
    }
}

@Composable
fun SavedScreen(
    user: AuthUser,
    auth: AuthViewModel,
    consent: () -> Unit,
    openAsset: (app.yudy.domain.assets.XStockSuggestion) -> Unit,
    openBuy: (app.yudy.domain.assets.XStockSuggestion) -> Unit,
    modifier: Modifier = Modifier,
) {
    val model: SavedViewModel = viewModel()
    val state by model.state.collectAsStateWithLifecycle()
    LaunchedEffect(user.id) { model.bind(user.id) }
    DisposableEffect(user.id) { onDispose { model.clear() } }
    LaunchedEffect(state.consentRequired, state.sessionExpired) {
        if (state.consentRequired) consent()
        if (state.sessionExpired) auth.restore()
    }
    Column(modifier.padding(horizontal = 20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("YUDY // SAVED xSTOCKS", style = MaterialTheme.typography.labelSmall,
            color = app.yudy.ui.theme.YudyColors.Cyan,
            modifier = Modifier.padding(top = 8.dp))
        Text("Saved for exploration", style = MaterialTheme.typography.headlineSmall)
        Text("Only real xStocks you explicitly save appear here.",
            color = MaterialTheme.colorScheme.onSurfaceVariant)
        LazyColumn(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            if (state.busy) item { CircularProgressIndicator() }
            state.error?.let { error -> item { Text(error, color = MaterialTheme.colorScheme.error); Button(onClick = model::reload) { Text("Retry Saved") } } }
            state.actionError?.let { error -> item { Text(error, color = MaterialTheme.colorScheme.error) } }
            if (!state.busy && state.error == null && state.items.isEmpty()) item {
                Text("No saved xStocks yet. Tap the star on any card to keep it here.")
            }
            listOf("STOCK" to "Stocks", "ETF" to "ETFs").forEach { (type, title) ->
                val assets = state.items.filter { it.assetType == type }
                if (assets.isNotEmpty()) {
                    item { Text(title, style = MaterialTheme.typography.titleLarge) }
                    items(assets, key = { it.id }) { asset ->
                        XStockCard(asset, busy = asset.id in state.changing,
                            onAction = { model.change(asset, it) }, onBuy = { openBuy(asset) }) {
                            openAsset(asset)
                        }
                    }
                }
            }
            if (!state.busy) item { TextButton(onClick = model::reload) { Text("Refresh Saved") } }
        }
    }
}
