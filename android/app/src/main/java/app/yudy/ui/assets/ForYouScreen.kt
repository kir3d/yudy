package app.yudy.ui.assets

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Refresh
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import app.yudy.domain.assets.XStockSuggestion
import app.yudy.domain.auth.AuthUser
import app.yudy.ui.auth.AuthViewModel

@Composable
fun ForYouScreen(
    user: AuthUser,
    auth: AuthViewModel,
    consent: () -> Unit,
    openSettings: () -> Unit,
    openAsset: (XStockSuggestion) -> Unit,
    openBuy: (XStockSuggestion) -> Unit,
    modifier: Modifier = Modifier,
) {
    val model: ForYouViewModel = viewModel()
    val state by model.state.collectAsStateWithLifecycle()
    LaunchedEffect(user.id) { model.bind(user.id) }
    LaunchedEffect(state.consentRequired, state.sessionExpired, state.profileRequired) {
        if (state.consentRequired) consent()
        if (state.sessionExpired) auth.restore()
        if (state.profileRequired) openSettings()
    }
    LazyColumn(modifier.padding(horizontal = 20.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
        contentPadding = PaddingValues(bottom = 24.dp)) {
        item {
            Row(Modifier.fillMaxWidth().padding(top = 8.dp, bottom = 6.dp),
                verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("LIVE xSTOCKS · PERSONALIZED",
                        style = MaterialTheme.typography.labelSmall,
                        color = app.yudy.ui.theme.YudyColors.Cyan)
                    Spacer(Modifier.height(6.dp))
                    Text("Selected for exploration",
                        style = MaterialTheme.typography.headlineMedium)
                    Spacer(Modifier.height(4.dp))
                    Text("Based on anonymous profile signals. This is not investment advice.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                OutlinedIconButton(onClick = { model.reload(forceRefresh = true) }, enabled = !state.busy) {
                    Icon(Icons.Outlined.Refresh, "Refresh selection")
                }
            }
        }
        if (state.busy) item {
            Column(Modifier.fillMaxWidth().padding(vertical = 36.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(12.dp)) {
                CircularProgressIndicator()
                Text("Reviewing the live xStocks catalog…")
            }
        }
        state.error?.let { message -> item {
            Surface(color = MaterialTheme.colorScheme.errorContainer,
                shape = RoundedCornerShape(16.dp)) {
                Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(message, color = MaterialTheme.colorScheme.onErrorContainer)
                    TextButton(onClick = { model.reload(forceRefresh = true) }) { Text("Try again") }
                }
            }
        } }
        state.actionError?.let { message -> item {
            Text(message, color = MaterialTheme.colorScheme.error,
                style = MaterialTheme.typography.bodySmall)
        } }
        if (!state.busy && state.error == null && state.items.isEmpty()) item {
            Text("No active xStocks are available right now.")
        }
        items(state.items, key = { it.id }) { item ->
            XStockCard(item, busy = item.id in state.changing,
                onAction = { model.change(item, it) }, onBuy = { openBuy(item) }) {
                openAsset(item)
            }
        }
        if (state.items.isNotEmpty()) item {
            Text("Asset data: xStocks · 7-day charts: CoinGecko · Updated ${state.generatedAt?.take(10).orEmpty()}",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}
