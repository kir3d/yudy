package app.yudy.ui.assets

import android.content.Intent
import android.net.Uri
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import app.yudy.domain.assets.XStockSuggestion
import app.yudy.ui.theme.YudyColors
import coil.compose.AsyncImage
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel

@Composable
fun XStockCard(
    item: XStockSuggestion,
    busy: Boolean = false,
    onAction: (String) -> Unit = {},
    onBuy: () -> Unit = {},
    open: () -> Unit,
) {
    val positive = (item.priceChangePercentage7d ?: 0.0) >= 0.0
    val trendColor = if (positive) YudyColors.Cyan else MaterialTheme.colorScheme.error
    Surface(onClick = open, modifier = Modifier.fillMaxWidth(), color = YudyColors.Surface,
        shape = RoundedCornerShape(12.dp), border = BorderStroke(1.dp, YudyColors.Line),
        tonalElevation = 0.dp) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                XStockLogo(item, 46.dp)
                Column(Modifier.weight(1f)) {
                    Row(verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text(item.symbol, style = MaterialTheme.typography.titleLarge)
                        Surface(color = YudyColors.SurfaceVariant, shape = RoundedCornerShape(6.dp),
                            border = BorderStroke(1.dp, YudyColors.Line)) {
                            Text(item.assetType.uppercase(), Modifier.padding(horizontal = 7.dp, vertical = 3.dp),
                                style = MaterialTheme.typography.labelSmall, color = YudyColors.Mint)
                        }
                    }
                    Text(item.name.removeSuffix(" xStock"), style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 1, overflow = TextOverflow.Ellipsis)
                }
                Column(horizontalAlignment = Alignment.End) {
                    Text(item.price?.let { "${item.currency} $it" } ?: "—",
                        style = MaterialTheme.typography.titleMedium)
                    item.priceChangePercentage7d?.let {
                        Text("${signedPercent(it)} · 7D", style = MaterialTheme.typography.labelMedium,
                            color = trendColor)
                    }
                }
            }
            if (item.sparkline7d.size > 1) {
                XStockSparkline(item.sparkline7d, trendColor,
                    Modifier.fillMaxWidth().height(82.dp))
            } else {
                Box(Modifier.fillMaxWidth().height(82.dp), contentAlignment = Alignment.Center) {
                    Text("7-day chart unavailable", style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
            HorizontalDivider(color = YudyColors.Line)
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                XStockAction("Like", if (item.interaction.liked) Icons.Outlined.ThumbUp
                    else Icons.Outlined.ThumbUpOffAlt, item.interaction.liked, busy,
                    Modifier.weight(1f)) { onAction("like") }
                XStockAction("Dislike", if (item.interaction.disliked) Icons.Outlined.ThumbDown
                    else Icons.Outlined.ThumbDownOffAlt, item.interaction.disliked, busy,
                    Modifier.weight(1f)) { onAction("dislike") }
                XStockAction("Save", if (item.interaction.saved) Icons.Outlined.Star
                    else Icons.Outlined.StarBorder, item.interaction.saved, busy,
                    Modifier.weight(1f)) { onAction("save") }
                XStockAction("Buy", Icons.Outlined.OpenInNew, false, busy,
                    Modifier.weight(1f), accent = true, click = onBuy)
            }
        }
    }
}

@Composable
private fun XStockAction(
    label: String,
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    selected: Boolean,
    busy: Boolean,
    modifier: Modifier = Modifier,
    accent: Boolean = false,
    click: () -> Unit,
) {
    TextButton(onClick = click, enabled = !busy, modifier = modifier.heightIn(min = 48.dp),
        contentPadding = PaddingValues(horizontal = 2.dp, vertical = 8.dp),
        colors = ButtonDefaults.textButtonColors(
            contentColor = if (selected || accent) YudyColors.Cyan else YudyColors.Mint,
        )) {
        Column(horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(3.dp)) {
            Icon(icon, contentDescription = null, modifier = Modifier.size(19.dp))
            Text(label, style = MaterialTheme.typography.labelSmall, maxLines = 1)
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun XStockDetailScreen(item: XStockSuggestion, back: () -> Unit) {
    BackHandler(onBack = back)
    val positive = (item.priceChangePercentage7d ?: 0.0) >= 0.0
    val trendColor = if (positive) YudyColors.Cyan else MaterialTheme.colorScheme.error
    Scaffold(containerColor = MaterialTheme.colorScheme.background,
        topBar = {
            TopAppBar(title = { Text(item.symbol) }, navigationIcon = {
                IconButton(onClick = back) {
                    Icon(Icons.AutoMirrored.Outlined.ArrowBack, "Back")
                }
            }, colors = TopAppBarDefaults.topAppBarColors(
                containerColor = MaterialTheme.colorScheme.background))
        }) { insets ->
        LazyColumn(Modifier.fillMaxSize().padding(insets).padding(horizontal = 20.dp),
            verticalArrangement = Arrangement.spacedBy(18.dp),
            contentPadding = PaddingValues(bottom = 36.dp)) {
            item {
                Row(verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                    XStockLogo(item, 62.dp)
                    Column(Modifier.weight(1f)) {
                        Text(item.name, style = MaterialTheme.typography.headlineSmall)
                        Text("${item.underlyingSymbol} underlying · ${item.assetType.lowercase().replaceFirstChar { it.uppercase() }}",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
            item {
                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text("Current xStocks quote", style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Row(verticalAlignment = Alignment.Bottom,
                        horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        Text(item.price?.let { "${item.currency} $it" } ?: "Quote unavailable",
                            style = MaterialTheme.typography.headlineMedium)
                        item.priceChangePercentage24h?.let {
                            Text("${signedPercent(it)} · 24H", color = if (it >= 0) YudyColors.Cyan
                                else MaterialTheme.colorScheme.error,
                                style = MaterialTheme.typography.labelLarge,
                                modifier = Modifier.padding(bottom = 5.dp))
                        }
                    }
                }
            }
            item {
                Surface(color = YudyColors.Surface, shape = RoundedCornerShape(12.dp),
                    border = BorderStroke(1.dp, YudyColors.Line)) {
                    Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                            Text("Price movement", style = MaterialTheme.typography.titleMedium)
                            item.priceChangePercentage7d?.let {
                                Text("${signedPercent(it)} · 7D", color = trendColor,
                                    style = MaterialTheme.typography.labelLarge)
                            }
                        }
                        if (item.sparkline7d.size > 1) {
                            XStockSparkline(item.sparkline7d, trendColor,
                                Modifier.fillMaxWidth().height(190.dp))
                        } else {
                            Box(Modifier.fillMaxWidth().height(190.dp), contentAlignment = Alignment.Center) {
                                Text("7-day chart unavailable",
                                    color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        }
                        Text("7-day market chart from CoinGecko${item.marketDataAsOf?.take(10)?.let { " · $it" } ?: ""}",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
            item {
                Text("Market snapshot", style = MaterialTheme.typography.titleLarge)
                Spacer(Modifier.height(10.dp))
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    StatRow("24H high", moneyValue(item.high24h, item.currency),
                        "24H low", moneyValue(item.low24h, item.currency))
                    StatRow("Market cap", compactValue(item.marketCap, item.currency),
                        "24H volume", compactValue(item.volume24h, item.currency))
                    StatRow("All-time high", moneyValue(item.allTimeHigh, item.currency),
                        "Asset type", item.assetType.lowercase().replaceFirstChar { it.uppercase() })
                }
            }
            item {
                DetailPanel("Underlying asset") {
                    DetailLine("Ticker", item.underlyingSymbol)
                    DetailLine("Exchange", listOfNotNull(item.exchangeName, item.exchangeCode)
                        .distinct().joinToString(" · ").ifBlank { "Unavailable" })
                    DetailLine("Country", item.country ?: "Unavailable")
                    DetailLine("ISIN", item.underlyingIsin ?: "Unavailable")
                }
            }
            item {
                DetailPanel("Tokenized representation") {
                    Text("${item.symbol} represents economic exposure to ${item.underlyingSymbol}. It is a tokenized asset, not the underlying share itself.",
                        style = MaterialTheme.typography.bodyMedium)
                    if (item.networks.isNotEmpty()) {
                        Text("Available networks", style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Text(item.networks.joinToString(" · "), style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
            item {
                DetailPanel("Selected for exploration") {
                    Text(item.reason, style = MaterialTheme.typography.bodyMedium)
                    Text("This explanation is educational and is not investment advice.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
            item {
                Text("Official asset identity and current quote: xStocks · Market chart and metrics: CoinGecko",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun XStockBuyScreen(
    item: XStockSuggestion,
    back: () -> Unit,
    consent: () -> Unit,
    restoreSession: () -> Unit,
) {
    BackHandler(onBack = back)
    val model: XStockBuyViewModel = viewModel()
    val state by model.state.collectAsStateWithLifecycle()
    val context = LocalContext.current
    androidx.compose.runtime.LaunchedEffect(item.id) { model.bind(item.id) }
    androidx.compose.runtime.LaunchedEffect(state.consentRequired, state.sessionExpired) {
        if (state.consentRequired) consent()
        if (state.sessionExpired) restoreSession()
    }
    Scaffold(containerColor = MaterialTheme.colorScheme.background,
        topBar = {
            TopAppBar(title = { Text("Trade ${item.symbol}") }, navigationIcon = {
                IconButton(onClick = back) {
                    Icon(Icons.AutoMirrored.Outlined.ArrowBack, "Back")
                }
            }, colors = TopAppBarDefaults.topAppBarColors(
                containerColor = MaterialTheme.colorScheme.background))
        }) { insets ->
        LazyColumn(Modifier.fillMaxSize().padding(insets).padding(horizontal = 20.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
            contentPadding = PaddingValues(bottom = 36.dp)) {
            item {
                Row(verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(14.dp)) {
                    XStockLogo(item, 54.dp)
                    Column(Modifier.weight(1f)) {
                        Text(item.name, style = MaterialTheme.typography.headlineSmall)
                        Text("${item.assetType.uppercase()} · ${item.underlyingSymbol}",
                            style = MaterialTheme.typography.labelSmall, color = YudyColors.Cyan)
                    }
                }
            }
            item {
                Surface(color = YudyColors.Surface, shape = RoundedCornerShape(12.dp),
                    border = BorderStroke(1.dp, YudyColors.Line)) {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(7.dp)) {
                        Text("Choose an external venue", style = MaterialTheme.typography.titleMedium)
                        Text("YUDY does not execute trades or hold funds. Availability, fees and eligibility are determined by the venue.",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
            if (state.busy) item {
                Row(Modifier.fillMaxWidth().padding(vertical = 28.dp),
                    horizontalArrangement = Arrangement.Center) { CircularProgressIndicator() }
            }
            state.error?.let { message -> item {
                Surface(color = MaterialTheme.colorScheme.errorContainer,
                    shape = RoundedCornerShape(12.dp)) {
                    Column(Modifier.fillMaxWidth().padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text(message, color = MaterialTheme.colorScheme.onErrorContainer)
                        TextButton(onClick = model::reload) { Text("Try again") }
                    }
                }
            } }
            if (!state.busy && state.error == null && state.venues.isEmpty()) item {
                Text("No verified trading venues are available for this asset right now.",
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            items(state.venues.size) { index ->
                val venue = state.venues[index]
                Surface(color = YudyColors.Surface, shape = RoundedCornerShape(12.dp),
                    border = BorderStroke(1.dp, YudyColors.Line)) {
                    Row(Modifier.fillMaxWidth().padding(16.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        Surface(color = YudyColors.SurfaceVariant, shape = CircleShape) {
                            Icon(if (venue.kind == "DEX") Icons.Outlined.SwapHoriz else Icons.Outlined.Storefront,
                                contentDescription = null, tint = YudyColors.Cyan,
                                modifier = Modifier.padding(11.dp).size(22.dp))
                        }
                        Column(Modifier.weight(1f)) {
                            Text(venue.name, style = MaterialTheme.typography.titleMedium)
                            Text(listOfNotNull(venue.kind, venue.network).joinToString(" · "),
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        TextButton(onClick = {
                            model.recordOpen(venue) {
                                context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(venue.url)))
                            }
                        }, enabled = state.opening == null,
                            modifier = Modifier.heightIn(min = 44.dp),
                            contentPadding = PaddingValues(horizontal = 8.dp, vertical = 6.dp),
                            colors = ButtonDefaults.textButtonColors(contentColor = YudyColors.Cyan)) {
                            if (state.opening == venue.name) {
                                CircularProgressIndicator(Modifier.size(18.dp), strokeWidth = 2.dp)
                            } else {
                                Text("Buy")
                                Spacer(Modifier.width(6.dp))
                                Icon(Icons.Outlined.OpenInNew, null, Modifier.size(17.dp))
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun DetailPanel(title: String, content: @Composable ColumnScope.() -> Unit) {
    Surface(color = YudyColors.Surface, shape = RoundedCornerShape(12.dp),
        border = BorderStroke(1.dp, YudyColors.Line)) {
        Column(Modifier.fillMaxWidth().padding(18.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text(title, style = MaterialTheme.typography.titleMedium, color = YudyColors.Cyan)
            content()
        }
    }
}

@Composable
private fun DetailLine(label: String, value: String) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        Text(label, style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.SemiBold)
    }
}

@Composable
private fun StatRow(firstLabel: String, firstValue: String, secondLabel: String, secondValue: String) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        StatCell(firstLabel, firstValue, Modifier.weight(1f))
        StatCell(secondLabel, secondValue, Modifier.weight(1f))
    }
}

@Composable
private fun StatCell(label: String, value: String, modifier: Modifier = Modifier) {
    Surface(modifier, color = YudyColors.Surface, shape = RoundedCornerShape(10.dp),
        border = BorderStroke(1.dp, YudyColors.Line)) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(label, style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
            Text(value, style = MaterialTheme.typography.titleSmall)
        }
    }
}

@Composable
private fun XStockLogo(item: XStockSuggestion, size: Dp) {
    Box(Modifier.size(size).clip(CircleShape).background(Color.White),
        contentAlignment = Alignment.Center) {
        AsyncImage(model = item.logoUrl, contentDescription = "${item.name} logo",
            contentScale = ContentScale.Crop,
            modifier = Modifier.fillMaxSize().graphicsLayer(scaleX = 1.65f, scaleY = 1.65f))
    }
}

@Composable
private fun XStockSparkline(points: List<Double>, color: Color, modifier: Modifier = Modifier) {
    Canvas(modifier) {
        if (points.size < 2) return@Canvas
        val minimum = points.minOrNull() ?: return@Canvas
        val maximum = points.maxOrNull() ?: return@Canvas
        val range = (maximum - minimum).takeIf { it > 0.0 } ?: 1.0
        val line = Path()
        val fill = Path()
        var lastY = size.height / 2f
        points.forEachIndexed { index, value ->
            val x = size.width * index / (points.size - 1).toFloat()
            val y = size.height - ((value - minimum) / range * size.height * 0.82f).toFloat() - size.height * 0.09f
            lastY = y
            if (index == 0) {
                line.moveTo(x, y)
                fill.moveTo(x, size.height)
                fill.lineTo(x, y)
            } else {
                line.lineTo(x, y)
                fill.lineTo(x, y)
            }
        }
        fill.lineTo(size.width, size.height)
        fill.close()
        drawPath(fill, Brush.verticalGradient(listOf(color.copy(alpha = 0.22f), Color.Transparent)))
        drawPath(line, color, style = Stroke(width = 3.dp.toPx(), cap = StrokeCap.Round))
        drawCircle(color, radius = 3.5.dp.toPx(), center = Offset(size.width, lastY))
    }
}

private fun signedPercent(value: Double) = "${if (value >= 0) "+" else ""}${"%.2f".format(value)}%"
private fun moneyValue(value: Double?, currency: String) = value?.let { "$currency ${"%,.2f".format(it)}" } ?: "—"
private fun compactValue(value: Double?, currency: String): String {
    if (value == null) return "—"
    val formatted = when {
        value >= 1_000_000_000_000 -> "%.2fT".format(value / 1_000_000_000_000)
        value >= 1_000_000_000 -> "%.2fB".format(value / 1_000_000_000)
        value >= 1_000_000 -> "%.2fM".format(value / 1_000_000)
        value >= 1_000 -> "%.2fK".format(value / 1_000)
        else -> "%.2f".format(value)
    }
    return "$currency $formatted"
}
