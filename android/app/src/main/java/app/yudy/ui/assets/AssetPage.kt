package app.yudy.ui.assets

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import app.yudy.domain.assets.*
import java.time.Instant

@Composable
fun AssetPage(id: String, user: app.yudy.domain.auth.AuthUser, auth: app.yudy.ui.auth.AuthViewModel, consent: () -> Unit, origin: String = "Discover", back: () -> Unit) {
    val model: AssetDetailsViewModel = viewModel()
    val state by model.state.collectAsStateWithLifecycle()
    LaunchedEffect(id) { model.bind(id) }
    DisposableEffect(id) { onDispose { model.clear() } }
    BackHandler { back() }
    Column(Modifier.fillMaxSize().safeDrawingPadding().verticalScroll(rememberScrollState()).padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)) {
        TextButton(onClick = back) { Text("Back to $origin") }
        DemoBanner()
        if (state.busy) { CircularProgressIndicator(); Text("Loading the asset…") }
        state.error?.let {
            Text(it, color = MaterialTheme.colorScheme.error)
            Button(onClick = model::reload) { Text("Retry asset") }
        }
        state.details?.let { detail ->
            val asset = detail.asset
            Text(asset.symbol, style = MaterialTheme.typography.headlineLarge)
            Text(asset.name, style = MaterialTheme.typography.titleLarge)
            Text("Underlying ${if (asset.type == "ETF") "ETF" else "stock"} · ${detail.country ?: asset.region ?: "Region unavailable"}",
                style = MaterialTheme.typography.labelLarge)
            Text(money(asset.price, asset.currency), style = MaterialTheme.typography.headlineMedium)
            Text("Demo snapshot · ${asset.asOf?.take(10) ?: "Unavailable"} · ${asset.currency}",
                style = MaterialTheme.typography.bodySmall)
            AssetActions(user, id, auth, consent)
            BuyAction(user, id, detail.tokens, auth, consent)
            Text("Performance", style = MaterialTheme.typography.titleLarge)
            Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                historyPeriods.forEach { (code, title) -> FilterChip(selected = state.period == code,
                    onClick = { model.period(code) }, label = { Text(title) }) }
            }
            if (state.historyBusy) { CircularProgressIndicator(); Text("Loading ${historyPeriods[state.period]} history…") }
            state.historyError?.let {
                Text(it, color = MaterialTheme.colorScheme.error)
                TextButton(onClick = { model.period(state.period) }) { Text("Retry history") }
            }
            state.history?.let { history ->
                Text("${percent(history.performance)} · ${historyPeriods[history.period]}", style = MaterialTheme.typography.titleMedium)
                PerformanceChart(history, asset.currency)
            }
            Text("In simple words", style = MaterialTheme.typography.titleLarge)
            Text(detail.description)
            Text(listOfNotNull(asset.sector, asset.industry, asset.market).joinToString(" · "),
                style = MaterialTheme.typography.bodySmall)
            if (detail.themes.isNotEmpty()) Text("Themes: ${detail.themes.joinToString { it.title }}")
            Disclosure("Key numbers · underlying asset", false) {
                val numbers = detail.fundamentals
                if (numbers == null) Text("Financial figures are unavailable.") else {
                    val fields = listOf("Market cap" to amount(numbers.marketCap), "P/E" to amount(numbers.pe),
                        "EPS (${asset.currency})" to amount(numbers.eps), "Revenue (${asset.currency})" to amount(numbers.revenue),
                        "Revenue growth" to percent(numbers.revenueGrowth), "Net income (${asset.currency})" to amount(numbers.netIncome),
                        "Debt (${asset.currency})" to amount(numbers.debt), "Cash flow (${asset.currency})" to amount(numbers.cashFlow),
                        "Dividend (${asset.currency})" to amount(numbers.dividend), "Dividend yield" to percent(numbers.dividendYield))
                    fields.forEach { (label, value) -> InfoLine(label, value) }
                    Text("Synthetic figures · ${numbers.updatedAt.take(10)}", style = MaterialTheme.typography.bodySmall)
                }
            }
            Disclosure("Risks · underlying asset", true) {
                Text("These are asset-specific topics, separate from your Risk Profile.", style = MaterialTheme.typography.bodySmall)
                if (detail.risks.isEmpty()) Text("Asset-specific risk information is unavailable.")
                detail.risks.forEach { risk -> Text(risk.title, style = MaterialTheme.typography.titleMedium); Text(risk.description) }
            }
            Disclosure("Tokenized representations (${detail.tokens.size})", true) {
                Text("A token is a separate representation of the underlying asset. The examples below are fictional and unavailable for transactions.")
                if (detail.tokens.isEmpty()) Text("No tokenized representation is available in this demo.")
                detail.tokens.forEach { token ->
                    HorizontalDivider()
                    Text(token.symbol, style = MaterialTheme.typography.titleLarge)
                    Text(token.name, style = MaterialTheme.typography.titleMedium)
                    InfoLine("Underlying asset", "${asset.symbol} · ${asset.name}")
                    InfoLine("Issuer", token.issuer)
                    InfoLine("Tokenization provider", token.provider)
                    InfoLine("Backing", token.backing)
                    InfoLine("Proof of reserves", token.reservesUrl ?: "Not provided or verified")
                    InfoLine("Oracle", token.oracle)
                    InfoLine("Oracle reference", token.oracleReference)
                    InfoLine("Corporate actions", token.corporateActions)
                    InfoLine("Availability", token.availability)
                }
            }
        }
    }
}

@Composable
private fun InfoLine(label: String, value: String?) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(label, style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary)
        Text(value ?: "Unavailable", style = MaterialTheme.typography.bodyMedium)
    }
}

@Composable
private fun Disclosure(title: String, initiallyOpen: Boolean, content: @Composable ColumnScope.() -> Unit) {
    var expanded by remember { mutableStateOf(initiallyOpen) }
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            TextButton(onClick = { expanded = !expanded }, modifier = Modifier.fillMaxWidth()) {
                Text("$title · ${if (expanded) "Hide" else "Show"}")
            }
            if (expanded) content()
        }
    }
}

@Composable
private fun PerformanceChart(history: PriceHistory, currency: String) {
    if (history.points.size < 2) { Text("Not enough price history for this period."); return }
    val points = remember(history) { history.points.map { Instant.parse(it.timestamp).toEpochMilli() to it.close.toDouble() } }
    val firstTime = points.first().first
    val duration = (points.last().first - firstTime).coerceAtLeast(1).toDouble()
    val low = points.minOf { it.second }
    val high = points.maxOf { it.second }
    val span = (high - low).takeIf { it > 0 } ?: 1.0
    val line = MaterialTheme.colorScheme.primary
    val grid = MaterialTheme.colorScheme.outlineVariant
    Text("Range: ${money(low.toString(), currency)} – ${money(high.toString(), currency)}", style = MaterialTheme.typography.labelMedium)
    Canvas(Modifier.fillMaxWidth().height(200.dp).semantics {
        contentDescription = "Synthetic ${history.period} price chart. ${history.points.size} samples; change ${percent(history.performance)}."
    }) {
        val inset = 8.dp.toPx()
        val width = size.width - inset * 2
        val height = size.height - inset * 2
        repeat(3) { index ->
            val y = inset + height * index / 2
            drawLine(grid, Offset(inset, y), Offset(size.width - inset, y), strokeWidth = 1.dp.toPx())
        }
        val path = Path()
        points.forEachIndexed { index, (timestamp, price) ->
            val x = inset + ((timestamp - firstTime) / duration * width).toFloat()
            val y = if (high == low) size.height / 2 else inset + ((high - price) / span * height).toFloat()
            if (index == 0) path.moveTo(x, y) else path.lineTo(x, y)
        }
        drawPath(path, line, style = Stroke(width = 3.dp.toPx()))
    }
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        Text(history.points.first().timestamp.take(10), style = MaterialTheme.typography.labelSmall)
        Text(history.points.last().timestamp.take(10), style = MaterialTheme.typography.labelSmall)
    }
    Text("Sampled synthetic history, anchored to the last demo snapshot.", style = MaterialTheme.typography.bodySmall)
}
