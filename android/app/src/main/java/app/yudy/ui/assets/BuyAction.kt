package app.yudy.ui.assets

import android.content.ActivityNotFoundException
import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import app.yudy.BuildConfig
import app.yudy.domain.assets.*
import app.yudy.domain.auth.AuthUser
import app.yudy.ui.auth.AuthViewModel

@Composable
fun BuyAction(user: AuthUser, assetId: String, tokens: List<TokenInfo>, auth: AuthViewModel, consent: () -> Unit) {
    val model: BuyViewModel = viewModel()
    val state by model.state.collectAsStateWithLifecycle()
    val context = LocalContext.current
    var choosing by remember(assetId) { mutableStateOf(false) }
    LaunchedEffect(user.id, assetId) { model.bind(user.id, assetId) }
    DisposableEffect(user.id, assetId) { onDispose { model.clear() } }
    LaunchedEffect(state.consentRequired, state.sessionExpired) {
        if(state.consentRequired) consent()
        if(state.sessionExpired) auth.restore()
    }
    LaunchedEffect(state.launchUrl) {
        val url = state.launchUrl ?: return@LaunchedEffect
        model.consumeLaunch()
        if(!validExternalBuyUrl(url, BuildConfig.DEBUG && state.link?.demo == true)) { model.launchFailed(); return@LaunchedEffect }
        try { context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)).addCategory(Intent.CATEGORY_BROWSABLE)); model.dismiss() }
        catch(error: ActivityNotFoundException) { model.launchFailed() }
        catch(error: SecurityException) { model.launchFailed() }
    }
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Button(onClick = { choosing = true }, enabled = tokens.isNotEmpty() && !state.busy && !app.yudy.ui.cache.LocalCachedReadOnly.current, modifier = Modifier.fillMaxWidth()) { Text("BUY") }
        Text(if(tokens.isEmpty()) "No external demo representation is available." else "Opens an external provider demo. Purchases are unavailable.", style = MaterialTheme.typography.bodySmall)
    }
    if(choosing) AlertDialog(onDismissRequest = { choosing = false }, title = { Text("Choose a token representation") }, text = {
        Column(Modifier.heightIn(max = 360.dp).verticalScroll(rememberScrollState())) {
            tokens.forEach { token -> TextButton(onClick = { choosing = false; model.preview(token.id) }) { Text("${token.symbol} · ${token.issuer ?: token.name}") } }
        }
    }, confirmButton = {}, dismissButton = { TextButton(onClick = { choosing = false }) { Text("Cancel") } })
    if(state.tokenId != null) AlertDialog(onDismissRequest = model::dismiss,
        title = { Text("Good luck! ❤️") }, text = {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text("YUDY will be here when you're back.")
                if(state.busy) CircularProgressIndicator()
                state.link?.let { link ->
                    Text("${link.provider} · ${link.tokenSymbol}", style = MaterialTheme.typography.titleMedium)
                    Text("${Uri.parse(link.url).host}:${Uri.parse(link.url).port.takeIf { it != -1 } ?: if(Uri.parse(link.url).scheme == "https") 443 else 80}")
                    Text("You're leaving YUDY. This demo cannot place orders or handle money. YUDY only opens the provider page.")
                }
                state.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            }
        }, confirmButton = {
            TextButton(enabled = !state.busy, onClick = { if(state.link == null) model.preview(state.tokenId!!) else model.confirm() }) {
                Text(if(state.link == null) "Retry link" else if(state.confirmed) "Retry browser" else "Open provider demo")
            }
        }, dismissButton = { TextButton(onClick = model::dismiss) { Text("Cancel") } })
}
